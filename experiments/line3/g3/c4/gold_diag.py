"""G3-c4 diagnostic: what happens in the windows that SEAT the gold.
usage: gold_diag.py CACHE_ROOT [OUT.md]       (CACHE_ROOT/slide and CACHE_ROOT/order from sweep_c4.sh)
For each z_deep rule and each agreement rule, over the 69 intra2 questions: the windows that hold a question unit (every candidate window, no cap)
and seat a unit that holds the gold (the reach windows); every member of their classes is read as the question path reads it (slide_query.member_cross,
slide_ratios.read_axes, z self edges on); per axis the members are counted by outcome: the answer is the gold unit / another unit / a typed abstention.
`admitted gold` = the member answers the gold unit AND would be admitted (holds a question unit, grounded, strictly stable on that axis): the gold would
be in a candidate if that window were read.  Counts only; no ranking.  Exact integers."""
import functools
import os
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
G3 = os.path.dirname(HERE)
LINE3 = os.path.dirname(G3)
ROOT = os.path.dirname(os.path.dirname(LINE3))
sys.path.insert(0, os.path.join(LINE3, "t9")); sys.path.insert(0, os.path.join(LINE3, "bank2")); sys.path.insert(0, ROOT)
import scorer as S                      # noqa: E402
import baselines as BL                  # noqa: E402
from verantyx.line3 import slide as SL          # noqa: E402
from verantyx.line3 import slide_query as Q     # noqa: E402
from verantyx.line3 import slide_ratios as SR   # noqa: E402

CACHE = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "results", "gold_diag.md")
bank = {}
for l in open(os.path.join(LINE3, "bank2", "bank2.tsv"), encoding="utf-8"):
    if l.startswith("#") or not l.strip():
        continue
    r = dict(zip(BL.FIELDS, l.rstrip("\n").split("\t")))
    if r["corpus"] == "fulllead" and r["kind"] == "intra2":
        bank[r["id"]] = r
orig = SL.default_spec
L = []
L.append("# G3-c4 diagnostic: the members of the windows that seat the gold (fulllead, intra2, n = %d)" % len(bank))
L.append("")
L.append("Windows = those that hold a question unit and seat a unit that holds the gold (representative's seats). Members = every member of the class, read as the question path reads it; "
         "outcome per (member, axis): gold = the agreed unit holds the gold, other = another unit, else the typed abstention. `admitted gold` = gold AND the member holds a question unit, "
         "the answer is grounded and the axis is strictly stable for the member (what slide_query.read_window admits).")
L.append("")
for ag in ("three", "two_if_single_edge"):
    L.append("## agreement %s" % ag)
    L.append("")
    L.append("| z_deep | questions with a reach window | reach windows | members read | axis | gold | other unit | points_nowhere | section_disagreement | ratio_disagreement | no_edges | admitted gold (member-axes) | reach windows with an admitted gold on this axis | questions with an admitted gold on this axis |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for zd in ("slide", "order"):
        SL.default_spec = functools.partial(orig, z_deep=zd)
        wi = Q.WindowIndex.from_jsonl(os.path.join(LINE3, "bank2", "data", "fulllead_sents.jsonl"), os.path.join(CACHE, zd), build=False)
        tsp = wi.space.tiers[wi.tier]
        ev_cache = {}
        nq = nw = nm = 0
        per = {a: Counter() for a in SR.AXES}
        wins_adm = {a: set() for a in SR.AXES}
        q_adm = {a: set() for a in SR.AXES}
        for qid, r in sorted(bank.items()):
            it = Q.intake(wi, r["question"])
            pl = Q.plan_windows(wi, it)
            cand = [n for b in pl.blocks for n in b.windows]
            gw = [wi.by_n[n] for n in cand if any(S.hits_words(r["gold"], [u]) for u in wi.by_n[n].seated)]
            if not gw:
                continue
            nq += 1
            for w in gw:
                nw += 1
                ev = ev_cache.get(w.n) or ev_cache.setdefault(w.n, SR.counts_evidence(wi.counts(w), wi.tier))
                for i in range(w.class_size):
                    wc = Q.member_cross(w, i)
                    res = SR.read_axes(wc, ev, tsp, it.ctx, wi.foundation, z_self_edges=True, agreement=ag)
                    nm += 1
                    h, hs = Q.holds(w, it, "seats", "off", i)
                    for a in SR.AXES:
                        an = res.answer(a)
                        if an is None:
                            per[a][res.abstention(a).kind] += 1
                            continue
                        if S.hits_words(r["gold"], [an.unit]):
                            per[a]["gold"] += 1
                            if h > 0 and not (an.grounded < 1 and an.section is not None) and w.stable_member(i, a):
                                per[a]["admitted"] += 1
                                wins_adm[a].add((qid, w.n))
                                q_adm[a].add(qid)
                        else:
                            per[a]["other"] += 1
        for a in ("x", "z"):
            c = per[a]
            L.append("| %s | %d | %d | %d | %s | %d | %d | %d | %d | %d | %d | %d | %d | %d |" % (
                zd, nq, nw, nm, a, c["gold"], c["other"], c[SR.POINTS_NOWHERE], c[SR.SECTION_DISAGREEMENT], c[SR.RATIO_DISAGREEMENT], c[SR.NO_EDGES],
                c["admitted"], len(wins_adm[a]), len(q_adm[a])))
        print(ag, zd, "done", file=sys.stderr, flush=True)
    L.append("")
SL.default_spec = orig
open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
print("\n".join(L))
