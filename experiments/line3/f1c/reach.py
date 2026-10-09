"""F1c (copy of f1/reach.py; f1/ not modified): modes whole / ordered+stop (f1/raw) and skip (f1c/raw).  Original doc: the reach table of the T9 audit (bank2 intra2, 69 golds), before / after / reverse.  A gold is REACHED in a tier when some
cross (seed s) holds both a question unit (cycle.make_context(query units).energy_units) and a unit that contains the gold
(scorer rule: gold alternative in the normalised unit text).  Query units = the T9 audit re-run records (raw/ask_fulllead_standard.jsonl in t9/audit).
usage: reach.py -> reach.md"""
import glob, json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
F1 = os.path.join(os.path.dirname(HERE), "f1", "raw")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
T9 = os.path.join(ROOT, "experiments/line3/t9")
sys.path.insert(0, ROOT); sys.path.insert(0, T9)
import scorer as S                                       # noqa: E402
from verantyx.line3 import cycle as cy                   # noqa: E402
from verantyx.line3.space import build_space, load_jsonl   # noqa: E402
FL = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")
recs = [json.loads(l) for l in open(os.path.join(T9, "audit/raw/ask_fulllead_standard.jsonl"), encoding="utf-8")]
recs.sort(key=lambda r: r["id"])
space = build_space(load_jsonl(FL))
def cross_sets(tier, mode):
    def rows(path):
        return [json.loads(l) for l in open(path, encoding="utf-8")][1:]
    base = os.path.join(F1, "fulllead_sents_%s_%s_mid.jsonl" % (tier, "ordered" if mode == "skip" else mode))
    if not os.path.exists(base): return None
    out = {r["seed"]: set(r["units"]) for r in rows(base)}
    if mode == "skip":
        # skip = stop for every cross that exhausted under stop (identical); the rebuilt crosses overlay it, from every f1c file there is:
        # the full tier, a sample, and the reach seeds (the only budget-stopped seeds that can put a gold next to a question unit)
        have = [f for f in sorted(glob.glob(os.path.join(HERE, "raw", "fulllead_sents_%s_skip_mid*.jsonl" % tier)))]
        if not have: return None
        for f in have:
            for r in rows(f):
                out[r["seed"]] = set(r["units"])
    return out
modes = ("whole", "ordered", "skip")
cs = {(t, m): cross_sets(t, m) for t in ("RUN", "WORD", "CHAR") for m in modes}
ONE = {}   # id -> shares a sentence with a question unit (one hop), RUN or WORD, from the T9 audit definition (gold unit and question unit in one sentence)
res = {m: {} for m in modes}
ncross = {}
for r in recs:
    gold = r["gold"]
    for m in modes:
        per = {}
        for t in ("RUN", "WORD", "CHAR"):
            if cs[(t, m)] is None: continue
            ts = space.tiers[t]
            gu = {u for u in ts.units() if any(g in S.norm(u) for g in S.golds(gold))}
            qu = set(cy.make_context(tuple(r["layer0"][t]["query_units"])).energy_units)
            ok = bool(gu) and any((c & qu) and (c & gu) for c in cs[(t, m)].values())
            ncross[(m, t)] = ncross.get((m, t), 0) + (sum(1 for c in cs[(t, m)].values() if (c & qu) and (c & gu)) if gu else 0)
            per[t] = (bool(gu), ok)
        res[m][r["id"]] = per
    # one hop: some sentence holds a question unit and a gold unit (RUN or WORD)
    hop = False
    for t in ("RUN", "WORD"):
        ts = space.tiers[t]
        gu = {u for u in ts.units() if any(g in S.norm(u) for g in S.golds(gold))}
        qu = set(cy.make_context(tuple(r["layer0"][t]["query_units"])).energy_units)
        hop = hop or any((set(su) & qu) and (set(su) & gu) for su in ts.sentence_units)
    ONE[r["id"]] = hop
L = []
def out(s=""): L.append(s); print(s)
n = len(recs)
out("# F1c reach (bank2 intra2, n = %d, fulllead, level mid)" % n); out()
out("A gold counts as reached in a tier when a cross that holds a question unit also holds a unit containing the gold.")
out("`gold unit exists` = some unit of the tier contains the gold (tokenisation, independent of placement). One hop = a sentence holds a question unit and a gold unit (RUN or WORD): %d." % sum(ONE.values())); out()
out("| tier | gold unit exists | whole (before) | ordered + stop | ordered + skip |")
out("|---|---|---|---|---|")
for t in ("RUN", "WORD", "CHAR"):
    ex = sum(res["whole"][i][t][0] for i in res["whole"]) if cs[(t, "whole")] else "-"
    row = [str(sum(res[m][i][t][1] for i in res[m])) if cs[(t, m)] else "-" for m in modes]
    out("| %s | %s | %s |" % (t, ex, " | ".join(row)))
anyr = {m: {i: any(v[1] for v in res[m][i].values()) for i in res[m]} for m in modes}
anyr_rw = {m: {i: any(v[1] for t, v in res[m][i].items() if t in ("RUN", "WORD")) for i in res[m]} for m in modes}
out("| any tier | | %s |" % " | ".join(str(sum(anyr[m].values())) for m in modes))
out("| RUN or WORD | | %s |" % " | ".join(str(sum(anyr_rw[m].values())) for m in modes))
out()
out("Crosses (seeds) that hold a question unit AND a gold unit, summed over the 69 golds (how many different crosses reach, not whether one does):")
out()
out("| tier | whole | ordered + stop | ordered + skip |")
out("|---|---|---|---|")
for t in ("RUN", "WORD", "CHAR"):
    out("| %s | %s |" % (t, " | ".join(str(ncross.get((m, t), "-")) for m in modes)))
out()
out("Gained / lost against ordered+stop (any tier): skip +%d / -%d; against whole: stop +%d / -%d, skip +%d / -%d" % (
    sum(anyr["skip"][i] and not anyr["ordered"][i] for i in anyr["whole"]), sum(anyr["ordered"][i] and not anyr["skip"][i] for i in anyr["whole"]),
    sum(anyr["ordered"][i] and not anyr["whole"][i] for i in anyr["whole"]), sum(anyr["whole"][i] and not anyr["ordered"][i] for i in anyr["whole"]),
    sum(anyr["skip"][i] and not anyr["whole"][i] for i in anyr["whole"]), sum(anyr["whole"][i] and not anyr["skip"][i] for i in anyr["whole"])))
out("Reached by skip though not one hop: %s" % (", ".join(i for i in anyr["skip"] if anyr["skip"][i] and not ONE[i]) or "none"))
out("One hop but still not reached (skip): %s" % (", ".join(i for i in anyr["skip"] if ONE[i] and not anyr["skip"][i]) or "none"))
out("Reached by skip, per tier, differing from stop: " + (", ".join("%s %s" % (t, ",".join(i for i in res["skip"] if res["skip"][i][t][1] != res["ordered"][i][t][1])) for t in ("RUN", "WORD", "CHAR")
    if any(res["skip"][i][t][1] != res["ordered"][i][t][1] for i in res["skip"])) or "none"))
open(os.path.join(HERE, "reach.md"), "w", encoding="utf-8").write("\n".join(L) + "\n")
