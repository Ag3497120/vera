"""C3b measurement: CarryTower with pack_overflow = close | defer on S300 (stream order = data file order).
usage: c3b.py TIER LEVEL RULE [N] [OUTJSON]   (from the repo root, PYTHONPATH=.)   RULE = close | defer
Same quantities as experiments/line3/carry/c3/c3.py, plus (counted by a spy around Black.admit):
  pack_collapses_nonempty   admissions into a NON-empty black that collapsed while woken packs were in the group
  alone_fits                ... of those, how many the occurrence/item alone (no packs) would have fitted
  closes_by_packs_only      such collapses that actually closed the black (close: all of them; defer: 0)
  deferred_empty / deferred_nonempty   activation_deferred events by the state of the black (L-357 vs L-401)
  centre_*                  blacks whose settled class has a centre that is a pack (level 0)
The spy re-runs the failed admission without the packs only to answer 'would it have fitted'; its time is
included in total_secs_cpu (the same overhead under both rules)."""
import json, sys, time
from verantyx.line3 import space as sp, placement as pl, carry as C
args = [a for a in sys.argv[1:] if not a.startswith("--")]
tier, lv, rule = args[0], args[1], args[2]
N = int(args[3]) if len(args) > 3 else 300
out = args[4] if len(args) > 4 else None
assert rule in C.PACK_OVERFLOW
rows = [json.loads(l) for l in open('experiments/line3/data/S300.jsonl', encoding='utf-8')][:N]
budget = pl.budget_level(lv)
ts = sp.build_space(rows).tiers[tier]
n = len(rows)
sids = list(range(n))

cnt = {"pack_collapses_nonempty": 0, "alone_fits": 0, "deferred_empty": 0, "deferred_nonempty": 0,
       "pack_collapses_nonempty_L0": 0, "alone_fits_L0": 0}
orig = C.Black.admit
def spy(self, occs, elements=()):
    elements, occs = tuple(elements), tuple(occs)
    try:
        return orig(self, occs, elements)
    except C.Collapse as c:
        woken = sum(e.origin == C.ORIGIN_INHERITED for e in elements)
        if woken and not c.reason.startswith("injected"):
            if self.is_empty:
                cnt["deferred_empty"] += 1
            else:
                cnt["pack_collapses_nonempty"] += 1
                fits = False
                try:
                    orig(self, occs, [e for e in elements if e.origin != C.ORIGIN_INHERITED]); fits = True
                except C.Collapse:
                    pass
                cnt["alone_fits"] += fits
                if self.level == 0:
                    cnt["pack_collapses_nonempty_L0"] += 1; cnt["alone_fits_L0"] += fits
        raise
C.Black.admit = spy

fed, cov_bad = [], []
def check(tw, s):
    fed.extend((s, o.pos, o.unit) for o in C.occurrences_of(ts, s))
    cov = tw.covered_occurrences()
    if len(cov) != len(set(cov)) or sorted(cov) != sorted(fed):
        cov_bad.append(s)
t_all = time.process_time()
tw = C.build_tower(tier, ts, sids, budget, unit_filter="default", clock=time.process_time, after_sentence=check,
                   pack_overflow=rule)
total = time.process_time() - t_all
C.Black.admit = orig
led = tw.ledger
ev = led.events()
kinds = {}
for e in ev: kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
copied = sum(len(v) for v in tw.carry.values())
final_woken = sum(1 for b, _ in tw.units() for e in b.space.elements if e.origin == C.ORIGIN_INHERITED)
distinct_woken = {e.id for b, _ in tw.units() for e in b.space.elements if e.origin == C.ORIGIN_INHERITED}
# deferrals in a non-empty black = all activation_deferred events minus those in an empty black (spy counted the empty ones)
cnt["deferred_nonempty"] = kinds.get("activation_deferred", 0) - cnt["deferred_empty"]
closes_by_packs = cnt["alone_fits"] if rule == "close" else 0
lvl = {}
cen = {"blacks": 0, "any_pack_centre": 0, "all_pack_centre": 0, "flats": 0, "pack_centre_flats": 0}
for b, st in tw.units():
    d = lvl.setdefault(b.level, {"units": 0, "elems": [], "sents": [], "carry": [], "woken": []})
    d["units"] += 1
    d["elems"].append(b.n_elements); d["sents"].append(b.space.N)
    d["carry"].append(len(tw.carry[b.unit]))
    d["woken"].append(sum(1 for e in b.space.elements if e.origin == C.ORIGIN_INHERITED))
    if b.level == 0 and st == "closed":
        cs = [f[0] for f in b.state]
        pk = [c for c in cs if c is not None and c[0] == "P" and c[1:2].isdigit() and ":" in c]
        cen["blacks"] += 1; cen["flats"] += len(cs); cen["pack_centre_flats"] += len(pk)
        cen["any_pack_centre"] += bool(pk); cen["all_pack_centre"] += (len(pk) == len(cs))
def stat(v):
    v = sorted(v); return {"min": v[0], "med": v[len(v) // 2], "max": v[-1], "sum": sum(v)}
levels = {str(k): {"units": d["units"], "elements": stat(d["elems"]), "sentences": stat(d["sents"]),
                   "carry": stat(d["carry"]), "woken": stat(d["woken"])} for k, d in sorted(lvl.items())}
res = {"mode": "c3b", "rule": rule, "tier": tier, "level": lv, "n": n, "levels": len(lvl), "units_per_level": tw.level_sizes(),
       "per_level": levels, "packs": len(tw.packs), "copied_pairs": copied, "woken_pairs": final_woken,
       "never_woken_pairs": copied - final_woken, "distinct_packs_woken": len(distinct_woken),
       "activation_deferred": kinds.get("activation_deferred", 0),
       "deferred_empty": cnt["deferred_empty"], "deferred_nonempty": cnt["deferred_nonempty"],
       "pack_collapses_nonempty": cnt["pack_collapses_nonempty"], "alone_fits": cnt["alone_fits"],
       "pack_collapses_nonempty_L0": cnt["pack_collapses_nonempty_L0"], "alone_fits_L0": cnt["alone_fits_L0"],
       "closes_by_packs_only": closes_by_packs,
       "rollbacks": kinds.get("rollback", 0), "closes": kinds.get("close", 0),
       "sentences_split": len(set(tw.split_sids)), "split_events": len(tw.split_sids),
       "centre_level0_closed": cen, "events": len(led), "event_kinds": kinds,
       "ledger_sha256": led.sha256(), "tower_sha256": tw.sha256(),
       "frontier_coverage_failed_after_sentences": cov_bad, "total_secs_cpu": round(total, 1),
       "ledger_mismatches": C.ledger_mismatches(tw)}
if out: json.dump(res, open(out, "w"), ensure_ascii=False)
print(json.dumps({k: v for k, v in res.items() if k not in ("per_level",)}, ensure_ascii=False))
