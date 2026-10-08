"""Keep this run's health evidence and restore pre-existing artifact bytes."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    target = HERE / "check_artifact_restoration.json"
    if target.exists():
        raise SystemExit("already archived/restored")
    backup = Path((HERE / "check_backup_path.txt").read_text().strip())
    after = HERE / "checks_after"
    # Copy every per-file guard result, including those identical to the old run.
    for src in sorted((ROOT / "experiments/guard").glob("results_confirm*.json")):
        dst = after / src.relative_to(ROOT)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    shutil.copy2(ROOT / "experiments/guard/verify_all_result.json", HERE / "guard_result.json")
    restored = []
    for name in (backup / "files.txt").read_text().splitlines():
        old, current = backup / name, ROOT / name
        if not old.is_file():
            continue
        if not current.is_file() or current.read_bytes() != old.read_bytes():
            record = {"path": name, "before_sha256": digest(old),
                      "after_sha256": digest(current) if current.is_file() else None}
            if current.is_file():
                dst = after / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(current, dst)
            shutil.copy2(old, current)
            assert current.read_bytes() == old.read_bytes()
            restored.append(record)
    target.write_text(json.dumps({"restored": restored,
                                 "preexisting_paths_py_preserved":
                                 (ROOT / "verantyx/paths.py").read_bytes() ==
                                 (backup / "verantyx/paths.py").read_bytes()},
                                ensure_ascii=False, indent=2) + "\n")
    print("Archived health evidence; restored", len(restored), "artifact files")


if __name__ == "__main__":
    main()
