"""C0 feasibility measurement (carry build order, idea 2). Measurement only; no product code.
usage: c0.py single|stream TIER LEVEL [N] [OUTJSON]
single: each sentence alone in an empty cross (settle?, capacity, time).
stream: word-by-word feed, closing only at sentence boundaries (OP-2 b), instability = budget exceeded (OP-3 a),
        copied packs get no seat unless a new sentence has one of their words (OP-1) -> no carry here (C0 ablation, carry empty).
"""
import json, sys, time
from verantyx.line3 import space as sp, placement as pl
mode, tier, lv = sys.argv[1], sys.argv[2], sys.argv[3]
N = int(sys.argv[4]) if len(sys.argv) > 4 else 300
out = sys.argv[5] if len(sys.argv) > 5 else None
rows = [json.loads(l) for l in open('experiments/line3/data/S300.jsonl', encoding='utf-8')][:N]
budget = pl.budget_level(lv)
full = sp.build_space(rows); ts = full.tiers[tier]
n = len(rows)
res = {"mode": mode, "tier": tier, "level": lv, "n": n}

if mode == "single":
    per = []
    for i in range(n):
        us = list(dict.fromkeys(ts.sentence_units[i]))
        if not us: per.append(None); continue
        t = time.process_time()
        one = sp.build_tier(tier, [rows[i]["sent"]])
        p = pl.build_cross(one, one.units()[0], budget=budget, quotient=False)
        per.append({"i": i, "units": len(us), "settled": p.stop != "budget", "cap": p.capacity, "secs": round(time.process_time() - t, 3)})
    res["per"] = [x for x in per if x]
    res["empty"] = sum(1 for x in per if x is None)
else:
    def tier_of(sids):
        return sp.TierSpace(tier, tuple(ts.sentence_units[s] if s in sids else () for s in range(n)),
                            {u: tuple(s for s in ts.postings[u] if s in sids) for u in set(x for s in sids for x in ts.sentence_units[s])})
    def add(state, placed, L, g, sids):
        """add group g (list of new units) to black; raises pl._Over"""
        w = pl.Weights(tier_of(sids)); work = pl._Work(budget)
        if state is None:
            st = pl._settle(w, [pl.canon((g[0],) + (None,) * 6, 1)], 1, work, budget); L2 = 1; rest = g[1:]; size = 1; base = st
        else:
            base = pl._settle(w, list(state), L, work, budget); L2 = L; rest = g; size = len(placed)
        if rest:
            L3 = pl.min_L(size + len(rest)); base = [pl.extend(x, L2, L3) if L3 > L2 else x for x in base]
            base = pl._settle(w, pl._insert_group(w, base, L3, rest, work, budget), L3, work, budget); L2 = L3
        return tuple(base), L2
    blacks = []; split_sents = set(); unsettled = 0; sent_secs = []
    cur = {"state": None, "placed": [], "L": 1, "sids": set()}
    def close():
        if cur["placed"]:
            blacks.append({"units": len(cur["placed"]), "sents": len(cur["sids"]), "L": cur["L"], "classes": len(cur["state"]) if cur["state"] else 0})
        cur.update(state=None, placed=[], L=1, sids=set())
    t_all = time.process_time()
    for s in range(n):
        ts0 = time.process_time()
        us = list(dict.fromkeys(ts.sentence_units[s]))
        if not us: sent_secs.append(0); continue
        snap = (cur["state"], list(cur["placed"]), cur["L"], set(cur["sids"]))
        def run(from_i):
            """feed us[from_i:] word by word into cur; on Over return index of failing word else None"""
            for k in range(from_i, len(us)):
                u = us[k]
                if u in cur["placed"]: continue
                try:
                    st, L = add(cur["state"], cur["placed"], cur["L"], [u], cur["sids"] | {s})
                except pl._Over:
                    return k
                cur.update(state=st, L=L, sids=cur["sids"] | {s}); cur["placed"] = cur["placed"] + [u]
            return None
        k = run(0)
        if k is not None and snap[1]:
            # OP-2 b: roll back to before this sentence, close the black, retry whole sentence in an empty black
            cur.update(state=snap[0], placed=snap[1], L=snap[2], sids=snap[3]); close()
            k = run(0)
        while k is not None:
            # does not fit even in an empty black: split the sentence here
            split_sents.add(s)
            if not cur["placed"] or not any(True for _ in cur["placed"]):
                unsettled += 1; cur.update(state=None, placed=[], L=1, sids=set()); k = run(k + 1); continue
            close()
            k = run(k)
        sent_secs.append(time.process_time() - ts0)
    close()
    ss = sorted(sent_secs)
    res.update(blacks=blacks, split=sorted(split_sents), unsettled_words=unsettled, total_secs=round(time.process_time() - t_all, 1),
               sent_secs_mean=sum(sent_secs) / max(1, len(sent_secs)), sent_secs_p90=ss[int(.9 * len(ss))], sent_secs_max=ss[-1])
if out: json.dump(res, open(out, "w"))
print(json.dumps({k: v for k, v in res.items() if k not in ("per", "blacks")}))
