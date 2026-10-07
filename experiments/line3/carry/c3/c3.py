"""C3 measurement: the full tower (verantyx.line3.carry.CarryTower) on S300, stream order = data file order (L-321).
usage: c3.py TIER LEVEL [N] [OUTJSON] [--verify] [--replay]   (run from the repo root, PYTHONPATH=.)
Reports: levels, units per level, packs copied / woken / never woken (per (unit, pack) pair), activation_deferred,
sentences split, time, the P-1 frontier coverage check after EVERY sentence, and the ledger-only replay check (O-2)."""
import json, sys, time
from verantyx.line3 import space as sp, placement as pl, carry as C
args = [a for a in sys.argv[1:] if not a.startswith("--")]
verify, replay = "--verify" in sys.argv, "--replay" in sys.argv
tier, lv = args[0], args[1]
N = int(args[2]) if len(args) > 2 else 300
out = args[3] if len(args) > 3 else None
rows = [json.loads(l) for l in open('experiments/line3/data/S300.jsonl', encoding='utf-8')][:N]
budget = pl.budget_level(lv)
ts = sp.build_space(rows).tiers[tier]
n = len(rows)
sids = list(range(n))
fed, cov_bad = [], []
def check(tw, s):
    fed.extend((s, o.pos, o.unit) for o in C.occurrences_of(ts, s))
    cov = tw.covered_occurrences()
    if len(cov) != len(set(cov)) or sorted(cov) != sorted(fed):
        cov_bad.append(s)
t_all = time.process_time()
tw = C.build_tower(tier, ts, sids, budget, unit_filter="default", clock=time.process_time, after_sentence=check)
total = time.process_time() - t_all
led = tw.ledger
ev = led.events()
kinds = {}
for e in ev: kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
copied = sum(len(v) for v in tw.carry.values())
woken_pairs = sum(len(a["activated"]) for a in ev if a["kind"] == "admit")
# woken pairs net of rollbacks: count from the unit's final elements
final_woken = sum(1 for b, _ in tw.units() for e in b.space.elements if e.origin == C.ORIGIN_INHERITED)
distinct_woken = sorted({e.id for b, _ in tw.units() for e in b.space.elements if e.origin == C.ORIGIN_INHERITED})
lvl = {}
for b, st in tw.units():
    d = lvl.setdefault(b.level, {"units": 0, "elems": [], "sents": [], "carry": [], "woken": []})
    d["units"] += 1
    d["elems"].append(b.n_elements); d["sents"].append(b.space.N)
    d["carry"].append(len(tw.carry[b.unit]))
    d["woken"].append(sum(1 for e in b.space.elements if e.origin == C.ORIGIN_INHERITED))
def stat(v):
    v = sorted(v); return {"min": v[0], "med": v[len(v) // 2], "max": v[-1], "sum": sum(v)}
levels = {str(k): {"units": d["units"], "elements": stat(d["elems"]), "sentences": stat(d["sents"]),
                   "carry": stat(d["carry"]), "woken": stat(d["woken"])} for k, d in sorted(lvl.items())}
res = {"mode": "c3", "tier": tier, "level": lv, "n": n, "levels": len(lvl), "units_per_level": tw.level_sizes(),
       "per_level": levels, "packs": len(tw.packs), "copied_pairs": copied, "woken_pairs": final_woken,
       "never_woken_pairs": copied - final_woken, "distinct_packs_woken": len(distinct_woken),
       "packs_never_woken_anywhere": len(tw.packs) - len(distinct_woken),
       "admit_activated_events_incl_rolled_back": woken_pairs,
       "activation_deferred": kinds.get("activation_deferred", 0),
       "sentences_split": len(set(tw.split_sids)), "split_events": len(tw.split_sids),
       "events": len(led), "event_kinds": kinds, "ledger_sha256": led.sha256(), "tower_sha256": tw.sha256(),
       "frontier_coverage_failed_after_sentences": cov_bad, "frontier_size_final": len(tw.frontier(0)),
       "total_secs_cpu": round(total, 1),
       "upper_attempt_secs": {str(k): round(v, 1) for k, v in tw.upper_attempt_secs.items()}}
ev0 = sorted(x for _, x in tw.event_secs)
res.update(level0_admit_secs_mean=sum(ev0) / len(ev0), level0_admits=len(ev0),
           level0_admit_secs_sum=round(sum(ev0), 1))
res["ledger_mismatches"] = C.ledger_mismatches(tw)
if replay:
    t0 = time.process_time()
    tw2 = C.replay_tower(led.to_bytes(), ts, tier, sids, budget)
    res["replay_identical"] = tw2.to_bytes() == tw.to_bytes()
    res["replay_secs_cpu"] = round(time.process_time() - t0, 1)
if verify:
    bad, tested, vsecs = [], 0, 0.0
    for b, st in tw.units():
        t0 = time.process_time(); r = b.verify(); vsecs += time.process_time() - t0
        tested += 1
        if not r.is_stable_class or r.size != len(b.state): bad.append(b.unit)
    res.update(verified=tested, verify_failed=bad, verify_secs=round(vsecs, 1))
if out: json.dump(res, open(out, "w"), ensure_ascii=False)
print(json.dumps({k: v for k, v in res.items() if k not in ("per_level",)}, ensure_ascii=False))
