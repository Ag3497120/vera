"""T5 helper: build every placement (one cross per unit) of one tier of one condition at one
budget level, in parallel, and pickle them (a cache; results do not depend on it, L-07).

usage: precompute.py COND TIER LEVEL [WORKERS]     (COND in S300 S3000)
"""
import multiprocessing as mp
import os
import pickle
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)
from verantyx.line3 import placement as pl                      # noqa: E402
from verantyx.line3.space import build_space, load_jsonl        # noqa: E402

SCRATCH = ("/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/"
           "d52dc51d-8cb5-4487-931c-cc143bce928f/scratchpad/line3/t5")
cond, tn, level = sys.argv[1], sys.argv[2], sys.argv[3]
workers = int(sys.argv[4]) if len(sys.argv) > 4 else 8
_T = None
_W = None


def _init():
    global _T, _W
    sp = build_space(load_jsonl(os.path.join(ROOT, "experiments/line3/data/%s.jsonl" % cond)))
    _T = sp.tiers[tn]
    _W = pl.Weights(_T)


def _work(seeds):
    b = pl.budget_level(level)
    out = []
    for s in seeds:
        t0 = time.time()
        out.append((s, pl.build_cross(_T, s, _W, budget=b), time.time() - t0))
    return out


if __name__ == "__main__":
    sp = build_space(load_jsonl(os.path.join(ROOT, "experiments/line3/data/%s.jsonl" % cond)))
    units = sp.tiers[tn].units()
    chunks = [units[i:i + 4] for i in range(0, len(units), 4)]
    t0 = time.time()
    res = {}
    secs = {}
    with mp.Pool(workers, initializer=_init) as pool:
        for part in pool.imap_unordered(_work, chunks):
            for s, p, dt in part:
                res[s] = p
                secs[s] = dt
    path = os.path.join(SCRATCH, "placements_%s_%s_%s.pkl" % (cond, tn, level))
    with open(path, "wb") as f:
        pickle.dump({"cond": cond, "tier": tn, "level": level, "placements": res, "secs": secs}, f)
    print(cond, tn, level, len(res), "seeds", round(time.time() - t0, 1), "s wall", round(sum(secs.values()), 1), "s cpu", flush=True)
