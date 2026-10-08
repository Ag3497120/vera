from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def main() -> None:
    if len(sys.argv) != 5:
        raise SystemExit("usage: compare_entry_dumps.py <none|r8> <before.jsonl> <after.jsonl> <changed.tsv>")
    mode, before_name, after_name, changed_name = sys.argv[1:]
    before, after = rows(Path(before_name)), rows(Path(after_name))
    if len(before) != len(after):
        raise SystemExit(f"row count differs: before={len(before)} after={len(after)}")
    changed = []
    counts = Counter()
    for old, new in zip(before, after):
        old_out, new_out = old["out"], new["out"]
        old_read, new_read = bool(old_out.get("readable")), bool(new_out.get("readable"))
        old_clauses, new_clauses = old_out.get("clauses", []), new_out.get("clauses", [])
        old_reasons = (old_out.get("abstain") or {}).get("reasons", [])
        new_reasons = (new_out.get("abstain") or {}).get("reasons", [])
        old_unsupported, new_unsupported = old_out.get("unsupported", []), new_out.get("unsupported", [])
        if canonical(old_out) == canonical(new_out):
            continue
        if old_read and not new_read:
            transition = "read_to_abstain"
        elif not old_read and new_read:
            transition = "abstain_to_read"
        elif old_read and new_read and canonical(old_clauses) != canonical(new_clauses):
            transition = "read_to_different_read"
        elif not old_read and not new_read and canonical(old_reasons) != canonical(new_reasons):
            transition = "abstain_reason_changed"
        else:
            transition = "other_output_changed"
        counts[transition] += 1
        changed.append({
            "text": old.get("text", ""),
            "source": old.get("source", ""),
            "transition": transition,
            "before_reasons": old_reasons,
            "after_reasons": new_reasons,
            "before_unsupported": old_unsupported,
            "after_unsupported": new_unsupported,
            "before_clauses": old_clauses,
            "after_clauses": new_clauses,
        })
    readable_before = sum(bool(row["out"].get("readable")) for row in before)
    readable_after = sum(bool(row["out"].get("readable")) for row in after)
    print(f"mode={mode} inputs={len(before)} readable_before={readable_before} readable_after={readable_after} "
          f"changed={len(changed)} transitions={json.dumps(dict(sorted(counts.items())), ensure_ascii=False, sort_keys=True)}")
    with Path(changed_name).open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["text", "source", "transition", "before_reasons", "after_reasons",
                                                    "before_unsupported", "after_unsupported", "before_clauses",
                                                    "after_clauses"], delimiter="\t")
        writer.writeheader()
        for row in changed:
            writer.writerow({key: value if isinstance(value, str) else canonical(value) for key, value in row.items()})


if __name__ == "__main__":
    main()
