"""Merge two real-provider runs of the same 64 questions: BASE (the full run) and REPLACE (a re-run of a pre-declared id list).
The rows of REPLACE take the place of the rows of BASE with the same id; every other row is the BASE row unchanged.  The merged
G3 numbers are computed from the merged rows with the same judge/summarizer as run_map_bank (tests/conduct_ask/run_bank.py).
Usage: merge_r3.py <base dir> <replace dir> <subset file> <out dir> [<items.jsonl>]
The output directory gets results.jsonl, summary.json (with the input names, the replaced ids and the old and new verdict of each),
and the three G3 numbers are printed.  Nothing is judged by this script's own rule: judge() is run_bank's."""
import json, sys
from pathlib import Path

W = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(W / "tests" / "conduct_ask"))
import run_bank  # noqa: E402


def rows_of(d):
    return [json.loads(l) for l in (d / "results.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]


def main(argv):
    base_d, rep_d, subset, out_d = (Path(a) for a in argv[:4])
    items_p = Path(argv[4]) if len(argv) > 4 else W / "tests/conduct_ask/w2g2/items.jsonl"
    base, rep = rows_of(base_d), {r["id"]: r for r in rows_of(rep_d)}
    ids = [l.strip() for l in subset.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert set(rep) <= set(ids), ("replacement rows outside the declared subset", sorted(set(rep) - set(ids)))
    not_run = sorted(set(ids) - set(rep))
    items = {json.loads(l)["id"]: json.loads(l) for l in items_p.read_text(encoding="utf-8").splitlines() if l.strip()}
    merged, changes = [], []
    for r in base:
        n = rep.get(r["id"])
        if n is None:
            merged.append(r)
            continue
        merged.append(n)
        changes.append({"id": r["id"], "old": [r["verdict"], r["observed"]["decision"], r["observed"].get("reason"), r["observed"].get("detail")],
                        "new": [n["verdict"], n["observed"]["decision"], n["observed"].get("reason"), n["observed"].get("detail")]})
    # re-judge every merged row from its expectation and observation with run_bank.judge (never trust a stored verdict)
    fresh = []
    for r in merged:
        item = {"expect": {"decision": r["expect"]["decision"], "answer_option_index": r["expect"]["answer_option_index"], "answer": r["expect"]["answer"]},
                "options": r["expect"]["answer_option_index"] is not None, "w2c": r["w2c"]}
        verdict, reason_match = run_bank.judge(item, {"decision": r["observed"]["decision"], "answer_option_index": r["observed"]["answer_option_index"],
                                                      "answer": r["observed"]["answer"], "escalate_reason": r["observed"]["reason"]})
        fresh.append({**r, "verdict": verdict, "reason_match": reason_match})
    summ = run_bank.summarize(fresh)
    out_d.mkdir(parents=True, exist_ok=True)
    with (out_d / "results.jsonl").open("w", encoding="utf-8") as fh:
        for r in fresh:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    wrong = [r["id"] for r in fresh if r["verdict"] in ("false_answer", "wrong_answer")]
    summary = {k: summ[k] for k in ("total", "q1_wrong_count", "q1_rate", "correct", "over_escalate", "correct_escalate", "answer_expected", "q2_answer_rate", "escalate_expected",
                                    "escalate_correct", "escalate_correct_rate", "q2_by_category", "by_lang", "by_split")}
    summary.update({"false_or_wrong_ids": wrong, "inputs": {"base": str(base_d), "replace": str(rep_d), "subset": str(subset), "items": str(items_p)},
                    "replaced_ids": [c["id"] for c in changes], "declared_but_not_run": not_run, "changes": changes,
                    "note": "rows of `replace` stand in for the rows of `base` with the same id; all other rows are `base` unchanged"})
    (out_d / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("merged", len(fresh), "rows | replaced", len(changes), "| declared but not run", not_run)
    print("q1_wrong_count", summ["q1_wrong_count"], "q1_rate", summ["q1_rate"], "| q2_answer_rate", summ["q2_answer_rate"], f"({summ['answer_expected']} expected answers)",
          "| escalate_correct_rate", summ["escalate_correct_rate"], f"({summ['escalate_expected']} expected escalations)")
    for c in changes:
        print(" ", c["id"], c["old"], "->", c["new"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
