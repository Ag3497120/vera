"""G3-f diagnostic: under evidence "window" how much of the trace (P-4) rests on a constructed pair sentence?  For the windows S1 fast reads (94
questions, members representative, budget 512/64), sum over the DISTINCT (question, window) answers the path words that close an edge and the ones whose edge only
a constructed pair sentence evidences (trace.constructed_edge_words), for evidence "window"; the same sum for "plain" (0 by construction).
usage: trace_share.py CACHE_ROOT [z_deep=slide] -> results/trace_share_<z_deep>.txt"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)
from verantyx.line3 import slide_flat as F    # noqa: E402
from verantyx.line3 import slide_query as Q   # noqa: E402

ZD = sys.argv[2] if len(sys.argv) > 2 else "slide"
wi = Q.WindowIndex.from_jsonl(os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl"), os.path.join(sys.argv[1], ZD), build=False, z_deep=ZD)
rows = [l.rstrip("\n").split("\t") for l in open(os.path.join(ROOT, "experiments/line3/bank2/bank2.tsv"), encoding="utf-8") if not l.startswith("#") and l.strip()]
rows = [r for r in rows if r[2] == "fulllead" and r[1] in ("intra2", "unans")]
out = []
for ev in ("plain", "window"):
    wins = edges = cons = 0
    for r in rows:
        a = F.ask_flat(wi, r[4], effort="fast", members="representative", labels=False, evidence=ev)
        seen = {}
        for e in a.entries:
            seen[e["window"]["n"]] = e["trace"]
        for t in seen.values():
            wins += 1; edges += t["edge_words"]; cons += t["constructed_edge_words"]
    out.append("evidence %s, z_deep %s: %d (question, window) answers with an entry; path words that close an edge (over the paths of all adopted states) %d; "
               "of those evidenced only by a constructed pair sentence %d" % (ev, ZD, wins, edges, cons))
txt = "\n".join(out)
print(txt)
open(os.path.join(HERE, "results", "trace_share_%s.txt" % ZD), "w", encoding="utf-8").write(txt + "\n")
