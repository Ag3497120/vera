"""R5 scoring (registered in docs/COARSE_PLACEMENT.md section 12.19 before the data): `verdict == ANSWER` and sorted(values) == sorted(expect.values) -> correct; `verdict == ANSWER` otherwise (an ANSWER to a
question whose expect is ABSTAIN included) -> wrong; everything else -> abstained. Every verdict that came out is counted; a non-ANSWER with non-empty `values` is listed for a look.
usage: score_qa.py <run.jsonl>..."""
import collections
import json
import sys


def score(path):
    c = collections.Counter()
    verdicts = collections.Counter()
    wrong, check, per = [], [], {}
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        o, exp = r["out"], r["expect"]
        v = o.get("verdict")
        verdicts[v] += 1
        if v == "ANSWER":
            if exp != "ABSTAIN" and sorted(o.get("values") or []) == sorted(exp["values"]):
                k = "correct"
            else:
                k = "wrong"
                wrong.append({"id": r["id"], "question": r["question"], "expect": exp, "values": o.get("values")})
        else:
            k = "abstained"
            if o.get("values"):
                check.append({"id": r["id"], "verdict": v, "values": o.get("values")})
        c[k] += 1
        c["answerable_" + k if exp != "ABSTAIN" else "unanswerable_" + k] += 1
        per[r["id"]] = k
    return {"file": path, "questions": sum(c[k] for k in ("correct", "wrong", "abstained")), "correct": c["correct"], "wrong": c["wrong"], "abstained": c["abstained"],
            "answerable": {k: c["answerable_" + k] for k in ("correct", "wrong", "abstained")}, "unanswerable": {k: c["unanswerable_" + k] for k in ("correct", "wrong", "abstained")},
            "verdicts": dict(sorted(verdicts.items(), key=lambda x: str(x[0]))), "wrong_items": wrong, "to_check": check}, per


results = [score(p) for p in sys.argv[1:]]
for r, _ in results:
    print(json.dumps(r, ensure_ascii=False))
base = results[0][1] if results else {}
print("SUMMARY (questions %d)" % (results[0][0]["questions"] if results else 0))
for r, per in results:
    gained = sorted(i for i, k in per.items() if k == "correct" and base.get(i) != "correct")
    lost = sorted(i for i, k in per.items() if base.get(i) == "correct" and k != "correct")
    print("%s: correct %d wrong %d abstained %d | gained vs first %s lost %s" % (r["file"], r["correct"], r["wrong"], r["abstained"], gained, lost))
sys.exit(0 if all(r["wrong"] == 0 for r, _ in results) else 1)
