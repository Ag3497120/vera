"""F1 measurement: build the crosses of one corpus/tier at a budget level with group_insert whole|ordered|reverse.
usage: build.py DATA TIER MODE [LEVEL=mid] [WORKERS=4] [LIMIT=0] -> raw/<corpus>_<TIER>_<MODE>_<LEVEL>.jsonl
One line per seed: size, stop, left_in_group, left_after, secs, L, class_size, expanded_size, units (seed + units seated), order_log
(order_log: only the groups reached; the recorded insertion order)."""
import json, os, sys, time, multiprocessing as mp
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from verantyx.line3 import placement as pl            # noqa: E402
from verantyx.line3.space import build_space, load_jsonl   # noqa: E402

DATA, TIER, MODE = sys.argv[1], sys.argv[2], sys.argv[3]
LEVEL = sys.argv[4] if len(sys.argv) > 4 else "mid"
WORKERS = int(sys.argv[5]) if len(sys.argv) > 5 else 4
LIMIT = int(sys.argv[6]) if len(sys.argv) > 6 else 0
G = {}


def work(chunk):
    out = []
    for s in chunk:
        t0 = time.time()
        gi = "whole" if MODE == "whole" else "ordered"
        p = pl.build_cross(G["tier"], s, G["w"], budget=G["b"], group_insert=gi,
                           order="reverse" if MODE == "reverse" else "forward")
        dt = time.time() - t0
        units = {s}
        for st in p.steps:
            if st.status == pl.STABLE:
                units.update(st.units)
        out.append({"seed": s, "size": p.size, "stop": p.stop, "left_in_group": p.left_in_group,
                    "left_after": p.left_after, "secs": round(dt, 3), "L": p.L, "class_size": p.class_size,
                    "expanded_size": p.expanded_size, "candidates": p.candidates,
                    "broke_reason": p.broke_on.reason if p.broke_on else None,
                    "units": sorted(units), "order_log": [[sh, list(us)] for sh, us in p.order_log]})
    return out


if __name__ == "__main__":
    space = build_space(load_jsonl(DATA))
    ts = space.tiers[TIER]
    G.update(tier=ts, w=pl.Weights(ts), b=pl.budget_level(LEVEL))
    units = ts.units()
    if LIMIT:
        units = units[::max(1, len(units) // LIMIT)][:LIMIT]
    chunks = [units[i:i + 4] for i in range(0, len(units), 4)]
    t0 = time.time()
    with mp.get_context("fork").Pool(WORKERS) as pool:
        parts = list(pool.imap_unordered(work, chunks))
    rows = sorted((r for p in parts for r in p), key=lambda r: r["seed"])
    wall = time.time() - t0
    name = "%s_%s_%s_%s%s" % (os.path.basename(DATA).split(".")[0], TIER, MODE, LEVEL, "_lim%d" % LIMIT if LIMIT else "")
    with open(os.path.join(HERE, "raw", name + ".jsonl"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"_meta": {"data": DATA, "tier": TIER, "mode": MODE, "level": LEVEL, "workers": WORKERS,
                                       "wall_s": round(wall, 1), "cpu_s": round(sum(r["secs"] for r in rows), 1),
                                       "seeds": len(rows)}}) + "\n")
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    print(name, "seeds", len(rows), "wall %.1f s" % wall, "cpu %.1f s" % sum(r["secs"] for r in rows))
