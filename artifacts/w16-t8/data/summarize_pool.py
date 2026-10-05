import json, os, collections
D = os.path.dirname(os.path.abspath(__file__))
def tsv(name):
    rows = [l.rstrip("\n").split("\t") for l in open(os.path.join(D, name), encoding="utf-8") if l.strip() and not l.startswith("#") and not l.startswith("sentence_id")]
    return rows
pools = {}
sent_status = {}
for i in (1, 2, 3):
    rows = tsv("candidate_pool_%d_base.tsv" % i)
    by = collections.defaultdict(list)
    for r in rows:
        if len(r) >= 3 and r[2] in ("READ", "ABSTAIN"):
            by[r[1]].append(r)
    st = {}
    for t, rs in by.items():
        if rs[0][2] == "READ": st[t] = "READ"
        elif any(len(r) > 9 and r[9] == "true" for r in rs): st[t] = "ABSTAIN_REACHABLE"
        else: st[t] = "ABSTAIN_UNREACHABLE"
    sent_status.update(st)
    c = collections.Counter(st.values())
    pools["candidate_pool_%d" % i] = {"sentences": len(st), **dict(c)}
targets = [json.loads(l) for l in open(os.path.join(D, "synthetic_40.jsonl"), encoding="utf-8") if '"target"' in l]
in_pool = [t["id"] for t in targets if t["text"] in sent_status]
fresh = [t["id"] for t in targets if t["text"] not in sent_status]
summary = {"pools": pools, "candidates_total": sum(p["sentences"] for p in pools.values()),
           "targets": len(targets), "targets_taken_from_pool": in_pool, "targets_composed_fresh_by_the_same_templates": fresh,
           "pool_status_of_targets_in_pool": {t: sent_status[next(x["text"] for x in targets if x["id"] == t)] for t in in_pool},
           "note": "candidate_pool_1 and _2 (100 sentences) were explored before the preregistration timestamp and candidate_pool_3 (30 sentences, the verbs of the measure set) after it and before the data freeze (see docs/COARSE_PLACEMENT.md 12.21.6); every target abstained at the base (readable_before == 0 in t82_summary.json); the pool sentences NOT adopted are those that the base already reads (READ) and those no confirmation of this kind reaches (ABSTAIN_UNREACHABLE: the reader never asks the placement)"}
json.dump(summary, open(os.path.join(D, "candidate_pool_summary.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(summary, ensure_ascii=False, indent=1))
