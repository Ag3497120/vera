"""Budget-capacity curve (T4c): run one budget level on one tier of S300.

usage: run_level.py TIER LEVEL [N_SEEDS]
Seeds: the same 240 evenly spaced seeds as T4b: units[(i * n) // 240], i = 0..239 (units() order).
If N_SEEDS < 240 the first N_SEEDS of an even 240-subsampling are NOT used; instead seeds are
re-spaced evenly: units[(i * n) // N_SEEDS] (stated in the output).
Writes results/<TIER>_<LEVEL>.jsonl (one line per seed) and a summary line at the end.
"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
from verantyx.line3 import placement as pl                      # noqa: E402
from verantyx.line3.space import build_space, load_jsonl        # noqa: E402

tn, level = sys.argv[1], sys.argv[2]
nseeds = int(sys.argv[3]) if len(sys.argv) > 3 else 240
sp = build_space(load_jsonl(os.path.join(ROOT, "experiments/line3/data/S300.jsonl")))
t = sp.tiers[tn]
us = t.units()
seeds = [us[(i * len(us)) // nseeds] for i in range(nseeds)]
budget = pl.budget_level(level)
w = pl.Weights(t)
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
os.makedirs(out, exist_ok=True)
path = os.path.join(out, "%s_%s%s.jsonl" % (tn, level, "" if nseeds == 240 else "_n%d" % nseeds))
t0 = time.time()
with open(path, "w", encoding="utf-8") as f:
    for s in seeds:
        a = time.time()
        p = pl.build_cross(t, s, w, budget=budget)
        rec = {"seed": s, "capacity": p.capacity, "stop": p.stop, "class_size": p.class_size,
               "candidates": p.candidates, "secs": round(time.time() - a, 3),
               "reason": p.broke_on.reason if p.broke_on else None,
               "steps": [[st.share, len(st.units), st.size_after, st.status, st.explored,
                          st.class_size] for st in p.steps]}
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
    f.write(json.dumps({"summary": True, "tier": tn, "level": level, "n_seeds": nseeds,
                        "total_secs": round(time.time() - t0, 1)}) + "\n")
