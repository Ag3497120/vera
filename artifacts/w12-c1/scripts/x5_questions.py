"""K414: the 50 questions of X5 -> inputs/x5_questions.jsonl. bicycle 30 + pottery 15 + 5 factual questions of W10-f01 sampled with random.Random(20261005).sample(sorted(id), 5).
Each row: {id, set, question, documents, expect}. W10-f01 `truth` -> `expect`: ONE -> {"verdict":"ANSWER","values":[filler]}, NONE -> "ABSTAIN" (K415).
usage: x5_questions.py <tree>"""
import json
import os
import random
import sys

W = sys.argv[1]
A = os.path.join(W, "artifacts/w12-c1")
rows = []
for name, doc in (("bicycle", "inputs/domain_bicycle.txt"), ("pottery", "inputs/domain_pottery.txt")):
    for line in open(os.path.join(A, "inputs/domain_%s_qa.jsonl" % name), encoding="utf-8"):
        if line.strip():
            q = json.loads(line)
            rows.append({"id": "%s:%s" % (name, q["id"]), "set": name, "question": q["question"], "documents": [doc], "expect": q["expect"]})
f01 = [json.loads(l) for l in open(os.path.join(W, "artifacts/w10-f01/data/questions.jsonl"), encoding="utf-8") if l.strip()]
fact = {r["id"]: r for r in f01 if r["request_kind"] == "factual"}
pick = random.Random(20261005).sample(sorted(fact), 5)
for i in pick:
    r = fact[i]
    t = r["truth"]
    exp = {"verdict": "ANSWER", "values": [t["filler"]]} if t["kind"] == "ONE" else "ABSTAIN"
    rows.append({"id": "f01:%s" % i, "set": "f01", "question": r["question"], "documents": ["inputs/docs_f01"], "expect": exp})
with open(os.path.join(A, "inputs/x5_questions.jsonl"), "w", encoding="utf-8") as fo:
    for r in rows:
        fo.write(json.dumps(r, ensure_ascii=False) + "\n")
print(len(rows), "questions; f01 picked:", pick)
