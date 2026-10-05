"""Wheel smoke trace を path 一覧へ正規化し、wheel member と照合する。"""
from __future__ import annotations

import json
from pathlib import Path
import sys


def _under(path: Path, root: Path):
    try:
        return path.relative_to(root)
    except ValueError:
        return None


def main(argv):
    trace_file, package_root, scratch_root, worktree_root, out_dir = map(Path, argv[1:])
    package_root = package_root.resolve()
    scratch_root = scratch_root.resolve()
    worktree_root = worktree_root.resolve()
    package_base = package_root.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    events = []
    for raw in trace_file.read_text(encoding="utf-8").splitlines():
        if not raw:
            continue
        event = json.loads(raw)
        path = Path(event["path"]).expanduser().absolute()
        event["_path"] = path
        rel = _under(path, package_root)
        if rel is not None:
            event["display_path"] = "package:verantyx/" + rel.as_posix()
            event["package_member"] = "verantyx/" + rel.as_posix()
        else:
            rel = _under(path, scratch_root)
            if rel is not None:
                event["display_path"] = "scratch/" + rel.as_posix()
            else:
                rel = _under(path, worktree_root)
                if rel is not None:
                    event["display_path"] = "worktree/" + rel.as_posix()
                else:
                    event["display_path"] = "external/" + path.name
            event["package_member"] = None
        events.append(event)

    all_lines = sorted({
        "{}\t{}\t{}".format(event["status"], event["operation"], event["display_path"])
        for event in events
    })
    (out_dir / "open-paths.txt").write_text(
        "\n".join(all_lines) + ("\n" if all_lines else ""), encoding="utf-8"
    )
    package_events = [event for event in events if event["package_member"] is not None]
    opened_members = sorted({
        event["package_member"] for event in package_events if event["status"] == "opened"
    })
    failed_members = sorted({
        event["package_member"] for event in package_events if event["status"] == "failed"
    })
    (out_dir / "package-open-paths.txt").write_text(
        "".join(path + "\n" for path in opened_members), encoding="utf-8"
    )
    (out_dir / "package-open-failures.txt").write_text(
        "".join(path + "\n" for path in failed_members), encoding="utf-8"
    )

    wheel_members = set(
        (out_dir / "wheel-members.txt").read_text(encoding="utf-8").splitlines()
    )
    missing = sorted(path for path in opened_members if path not in wheel_members)
    (out_dir / "package-missing-members.txt").write_text(
        "".join(path + "\n" for path in missing), encoding="utf-8"
    )
    has_constructions = any(path.startswith("verantyx/constructions/") for path in wheel_members)
    has_data = any(path.startswith("verantyx/data/") for path in wheel_members)
    passed = not missing and has_constructions and has_data
    result = {
        "verdict": "PASS" if passed else "FAIL",
        "opened_package_path_count": len(opened_members),
        "failed_package_path_count": len(failed_members),
        "missing_opened_wheel_member_count": len(missing),
        "missing_opened_wheel_members": missing,
        "constructions_present": has_constructions,
        "data_present": has_data,
        "note": "wheel 内の Python module import は Python-level open tracer の対象外",
    }
    (out_dir / "p2-verification.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
