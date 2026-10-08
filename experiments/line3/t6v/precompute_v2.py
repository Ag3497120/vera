"""T6v: placements (one cross per unit, level mid) of the V2 space (function / question words are
not units) for one tier.  usage: precompute_v2.py COND TIER [LEVEL=mid] [WORKERS=8]"""
import multiprocessing as mp
import os
import pickle
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C                                              # noqa: E402
from verantyx.line3 import placement as pl                      # noqa: E402

cond, tn = sys.argv[1], sys.argv[2]
level = sys.argv[3] if len(sys.argv) > 3 else "mid"
workers = int(sys.argv[4]) if len(sys.argv) > 4 else 8
_T = _W = None


def _init():
    global _T, _W
    _T = C.space_for(cond, True).tiers[tn]
    _W = pl.Weights(_T)


def _work(seeds):
    b = pl.budget_level(level)
    out = []
    for s in seeds:
        t0 = time.time()
        out.append((s, pl.build_cross(_T, s, _W, budget=b), time.time() - t0))
    return out


if __name__ == "__main__":
    units = C.space_for(cond, True).tiers[tn].units()
    chunks = [units[i:i + 4] for i in range(0, len(units), 4)]
    t0 = time.time()
    res, secs = {}, {}
    with mp.Pool(workers, initializer=_init) as pool:
        for part in pool.imap_unordered(_work, chunks):
            for s, p, dt in part:
                res[s] = p
                secs[s] = dt
    with open(os.path.join(C.SCRATCH, "placements_V2_%s_%s_%s.pkl" % (cond, tn, level)), "wb") as f:
        pickle.dump({"cond": cond, "tier": tn, "level": level, "placements": res, "secs": secs}, f)
    print(cond, tn, level, "V2 space:", len(res), "seeds", round(time.time() - t0, 1), "s wall", round(sum(secs.values()), 1), "s cpu", flush=True)
