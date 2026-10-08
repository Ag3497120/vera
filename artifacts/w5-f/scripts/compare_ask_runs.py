from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


def rows(path: Path) -> dict[str, dict]:
    result = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        output = json.loads(row["stdout"])
        result[row["id"]] = {
            "verdict": output.get("verdict"),
            "text": output.get("text"),
            "sources": [{key: source.get(key) for key in ("source", "line", "text")}
                        for source in output.get("sources", [])],
        }
    return result


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit("usage: compare_ask_runs.py <before.jsonl> <after.jsonl> <changed.tsv>")
    before, after = rows(Path(sys.argv[1])), rows(Path(sys.argv[2]))
    if set(before) != set(after):
        raise SystemExit(f"question ids differ: before={len(before)} after={len(after)}")
    changed = [(key, before[key], after[key]) for key in before if before[key] != after[key]]
    print(f"questions={len(after)} changed={len(changed)}")
    with Path(sys.argv[3]).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream, delimiter="\t")
        writer.writerow(("id", "before", "after"))
        for key, old, new in changed:
            writer.writerow((key, json.dumps(old, ensure_ascii=False, sort_keys=True),
                             json.dumps(new, ensure_ascii=False, sort_keys=True)))


if __name__ == "__main__":
    main()
