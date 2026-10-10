"""G3-k: is `grammar="off"` still the committed path?  Re-run ask_combined(grammar="off") on the cheapest recorded T10 questions and compare, source by source
and candidate by candidate in order (words and origins), the flat cross and the layers with what T10 recorded (replay.flat_src / layers_src of
../combined/replay.py).  The windows are not compared here (T10 has none; their default path is the same code as before this ticket and is covered by the
byte tests of tests/line3/test_grammar_wiring.py and by bank3's off run against the T11 records, summary.md).
usage: equiv_off.py --cache DIR [--n 8] [--ids a,b] [--max-secs 150]   (from the repository root; Pro python).  Exit 1 on any difference; writes results/equiv_off.txt."""
import argparse, json, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
COMB = os.path.join(os.path.dirname(HERE), "combined")
sys.path.insert(0, COMB)
from replay import flat_src, layers_src, ROOT   # noqa: E402
from verantyx.line3 import ask as A, combined as CB   # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--cache", required=True)
ap.add_argument("--n", type=int, default=8)
ap.add_argument("--ids", default="")
ap.add_argument("--max-secs", type=float, default=150.0)
a = ap.parse_args()
DATA = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")
t10 = {}
for l in open(os.path.join(ROOT, "experiments/line3/t10/results/ask_fulllead_fast_ordered-stop.jsonl"), encoding="utf-8"):
    r = json.loads(l)
    if "error" not in r:
        t10[r["id"]] = r


def cost(r): return (r["ms_layer0"] + r["on"]["seatsPath"]["ms"]) / 1000
def nonempty(r): return any(d["entries"] for d in r["layer0"].values()) or any(run["entries"] for d in r["on"]["seatsPath"]["tiers"].values() for run in d["runs"])


ids = a.ids.split(",") if a.ids else [i for i, r in sorted(t10.items(), key=lambda kv: cost(kv[1])) if nonempty(r) and cost(r) <= a.max_secs][:a.n]
idx = A.Index.from_jsonl(DATA, os.path.expanduser(a.cache), A.DEFAULT_LEVEL, A.TIERS, group_insert="ordered", order="forward")
LOG = ["equiv_off fast: %d questions: %s" % (len(ids), " ".join(ids))]
bad = 0
for i in ids:
    q = t10[i]["question"]
    t1 = time.time()
    live = CB.ask_combined(idx, q, effort="fast", grammar="off", window_evidence="plain", slide_members="representative")
    secs = time.time() - t1
    rep = {"flat": flat_src(t10[i]), "layers": layers_src(t10[i])}
    problems = []
    for ls in live.sources:
        if ls.name not in rep:
            continue
        lw = [(c.origin, tuple(c.words)) for c in ls.cands]
        rw = [(c.origin, tuple(c.words)) for c in rep[ls.name].cands]
        if lw != rw:
            problems.append("source %s: live %d candidates, T10 %d; first difference %s" % (ls.name, len(lw), len(rw), next(((x, y) for x, y in zip(lw, rw) if x != y), "length")))
    bad += bool(problems)
    LOG.append("%s %s: flat %d layers %d candidates, live %.0fs (T10 recorded %.0fs) %s" % (
        i, "SAME" if not problems else "DIFFERENT", len(live.sources[0].cands), len(live.sources[1].cands), secs, cost(t10[i]), "; ".join(problems)))
    print(LOG[-1], flush=True)
LOG.append("%d of %d questions identical" % (len(ids) - bad, len(ids)))
print(LOG[-1])
os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
open(os.path.join(HERE, "results", "equiv_off.txt"), "w", encoding="utf-8").write("\n".join(LOG) + "\n")
sys.exit(1 if bad else 0)
