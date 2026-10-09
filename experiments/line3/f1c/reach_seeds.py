"""F1c: the seeds whose skip cross can matter for the reach table.  A cross of seed s holds only s and units that share a sentence with s,
so a cross holding a question unit q and a gold unit g needs s in N(q) & N(g), N(x) = {x} + units co-occurring with x (any sentence).
Seeds outside that set can never be reached-relevant, whatever the build.  Output: reach_seeds_<TIER>.json = sorted list of seeds in that set
for at least one of the 69 questions AND stopped on budget under ordered+stop (the others are identical under skip).
usage: reach_seeds.py"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
T9 = os.path.join(ROOT, "experiments/line3/t9")
sys.path.insert(0, ROOT); sys.path.insert(0, T9)
import scorer as S                                       # noqa: E402
from verantyx.line3 import cycle as cy                   # noqa: E402
from verantyx.line3.space import build_space, load_jsonl   # noqa: E402
FL = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")
recs = [json.loads(l) for l in open(os.path.join(T9, "audit/raw/ask_fulllead_standard.jsonl"), encoding="utf-8")]
space = build_space(load_jsonl(FL))
for tier in ("RUN", "WORD", "CHAR"):
    ts = space.tiers[tier]
    rows = [json.loads(l) for l in open(os.path.join(ROOT, "experiments/line3/f1/raw/fulllead_sents_%s_ordered_mid.jsonl" % tier), encoding="utf-8")][1:]
    bud = {r["seed"] for r in rows if r["stop"] == "budget"}
    def N(x):
        out = {x}
        for sid in ts.postings.get(x, ()):
            out.update(ts.sentence_units[sid])
        return out
    keep = set()
    for r in recs:
        gu = [u for u in ts.units() if any(g in S.norm(u) for g in S.golds(r["gold"]))]
        qu = [u for u in cy.make_context(tuple(r["layer0"][tier]["query_units"])).energy_units if u in ts.postings]
        if not gu or not qu:
            continue
        nq = set().union(*(N(q) for q in qu)); ng = set().union(*(N(g) for g in gu))
        keep |= nq & ng
    sel = sorted(keep & bud)
    json.dump(sel, open(os.path.join(HERE, "reach_seeds_%s.json" % tier), "w", encoding="utf-8"), ensure_ascii=False)
    print(tier, "units", len(ts.units()), "budget-stopped", len(bud), "relevant seeds", len(keep), "of which budget-stopped", len(sel))
