"""T6ab (4): grade a simulated user's choices on the S300 RUN lists and record them through the read-out's user-choice intake.
usage: grade_user.py CHOICES.json [--records choices_records.jsonl] [--out results/user_grade.md]
CHOICES.json: {key: entry index (0-based, as displayed) | "none"}; key = qid (a05 ...) or the neutral number (Q01 ...; blind_map.json).
Rule B: chosen entry's words contain a gold string (casefold) -> correct; else wrong; "none" -> abstain; a chosen entry of an
unanswerable question (no gold) -> wrong.  A list without a choice = abstain.  Non-list questions keep their T6z grade (rule B, list = abstention).
Each chosen entry is passed through readout.choose_item (-> AnswerAdoption.memory_record) and written as one JSON line
{"qid", "choice_index", "grade", "record"} to the records file (for T11); "none" and unanswered lists produce no record."""
import argparse
import json
import os
import sys
from common import *      # noqa
import grade as G

ap = argparse.ArgumentParser()
ap.add_argument("choices")
ap.add_argument("--records", default=os.path.join(HERE, "choices_records.jsonl"))
ap.add_argument("--out", default=os.path.join(HERE, "results", "user_grade.md"))
args = ap.parse_args()
raw = json.load(open(args.choices, encoding="utf-8"))
nmap = json.load(open(os.path.join(HERE, "blind_map.json")))
back = {v: k for k, v in nmap.items()}
choices = {}
for k, v in raw.items():
    q = back.get(k, k)
    if q in choices:
        sys.exit("duplicate choice for %s" % q)
    choices[q] = v
rows = {r["id"]: r for r in stored_rows()}
lists = {q for q, r in rows.items() if r["answer"].get("verdict") == "CHOICE"}
unknown = set(choices) - lists
if unknown:
    sys.exit("not a list question: %s" % sorted(unknown))
for q, v in choices.items():
    if v != "none" and (isinstance(v, bool) or not isinstance(v, int) or not 0 <= v < len(rows[q]["answer"]["entries"])):
        sys.exit("bad choice for %s: %r" % (q, v))
t, facts = tier_and_facts()
gl = lambda r: [x.casefold() for x in r["gold"].split("|") if x]
graded, recs, detail = [], [], []
for q, r in rows.items():
    v = r["answer"].get("verdict")
    if q not in lists:
        txt = "\n".join(r["answer"]["entries"][0]["words"]) if v == "ANSWER" else ""
        g, hit, _ = G.grade(G.classify(v), r["core"], txt, r["subject"], r["gold"])
        graded.append(dict(qid=q, kind=r["kind"], cls=G.classify(v), grade=g, gold_hit=hit))
        continue
    c = choices.get(q, "none")
    if c == "none":
        g, cls, hit = "abstain", "ABSTAIN", False
        detail.append((q, "none" if q in choices else "(no choice)", "abstain"))
    else:
        words = r["answer"]["entries"][c]["words"]
        hit = any(x in w.casefold() for x in gl(r) for w in words)
        g, cls = ("correct" if hit else "wrong"), "ANSWER"            # no gold (unanswerable): hit is False -> wrong
        detail.append((q, c, g))
        ans = readout_default(t, facts, r)
        assert sha(ans.answer_obj()) == sha(r["answer"]), q          # the intake works on the stored default read-out
        rec = ro.choose_item(ans, c).memory_record()
        recs.append({"qid": q, "choice_index": c, "grade": g, "record": rec})
    graded.append(dict(qid=q, kind=r["kind"], cls=cls, grade=g, gold_hit=hit))
tt = G.tally(graded)
with open(args.records, "w", encoding="utf-8") as f:
    for x in recs:
        f.write(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n")
L = ["## user grade (%s)" % os.path.basename(args.choices), "",
     "| system | correct/wrong/abstain (60 answerable) | unanswerable answered (fict+attr) |", "|---|---|---|",
     "| T0 legacy a1 | 45/7/8 | 11 |", "| T6z | 18/3/39 | 4 |",
     "| **this user** | %d/%d/%d | %d |" % (tt["correct"], tt["wrong"], tt["abstain"], tt["answered_unanswerable"]), "",
     "| id | choice | grade |", "|---|---|---|"] + ["| %s | %s | %s |" % d for d in detail]
open(args.out, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
print("records:", len(recs), "->", args.records)
