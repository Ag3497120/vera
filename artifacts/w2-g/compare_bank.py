# compares bank results of W2-c (artifacts/w2-c/bank/{off,fake}) with g4/before_* and g4/after_* per id
import json, os
root = "artifacts"
def load(p):
    return {json.loads(l)["id"]: json.loads(l) for l in open(p, encoding="utf-8")}
def sig(r):
    o = r["observed"]; return (o["decision"], o["answer_option_index"], o["answer"], o["reason"], o["detail"])
for m in ("off", "fake"):
    base = load(f"{root}/w2-c/bank/{m}/results.jsonl")
    for tag in ("before", "after"):
        p = f"{root}/w2-g/g4/{tag}_{m}/results.jsonl"
        if not os.path.exists(p):
            print(f"{m} {tag}: (not run)"); continue
        cur = load(p)
        diff = [i for i in sorted(base) if sig(base[i]) != sig(cur.get(i, {"observed": {"decision": None, "answer_option_index": None, "answer": None, "reason": None, "detail": None}}))]
        print(f"{m} vs W2-c saved ({tag}): rows={len(base)}/{len(cur)} differing ids={len(diff)} {diff[:5]}")
