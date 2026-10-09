"""G3-f diagnostic: in the windows S1 fast actually reads (intra2 + unans of bank2 fulllead, read order qcount_first, 4 windows), how many of the
EDGES of the window crosses are evidenced for the flat reader?  The flat reader (cycle.Reader) reads n_pair(o, i), the corpus same-sentence count of the
two units, on every arm; the per-axis reader reads n_a of the axis of the arm the edge lies on (x: the same n_pair, z: the slide count).  For every edge
with both ends seated (every strictly stable member, or the representatives only): per axis of its arm, edges / evidenced for the per-axis reader
(n_a > 0) / evidenced for the flat reader (n_pair > 0) / evidenced for the per-axis reader only.
usage: edge_evidence.py CACHE_ROOT [z_deep=slide] [members=representative]  -> results/edge_evidence_<z_deep>_<members>.txt (+ prints)"""
import os, sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)
from verantyx.line3 import geometry as geo          # noqa: E402
from verantyx.line3 import slide_query as Q         # noqa: E402
from verantyx.line3 import slide_ratios as SR       # noqa: E402

CACHE = sys.argv[1]
ZD = sys.argv[2] if len(sys.argv) > 2 else "slide"
MEM = sys.argv[3] if len(sys.argv) > 3 else "representative"
BANK = os.path.join(ROOT, "experiments/line3/bank2/bank2.tsv")
DATA = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")
wi = Q.WindowIndex.from_jsonl(DATA, os.path.join(CACHE, ZD), build=False, z_deep=ZD)
tsp = wi.space.tiers[wi.tier]
rows = [l.rstrip("\n").split("\t") for l in open(BANK, encoding="utf-8") if not l.startswith("#") and l.strip()]
rows = [r for r in rows if r[2] == "fulllead" and r[1] in ("intra2", "unans")]
seen = set()
tot = Counter()
for r in rows:
    it = Q.intake(wi, r[4])
    plan = Q.plan_windows(wi, it, cap=4)
    for n in plan.read:
        w = wi.by_n[n]
        sel, _ = Q.choose_members(w, MEM, "abstain")
        ev = SR.counts_evidence(wi.counts(w), wi.tier)
        for m in sel:
            if (n, m) in seen:
                continue
            seen.add((n, m))
            wc = Q.member_cross(w, m)
            by = wc.by_seat()
            for o, i in geo.edges(wc.L):
                so, si = by.get(o), by.get(i)
                if so is None or si is None:
                    continue
                ax = o.arm[1]
                na, _src = ev(o.arm, so.unit, si.unit)
                npair = tsp.n_pair(so.unit, si.unit) if so.unit != si.unit else tsp.n(so.unit)
                tot[(ax, "edges")] += 1
                tot[(ax, "axis")] += na > 0
                tot[(ax, "pair")] += npair > 0
                tot[(ax, "axis_only")] += (na > 0 and npair == 0)
                tot[(ax, "centre_edges")] += i == geo.CENTER
                tot[(ax, "centre_pair")] += (i == geo.CENTER and npair > 0)
lines = ["edge evidence in the crosses of the windows read at fast (%s, members %s): %d (window, member) crosses of %d questions" % (ZD, MEM, len(seen), len(rows)),
         "| axis of the arm | edges (both ends seated) | per-axis evidence n_a > 0 | flat evidence n_pair > 0 | per-axis only | edges at the centre | ... flat-evidenced |",
         "|---|---|---|---|---|---|---|"]
for ax in ("x", "y", "z"):
    lines.append("| %s | %d | %d | %d | %d | %d | %d |" % (ax, tot[(ax, "edges")], tot[(ax, "axis")], tot[(ax, "pair")], tot[(ax, "axis_only")],
                                                          tot[(ax, "centre_edges")], tot[(ax, "centre_pair")]))
txt = "\n".join(lines)
print(txt)
os.makedirs(os.path.join(HERE, "results"), exist_ok=True)
open(os.path.join(HERE, "results", "edge_evidence_%s_%s.txt" % (ZD, MEM)), "w", encoding="utf-8").write(txt + "\n")
