"""Compare before/after t6_1_synth.json per case and per fact. usage: synth_diff.py before.json after.json"""
import json, sys
b, a = (json.load(open(p)) for p in sys.argv[1:3])
def facts(c):
    out = {}
    for ex, e in c["extractors"].items():
        for cl in e["claims"]:
            for f in cl["facts"]:
                out[(ex, cl["claim_id"], f["fact"])] = (f["mark"], f["reason"])
    return out
ids = lambda d: [c.get("case") or c.get("id") for c in d["cases"]]
assert len(b["cases"]) == len(a["cases"]) == 40
changed, down, up, other = [], [], [], []
for cb, ca in zip(b["cases"], a["cases"]):
    cid = cb.get("case") or cb.get("id")
    fb, fa = facts(cb), facts(ca)
    assert fb.keys() == fa.keys(), cid
    same_claim_level = json.dumps(cb, sort_keys=True) == json.dumps(ca, sort_keys=True)
    if not same_claim_level:
        changed.append(cid)
    for k in fb:
        if fb[k] != fa[k]:
            row = (cid,) + k + fb[k] + fa[k]
            if fb[k][0] in ("RECORD", "MISMATCH") and fa[k] [0] == "TESTIMONY":
                down.append(row)
            elif fb[k][0] == "TESTIMONY" and fa[k][0] in ("RECORD", "MISMATCH"):
                up.append(row)
            else:
                other.append(row)
print("cases total: %d; cases whose output changed: %d -> %s" % (len(b["cases"]), len(changed), " ".join(changed)))
print("facts RECORD/MISMATCH -> TESTIMONY (case, extractor, claim, fact, before mark/reason, after mark/reason):")
for r in down: print("  ", r)
print("facts TESTIMONY -> RECORD/MISMATCH (must be 0): %d" % len(up))
for r in up: print("  ", r)
print("other mark changes: %d" % len(other))
for r in other: print("  ", r)
print("metrics before:", json.dumps(b["metrics"], ensure_ascii=False))
print("metrics after: ", json.dumps(a["metrics"], ensure_ascii=False))
