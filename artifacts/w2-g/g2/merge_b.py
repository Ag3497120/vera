"""W2-g2 (b): put the two re-runs of the second data set w2g2 (the 48 questions whose right action is to answer, then the 16 whose
right action is to hand up; protocol v2, effort low, codex with codex) together and compare them with the round 3 values over the same
questions.  Every row is judged again with run_bank.judge (a stored verdict is never trusted).

Usage: merge_b.py <answer run dir> <escalate run dir or -> <out dir>
Reads  artifacts/w2-g/live/w2g2/merged_r3b_codex_codex/results.jsonl  (round 3, the wording changed after the frozen data's result was seen: 27 / 48)
       artifacts/w2-g/live/w2g2/merged_r3a_codex_codex/results.jsonl  (round 3, the wording before that change, the pre-registered one: 21 / 48)
Writes <out dir>/results.jsonl and <out dir>/summary.json, and prints a table.  Questions that were not run (the budget ran out) are
left out of the v2 side AND of the round 3 side of the "same questions" columns; the full 64 / 48 columns are printed too."""
import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(W / "tests" / "conduct_ask"))
import run_bank  # noqa: E402


def rows_of(p):
    return [json.loads(ln) for ln in Path(p).read_text(encoding="utf-8").splitlines() if ln.strip()]


def rejudge(rows):
    out = []
    for r in rows:
        item = {"expect": {"decision": r["expect"]["decision"], "answer_option_index": r["expect"]["answer_option_index"],
                           "answer": r["expect"]["answer"]},
                "options": r["expect"]["answer_option_index"] is not None, "w2c": r["w2c"]}
        verdict, reason_match = run_bank.judge(item, {"decision": r["observed"]["decision"], "answer_option_index": r["observed"]["answer_option_index"],
                                                      "answer": r["observed"]["answer"], "escalate_reason": r["observed"]["reason"]})
        out.append({**r, "verdict": verdict, "reason_match": reason_match})
    return out


def line(name, rows):
    s = run_bank.summarize(rows)
    return {"name": name, "questions": s["total"], "wrong": s["q1_wrong_count"], "answered_correctly": s["correct"],
            "answer_expected": s["answer_expected"], "escalated_correctly": s["escalate_correct"], "escalate_expected": s["escalate_expected"],
            "q2_answer_rate": s["q2_answer_rate"], "escalate_correct_rate": s["escalate_correct_rate"]}


def main(argv):
    ans_dir, esc_dir, out_dir = argv[0], argv[1], Path(argv[2])
    v2 = rows_of(Path(ans_dir) / "results.jsonl")
    if esc_dir != "-" and (Path(esc_dir) / "results.jsonl").is_file():
        v2 += rows_of(Path(esc_dir) / "results.jsonl")
    v2 = rejudge(v2)
    r3b = rejudge(rows_of(W / "artifacts/w2-g/live/w2g2/merged_r3b_codex_codex/results.jsonl"))
    r3a = rejudge(rows_of(W / "artifacts/w2-g/live/w2g2/merged_r3a_codex_codex/results.jsonl"))
    ran = {r["id"] for r in v2}
    table = [line("v2 low (this round)", v2),
             line("round 3 wording b (after the result was seen), same questions", [r for r in r3b if r["id"] in ran]),
             line("round 3 wording a (pre-registered), same questions", [r for r in r3a if r["id"] in ran]),
             line("round 3 wording b, all 64", r3b), line("round 3 wording a, all 64", r3a)]
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / "results.jsonl").open("w", encoding="utf-8") as fh:
        for r in v2:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    not_run = sorted({r["id"] for r in r3b} - ran)
    per_q = [{"id": r["id"], "expect": r["expect"]["decision"], "v2": [r["verdict"], r["observed"]["decision"], r["observed"].get("reason"), r["observed"].get("detail")]}
             for r in v2]
    summary = {"inputs": {"answer_run": ans_dir, "escalate_run": esc_dir}, "table": table, "not_run": not_run, "per_question": per_q,
               "wrong_ids": [r["id"] for r in v2 if r["verdict"] in ("false_answer", "wrong_answer")]}
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("not run:", len(not_run))
    for t in table:
        print(f"{t['name']}: n={t['questions']} wrong={t['wrong']} answered_correctly={t['answered_correctly']}/{t['answer_expected']} "
              f"escalated_correctly={t['escalated_correctly']}/{t['escalate_expected']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
