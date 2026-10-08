# compares artifacts/w2-c/r5/bank_r4_prev/{off,fake}/results.jsonl (the round-4 code) with artifacts/w2-c/bank/{off,fake}/results.jsonl
import json, os
root = "artifacts/w2-c"
def load(p):
    return {json.loads(l)["id"]: json.loads(l) for l in open(p, encoding="utf-8")}
def sig(r):
    o = r["observed"]; return (o["decision"], o["answer_option_index"], o["answer"], o["reason"], o["detail"])
lines, counts = [], {"ans2esc": 0, "esc2ans": 0, "valchg": 0, "reasonchg": 0}
for m in ("off", "fake"):
    a, b = load(f"{root}/r5/bank_r4_prev/{m}/results.jsonl"), load(f"{root}/bank/{m}/results.jsonl")
    ch = 0
    for i in sorted(a):
        x, y = sig(a[i]), sig(b[i])
        if x == y: continue
        ch += 1
        if x[0] == "answer" and y[0] == "escalate": k = "ans2esc"
        elif x[0] == "escalate" and y[0] == "answer": k = "esc2ans"
        elif x[0] == "answer": k = "valchg"
        else: k = "reasonchg"
        counts[k] += 1
        lines.append(f"{m} {i} {k} {x} -> {y}")
    lines.insert(0, f"# {m}: rows={len(a)} changed={ch}")
lines.insert(2, f"# counts (off+fake rows): {counts}")
open(f"{root}/r5/bank_changes.txt", "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("\n".join(lines))
