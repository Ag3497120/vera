"""K415/K416: score x5_tiers.jsonl and group by `confidence_tiers.agree`.
Correct: an answerable question (expect = {"verdict":"ANSWER","values":[...]}) is correct when the outcome is an ANSWER outcome and the structured value (vera.reading.filler, else the content)
contains every expected value and nothing else; an unanswerable one (expect = "ABSTAIN") is correct when the outcome is not an ANSWER outcome. Any other ANSWER outcome is wrong; a non-ANSWER outcome
to an answerable question is an abstention (not wrong).
usage: score_tiers.py x5_tiers.jsonl out.json   (exit 0 iff no wrong answer)"""
import collections
import json
import sys

ANSWERS = ("ANSWER_HUMAN_BASIS", "ANSWER_FORM_FROM_GENERATED", "REFERENCE_GENERATED")


def classify(r):
    v = r["vera"]
    oc = (v.get("outcome") or {}).get("outcome")
    exp = r["expect"]
    if oc in ANSWERS:
        filler = (v.get("reading") or {}).get("filler")
        got = [filler] if filler is not None else None
        if exp != "ABSTAIN":
            if got is not None:
                ok = sorted(got) == sorted(exp["values"])
            else:
                ok = all(x in r["content"] for x in exp["values"])
            return ("correct" if ok else "wrong"), oc
        return "wrong", oc
    return ("correct_abstain" if exp == "ABSTAIN" else "abstained"), oc


def main(path, out):
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    per = []
    for r in rows:
        k, oc = classify(r)
        ct = r["vera"]["confidence_tiers"]
        per.append({"id": r["id"], "set": r["set"], "kind": k, "outcome": oc, "agree": ct["agree"], "answered": ct.get("answered"), "counted": ct["counted"], "shown_tier": ct["shown_tier"], "conflict": ct["conflict"],
                    "statuses": {t["name"]: t["status"] for t in ct["tiers"]}, "llm_called": r["vera"]["llm"]["called"]})
    def table(key):
        g = collections.defaultdict(collections.Counter)
        for p in per:
            g[p[key]][p["kind"]] += 1
        rows = []
        for k in sorted(g):
            c = g[k]
            n = sum(c.values())
            good = c["correct"] + c["correct_abstain"]
            rows.append({key: k, "questions": n, "correct": c["correct"], "correct_abstain": c["correct_abstain"], "abstained_on_answerable": c["abstained"], "wrong": c["wrong"],
                         "right_per_question": "%d/%d" % (good, n)})
        return rows
    by_agree = table("agree")
    rates = [(t["agree"], (t["correct"] + t["correct_abstain"]) / t["questions"]) for t in by_agree]
    monotone = all(b[1] >= a[1] for a, b in zip(rates, rates[1:]))
    # answers only: of the questions whose shown answer is an ANSWER outcome, how many were right (the rate of right answers by `agree`)
    ans = collections.defaultdict(collections.Counter)
    for p in per:
        if p["outcome"] in ANSWERS:
            ans[p["agree"]][p["kind"]] += 1
    shown_answers = [{"agree": k, "answers": sum(c.values()), "correct": c["correct"], "wrong": c["wrong"]} for k, c in sorted(ans.items())]
    summary = {"questions": len(per), "wrong": sum(1 for p in per if p["kind"] == "wrong"), "correct": sum(1 for p in per if p["kind"] == "correct"),
               "correct_abstain": sum(1 for p in per if p["kind"] == "correct_abstain"), "abstained_on_answerable": sum(1 for p in per if p["kind"] == "abstained"),
               "by_agree": by_agree, "by_counted": table("counted"), "by_answered": table("answered"), "by_set": table("set"), "shown_answers_by_agree": shown_answers,
               "monotone_nondecreasing_by_agree": monotone, "monotone_note": "right = correct or correct_abstain over all questions of that agree value; ties between neighbouring values count as monotone; one value only is trivially monotone",
               "conflicts": sum(1 for p in per if p["conflict"]), "llm_called_any": any(p["llm_called"] for p in per), "per_question": per}
    json.dump(summary, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, sort_keys=True)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("per_question", "by_set", "by_counted")}, ensure_ascii=False))
    return 0 if summary["wrong"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
