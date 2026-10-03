"""Which units of the self-made explanations the reader could not read, by explanation and by the reader's own reason (the input to the
reader's side, W1-a4).  Runs the real reader in-process and writes artifacts/w2-h2/reader_gaps.json and reader_gaps.md.

    python tests/routing_from_text/reader_gaps.py
"""
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
DATA = os.path.join(ROOT, "tests", "routing_from_text", "data")
OUT = os.path.join(ROOT, "artifacts", "w2-h2")


def main():
    from verantyx import routing_from_text as rt
    report = {"explanations": {}, "unread_reasons_all": {}, "units_all": {"units": 0, "by_status": {}}}
    all_reasons, all_status = Counter(), Counter()
    examples = {}
    for directory in ("explanations", "explanations_reader_shaped"):
        for name in sorted(os.listdir(os.path.join(DATA, directory))):
            if not name.endswith(".md"):
                continue
            text = open(os.path.join(DATA, directory, name), encoding="utf-8").read()
            explained = rt.explain(text, os.path.join(directory, name))
            units = explained.extraction.units
            status, reasons = Counter(u.status for u in units), Counter()
            for unit in units:
                if unit.status != "MAPPED" and unit.status != "COMPARISON_ONLY":
                    first = unit.reasons[0].split(":")[0] if unit.reasons else "NO_REASON"
                    reasons[f"{unit.status}/{first}"] += 1
                    examples.setdefault(f"{unit.status}/{first}", unit.witness)
            report["explanations"][name[:-3]] = {"units": len(units), "by_status": {s: status.get(s, 0) for s in rt.UNIT_STATUSES},
                                                 "unread_reasons": dict(sorted(reasons.items()))}
            all_reasons.update(reasons)
            all_status.update(status)
    report["unread_reasons_all"] = dict(sorted(all_reasons.items(), key=lambda kv: (-kv[1], kv[0])))
    report["units_all"] = {"units": sum(all_status.values()), "by_status": {s: all_status.get(s, 0) for s in rt.UNIT_STATUSES}}
    report["examples"] = {k: examples[k] for k in sorted(examples)}
    os.makedirs(OUT, exist_ok=True)
    with open(os.path.join(OUT, "reader_gaps.json"), "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    lines = ["# 読めなかった単位（読解器の側への入力）", "", "出典: `tests/routing_from_text/reader_gaps.py` の出力（`reader_gaps.json`）。単位は `segment` の切り方による。", ""]
    for name, entry in report["explanations"].items():
        lines.append(f"- {name}: {entry['units']} 単位。" + " ".join(f"{k} {v}" for k, v in entry["by_status"].items() if v))
        for reason, count in entry["unread_reasons"].items():
            lines.append(f"  - {reason}: {count}")
    lines += ["", "## 理由別の合計と例", ""]
    for reason, count in report["unread_reasons_all"].items():
        lines.append(f"- {reason}: {count}（例: {report['examples'][reason]}）")
    with open(os.path.join(OUT, "reader_gaps.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    print(json.dumps(report["units_all"], ensure_ascii=False))
    print(json.dumps(report["unread_reasons_all"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
