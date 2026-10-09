"""F1c measurement: build the crosses of one corpus/tier at a budget level with group_insert="ordered", on_collapse="skip".
usage: build.py DATA TIER [LEVEL=mid] [WORKERS=2] [LIMIT=0] [VERIFY=0] [SEEDS.json] -> raw/<corpus>_<TIER>_skip_<LEVEL>.jsonl
Copy of experiments/line3/f1/build.py (f1/ is not modified) with on_collapse="skip".
Shortcut (exact, tested in tests/line3/test_placement_skip.py::test_skip_equals_stop_when_nothing_collapses): a cross of the
ordered+stop build (f1/raw, same code path) that EXHAUSTED never collapsed, so skip builds the very same cross; its row is copied
(reused=true, same secs) and only the crosses that stopped on budget are rebuilt.  VERIFY=N rebuilds N reused crosses too and
checks they are identical (units, size, class_size) with no skipped member.
Times of rebuilt crosses are process CPU time (process_time) on the Air (reused rows keep the Pro wall secs of f1). A rebuilt cross also re-times the stop build on the same machine (stop_secs_here) so that CPU ratios are same-machine.
One line per seed: as f1 + n_skipped, skipped [[share, member, reason]], first_stop_size (size of the stop build), reused."""
import json, os, sys, time, multiprocessing as mp
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from verantyx.line3 import placement as pl            # noqa: E402
from verantyx.line3.space import build_space, load_jsonl   # noqa: E402

DATA, TIER = sys.argv[1], sys.argv[2]
LEVEL = sys.argv[3] if len(sys.argv) > 3 else "mid"
WORKERS = int(sys.argv[4]) if len(sys.argv) > 4 else 2
LIMIT = int(sys.argv[5]) if len(sys.argv) > 5 else 0
VERIFY = int(sys.argv[6]) if len(sys.argv) > 6 else 0
SEEDS = sys.argv[7] if len(sys.argv) > 7 else ""        # json list of seeds: only these (name suffix _reach); see reach_seeds.py
G = {}


def row(p, s, dt):
    units = {s}
    for st in p.steps:
        if st.status == pl.STABLE:
            units.update(st.units)
    return {"seed": s, "size": p.size, "stop": p.stop, "left_in_group": p.left_in_group,
            "left_after": p.left_after, "secs": round(dt, 3), "L": p.L, "class_size": p.class_size,
            "expanded_size": p.expanded_size, "candidates": p.candidates,
            "broke_reason": p.broke_on.reason if p.broke_on else None,
            "units": sorted(units), "order_log": [[sh, list(us)] for sh, us in p.order_log],
            "n_skipped": len(p.skipped), "skipped": [[sh, u, why] for sh, u, why in p.skipped]}


def work(chunk):
    out = []
    for s in chunk:
        t0 = time.process_time()
        q = pl.build_cross(G["tier"], s, G["w"], budget=G["b"], group_insert="ordered")      # stop, re-timed on THIS machine
        t1 = time.process_time()
        p = pl.build_cross(G["tier"], s, G["w"], budget=G["b"], group_insert="ordered", on_collapse="skip")
        r = row(p, s, time.process_time() - t1)
        r["stop_secs_here"] = round(t1 - t0, 3)
        r["stop_same_as_f1"] = row(q, s, 0)["units"]         # the units of the stop build here (checked against f1/raw below)
        out.append(r)
    return out


if __name__ == "__main__":
    corpus = os.path.basename(DATA).split(".")[0]
    f1 = os.path.join(ROOT, "experiments/line3/f1/raw", "%s_%s_ordered_%s.jsonl" % (corpus, TIER, LEVEL))
    prev = {r["seed"]: r for r in (json.loads(l) for l in open(f1, encoding="utf-8")) if "seed" in r}
    space = build_space(load_jsonl(DATA))
    ts = space.tiers[TIER]
    G.update(tier=ts, w=pl.Weights(ts), b=pl.budget_level(LEVEL))
    units = ts.units()
    assert set(units) == set(prev), "f1 ordered raw does not cover this tier"
    if LIMIT:
        units = units[::max(1, len(units) // LIMIT)][:LIMIT]
    if SEEDS:
        keep = set(json.load(open(SEEDS, encoding="utf-8")))
        units = [u for u in units if u in keep]
    todo = [u for u in units if prev[u]["stop"] != "exhausted"]
    reused = [u for u in units if prev[u]["stop"] == "exhausted"]
    ver = reused[::max(1, len(reused) // VERIFY)][:VERIFY] if VERIFY else []
    chunks = [(todo + ver)[i:i + 4] for i in range(0, len(todo) + len(ver), 4)]
    t0 = time.time()
    with mp.get_context("fork").Pool(WORKERS) as pool:
        parts = []
        for part in pool.imap_unordered(work, chunks):
            parts.append(part)
            if len(parts) % 20 == 0:
                print("progress %d/%d chunks, %.0f s" % (len(parts), len(chunks), time.time() - t0), flush=True)
    new = {r["seed"]: r for p in parts for r in p}
    bad = [s for s in ver if (new[s]["units"], new[s]["size"], new[s]["class_size"], new[s]["n_skipped"]) !=
           (prev[s]["units"], prev[s]["size"], prev[s]["class_size"], 0)]
    rows = []
    for s in units:
        if s in reused:
            r = dict(prev[s]); r.update(n_skipped=0, skipped=[], reused=True)
        else:
            r = new[s]; r["reused"] = False
        if not r["reused"]:
            r["stop_here_units_equal_f1"] = r.pop("stop_same_as_f1") == prev[s]["units"]
        r["first_stop_size"] = prev[s]["size"]
        r["first_stop_units"] = prev[s]["units"]
        rows.append(r)
    wall = time.time() - t0
    name = "%s_%s_skip_%s%s" % (corpus, TIER, LEVEL, ("_lim%d" % LIMIT if LIMIT else "") + ("_reach" if SEEDS else ""))
    with open(os.path.join(HERE, "raw", name + ".jsonl"), "w", encoding="utf-8") as f:
        f.write(json.dumps({"_meta": {"data": DATA, "tier": TIER, "mode": "ordered+skip", "level": LEVEL, "workers": WORKERS,
                                       "wall_s": round(wall, 1), "cpu_s": round(sum(r["secs"] for r in rows), 1),
                                       "cpu_rebuilt_s": round(sum(r["secs"] for r in rows if not r["reused"]), 1),
                                       "seeds": len(rows), "rebuilt": len(todo), "reused": len(reused),
                                       "verified": len(ver), "verify_mismatch": bad}}) + "\n")
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    print(name, "seeds", len(rows), "rebuilt", len(todo), "verified", len(ver), "mismatch", bad, "wall %.1f s" % wall,
          "cpu(rebuilt) %.1f s" % sum(r["secs"] for r in rows if not r["reused"]))
