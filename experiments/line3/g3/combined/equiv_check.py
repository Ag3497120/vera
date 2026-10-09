"""G3-g: is the replay honest?  Re-run the LIVE combined list (combined.ask_combined: ask.ask + matryoshka.ask_layered stable-seats-path + both window
variants) on the cheapest recorded T10 questions and compare, entry by entry and in order, with what the replay builds from T10's record (flat cross =
layer0, layers = on.seatsPath) and from measure_windows.py's window records: the same words per candidate, the same origins, the same verdict.

usage: equiv_check.py PRESET --cache DIR_F1B --windows DIR_WINDOW_CACHE [--n 12] [--ids a,b,c] [--max-secs 120]   (from the repository root; Pro python)
The questions are the n with the smallest recorded flat + layers time that have at least one flat or layers entry (the others tell nothing); --ids names them.
Exit 1 on any difference.  The run writes results/equiv_<preset>.txt."""
import argparse, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from replay import flat_src, layers_src, win_src, ROOT   # noqa: E402
from verantyx.line3 import ask as A, combined as CB, slide_query as Q   # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("preset")
ap.add_argument("--cache", required=True)
ap.add_argument("--windows", required=True)
ap.add_argument("--n", type=int, default=12)
ap.add_argument("--ids", default="")
ap.add_argument("--max-secs", type=float, default=150.0, help="skip candidates whose recorded flat + layers time (T10, under load) exceeds this")
a = ap.parse_args()
P = a.preset
DATA = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")
t10 = {}
for l in open(os.path.join(ROOT, "experiments/line3/t10/results/ask_fulllead_%s_ordered-stop.jsonl" % P), encoding="utf-8"):
    r = json.loads(l)
    if "error" not in r:
        t10[r["id"]] = r
win = {}
for ev in ("plain", "window"):
    win[ev] = {}
    for l in open(os.path.join(HERE, "results", "win_%s_%s.jsonl" % (P, ev)), encoding="utf-8"):
        r = json.loads(l)
        if "error" not in r:
            win[ev][r["id"]] = r


def cost(r):
    return (r["ms_layer0"] + r["on"]["seatsPath"]["ms"]) / 1000


def nonempty(r):
    return any(d["entries"] for d in r["layer0"].values()) or any(run["entries"] for d in r["on"]["seatsPath"]["tiers"].values() for run in d["runs"])


ids = a.ids.split(",") if a.ids else [i for i, r in sorted(t10.items(), key=lambda kv: cost(kv[1])) if nonempty(r) and cost(r) <= a.max_secs][:a.n]
t0 = time.time()
idx = A.Index.from_jsonl(DATA, os.path.expanduser(a.cache), A.DEFAULT_LEVEL, A.TIERS, group_insert="ordered", order="forward")
short = {t: (len(idx.stores[t]._loaded), len(idx.space.tiers[t].units())) for t in idx.tiers}
assert all(x == y for x, y in short.values()), short
wi = Q.WindowIndex.from_jsonl(DATA, os.path.expanduser(a.windows), build=False)
LOG = ["equiv_check %s: index load %.0fs, %d questions: %s" % (P, time.time() - t0, len(ids), " ".join(ids))]
bad = 0
for i in ids:
    q = t10[i]["question"]
    t1 = time.time()
    live = CB.ask_combined(idx, q, effort=P, windows=wi, trace=True)
    secs = time.time() - t1
    srcs = [flat_src(t10[i]), layers_src(t10[i]), win_src(win["plain"][i], "plain"), win_src(win["window"][i], "window")]
    rep = CB.combine(q, srcs)
    problems = []
    for ls, rs in zip(live.sources, rep.sources):
        lw = [(c.origin, tuple(c.words)) for c in ls.cands]
        rw = [(c.origin, tuple(c.words)) for c in rs.cands]
        if lw != rw:
            problems.append("source %s: live %d candidates, replay %d; first difference %s" % (
                ls.name, len(lw), len(rw), next(((x, y) for x, y in zip(lw, rw) if x != y), "length")))
    lk = [(e.words, e.origins) for e in live.entries]
    rk = [(e.words, e.origins) for e in rep.entries]
    if lk != rk:
        problems.append("combined list differs (live %d entries, replay %d)" % (len(lk), len(rk)))
    if live.verdict != rep.verdict:
        problems.append("verdict live %s replay %s" % (live.verdict, rep.verdict))
    bad += bool(problems)
    LOG.append("%s %s: %d entries (%d candidates), verdict %s, live %.0fs (T10 recorded %.0fs) %s" % (
        i, "SAME" if not problems else "DIFFERENT", live.listed, live.listed_before_merge, live.verdict, secs, cost(t10[i]), "; ".join(problems)))
    print(LOG[-1], flush=True)
LOG.append("%d of %d questions identical" % (len(ids) - bad, len(ids)))
print(LOG[-1])
open(os.path.join(HERE, "results", "equiv_%s.txt" % P), "w", encoding="utf-8").write("\n".join(LOG) + "\n")
sys.exit(1 if bad else 0)
