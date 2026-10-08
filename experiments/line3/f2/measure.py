"""F2 measurement (L-490..): the 18 golds of bank2 intra2 that are not one unit of any tier (T9 audit tokenisation.jsonl).
(1) upper bound: from ALL units of the three tiers in the gold sentence, is the gold assemblable (scope all)?  how tight?
(2) re-run: the T9 standard records (raw/ask_fulllead_standard.jsonl: layer-0 entries of the three tiers, and the two
    layer configs) with the option on: how many golds are inside an assembled string.
Measurement only.  usage: PYTHONHASHSEED=0 python measure.py > results.txt"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
AUD = os.path.join(ROOT, "experiments/line3/t9/audit")
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "experiments/line3/t9"))
import scorer as S
from verantyx.line3 import space as sp
from verantyx.line3 import granularity as G

spc = sp.build_space(sp.load_jsonl(os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")))
ix = G.SpanIndex(spc)
tok = [json.loads(l) for l in open(os.path.join(AUD, "tokenisation.jsonl"), encoding="utf-8")]
non = [r for r in tok if not any(r[t]["one_unit"] for t in ("RUN", "WORD", "CHAR"))]
print("non-unit golds:", len(non), "of", len(tok))
ids = {r["id"] for r in non}


def norm_has(gold, text):
    t = S.norm(text)
    return [g for g in S.golds(gold) if g in t]


def excess(gold, text):
    t = S.norm(text)
    return min(len(t) - len(g) for g in S.golds(gold) if g in t)


print("\n== (1) upper bound: all units of all tiers of the gold sentence, scope all ==")
ub = 0
for r in non:
    sid = r["sid"]
    ents = [(t, set(spc.tiers[t].sentence_units[sid]), [sid]) for t in sp.TIERS]
    res = G.assemble(spc, ents, "all", ix)
    hit = [a for a in res if norm_has(r["gold"], a.text)]
    # per tier alone (entry scope on that tier's units only) and the tightest string
    per = {}
    for t in sp.TIERS:
        rs = G.assemble(spc, [(t, set(spc.tiers[t].sentence_units[sid]), [sid])], "entry", ix)
        h = [a for a in rs if norm_has(r["gold"], a.text)]
        per[t] = (min(excess(r["gold"], a.text) for a in h) if h else None)
    ub += bool(hit)
    print("%s gold=%s sentence=%r spans(R/W/C)=%s/%s/%s | assemblable=%s | tightest excess chars by tier-only chain %s | any tier mix: %s" % (
        r["id"], r["gold"], r["text"][:40], r["RUN"]["span"], r["WORD"]["span"], r["CHAR"]["span"], bool(hit), per,
        min((excess(r["gold"], a.text) for a in hit), default=None)))
print("upper bound (assemblable from the gold sentence's units): %d / %d" % (ub, len(non)))

print("\n== (2) re-run: T9 standard records, option on ==")
raw = [json.loads(l) for l in open(os.path.join(AUD, "raw/ask_fulllead_standard.jsonl"), encoding="utf-8")]
raw = {r["id"]: r for r in raw}


def sets_for(rec, system):
    """entries as (tier, words, sids) for one system of the T9 audit record."""
    out = []
    if system == "flat":
        for t in sp.TIERS:
            for e in rec["layer0"][t]["entries"]:
                out.append((t, e["words"], e["sids"]))
    else:
        for t in sp.TIERS:
            for e in rec["layer0"][t]["entries"]:
                out.append((t, e["words"], e["sids"]))
            for run in rec["on"][system]["tiers"][t]["runs"]:
                for e in run["entries"]:
                    out.append((t, e["words"], e["sids"]))
    return out


non_ids = [r["id"] for r in non]
golds = {r["id"]: r["gold"] for r in non}
for bridge in (False, True):
    print("\n-- bridge over function words = %s --" % bridge)
    if bridge:
        ub2 = 0
        for r in non:
            sid = r["sid"]
            ents = [(t, set(spc.tiers[t].sentence_units[sid]), [sid]) for t in sp.TIERS]
            ub2 += any(norm_has(r["gold"], a.text) for a in G.assemble(spc, ents, "all", ix, bridge=True))
        print("upper bound with bridge: %d / %d" % (ub2, len(non)))
    for system in ("flat", "path", "seatsPath"):
        for scope in ("entry", "all"):
            hitq, cnt, chance_num, chance_den, exc, bad = [], [], 0, 0, [], 0
            for qid in non_ids:
                ents = sets_for(raw[qid], system)
                res = G.assemble(spc, ents, scope, ix, bridge=bridge)
                cnt.append(len(res))
                hits = [a for a in res if norm_has(golds[qid], a.text)]
                if hits:
                    hitq.append(qid)
                    exc.append(min(excess(golds[qid], a.text) for a in hits))
                for a in res[:50]:
                    bad += len(G.trace_check(spc, a, bridge))
                for other in non_ids:                      # control: the other questions' golds against this question's strings
                    if other != qid:
                        chance_den += 1
                        chance_num += any(norm_has(golds[other], a.text) for a in res)
            cnt.sort()
            print("%-9s %-5s: hits %2d/18 %s excess %s | strings/question median %d max %d | control (other questions' golds) %d/%d | trace problems in first 50/q: %d" % (
                system, scope, len(hitq), hitq, sorted(exc), cnt[len(cnt) // 2], cnt[-1], chance_num, chance_den, bad))
