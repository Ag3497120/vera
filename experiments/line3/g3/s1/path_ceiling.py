"""G3-e2 diagnostic: what the path shape could reach if the agreement did not decide.  For the 69 intra2 questions of bank2 (fulllead), the windows the plan
reads at fast (read order qcount_first and, for comparison, grammar_first), every readable member of each window (the admission gate of L-646: the member
holds a question unit), the section walks of every axis (agreement three's reading, slide_ratios.read_axes): is the gold
  (a) the END unit (terminus) of some walk (the unit shape's ceiling if every walk's end were an answer),
  (b) a word of the PATH of some walk (the path shape's ceiling if every walk were an answer),
  (c) a seated unit of a read window (the window-level reach; the ceiling of both),
  (d) in an AGREED entry of the run (e2 jsonl, path shape)?
Counts of questions.  usage: path_ceiling.py CACHE_ROOT OUT.txt"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
G3 = os.path.dirname(HERE); LINE3 = os.path.dirname(G3); ROOT = os.path.dirname(os.path.dirname(LINE3))
sys.path.insert(0, os.path.join(LINE3, "t9")); sys.path.insert(0, os.path.join(LINE3, "bank2")); sys.path.insert(0, ROOT)
import scorer as S                      # noqa: E402
import baselines as BL                  # noqa: E402
from verantyx.line3 import slide_query as Q   # noqa: E402
from verantyx.line3 import slide_ratios as SR  # noqa: E402

CACHE, OUT = sys.argv[1], sys.argv[2]
bank = {}
for l in open(os.path.join(LINE3, "bank2", "bank2.tsv"), encoding="utf-8"):
    if l.startswith("#") or not l.strip():
        continue
    r = dict(zip(BL.FIELDS, l.rstrip("\n").split("\t")))
    if r["corpus"] == "fulllead" and r["kind"] == "intra2":
        bank[r["id"]] = r
L = []
def out(s=""):
    L.append(s); print(s, flush=True)
out("| placements | read order | questions | gold seated in a read window | gold = END unit of some walk | gold in the PATH of some walk | gold in the path of a WORKING section's walk | gold in an agreed entry (e2 run, path, three) |")
out("|---|---|---|---|---|---|---|---|")
for zd in ("slide", "order"):
    wi = Q.WindowIndex.from_jsonl(os.path.join(LINE3, "bank2", "data", "fulllead_sents.jsonl"), os.path.join(CACHE, zd), build=False, z_deep=zd)
    tsp = wi.space.tiers[wi.tier]
    agreed = {}
    p = os.path.join(HERE, "results", "e2_z%s-three-path.jsonl" % zd)
    for l in open(p, encoding="utf-8"):
        r = json.loads(l)
        agreed[r["id"]] = [w for e in r["entries"] for w in e["words"]]
    for ro in ("qcount_first", "grammar_first"):
        n = seated = end = anyp = work = ag = 0
        for qid, row in bank.items():
            gold = row["gold"]
            it = Q.intake(wi, row["question"])
            plan = Q.plan_windows(wi, it, cap=4, read_order=ro)
            n += 1
            sd = set(); ends = set(); paths = set(); wpaths = set()
            for wn in plan.read:
                w = wi.by_n[wn]
                sd |= w.seated
                sel, _skipped = Q.choose_members(w, "all", "abstain")
                ev = SR.counts_evidence(wi.counts(w), wi.tier)
                for i in sel:
                    h, hs = Q.holds(w, it, "seats", "off", i)
                    if h == 0:
                        continue
                    r = SR.read_axes(Q.member_cross(w, i), ev, tsp, it.ctx, wi.foundation, z_self_edges=True, agreement="three")
                    for ar in r.axes:
                        for s in ar.sections:
                            for wk in s.walks:
                                if wk.terminus is None:
                                    continue
                                ends.add(wk.terminus[0])
                                paths.update(k[0] for k in wk.path)
                                if s.unit is not None:
                                    wpaths.update(k[0] for k in wk.path)
            seated += S.hits_words(gold, sd)
            end += S.hits_words(gold, ends)
            anyp += S.hits_words(gold, paths)
            work += S.hits_words(gold, wpaths)
            if ro == "qcount_first":
                ag += S.hits_words(gold, agreed.get(qid, []))
        out("| z_deep %s | %s | %d | %d | %d | %d | %d | %s |" % (zd, ro, n, seated, end, anyp, work, ag if ro == "qcount_first" else "-"))
open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
