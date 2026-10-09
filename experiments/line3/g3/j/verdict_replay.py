"""G3-j addendum (L-789): the 94-question combined replay (G3-g2's inputs: T10 flat + layers records, live window records g2_win_*) with and without the block
flat/assembled, to count verdict changes under the owner's reading B (the assembled strings are display only).
The T10 records keep no sentences, so the block is built from PROXY sids (every sentence where a word of the entry is a unit of its tier: a superset of the live
source_sids, so a superset of the strings); for the 18 non-unit questions at fast the live sids exist (results/live_flat_fast.jsonl) and are used instead.
usage: PYTHONPATH=. PYTHONHASHSEED=0 python verdict_replay.py > results/verdict_replay.txt"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "experiments/line3/g3/combined"))
sys.path.insert(0, os.path.join(ROOT, "experiments/line3/bank2"))
import baselines as BL
from replay import flat_src, layers_src, win_src
from verantyx.line3 import combined as CB, granularity as GR, space as sp

L3 = os.path.join(ROOT, "experiments/line3")
CRES = os.path.join(L3, "g3/combined/results")
spc = sp.build_space(sp.load_jsonl(os.path.join(L3, "bank2/data/fulllead_sents.jsonl")))
ix = GR.SpanIndex(spc)
bank = {}
for l in open(os.path.join(L3, "bank2/bank2.tsv"), encoding="utf-8"):
    if l.startswith("#") or not l.strip():
        continue
    r = dict(zip(BL.FIELDS, l.rstrip("\n").split("\t")))
    bank[r["id"]] = r
jl = lambda p: [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
live = {r["id"]: r for r in jl(os.path.join(HERE, "results/live_flat_fast.jsonl"))}
tot = {}
for P in ("fast", "standard"):
    T10 = {r["id"]: r for r in jl(os.path.join(L3, "t10/results/ask_fulllead_%s_ordered-stop.jsonl" % P)) if "error" not in r}
    WIN = {ev: {r["id"]: r for r in jl(os.path.join(CRES, "g2_win_%s_%s.jsonl" % (P, ev))) if "error" not in r} for ev in ("plain", "window")}
    n = changed = ans_off = ans_on = with_block = flat_single_with_block = answer_changed = 0
    strings = 0
    for i in sorted(bank):
        if bank[i]["corpus"] != "fulllead" or i not in T10 or any(i not in WIN[e] for e in WIN):
            continue
        rec = T10[i]
        fs = flat_src(rec)
        cands = []
        for c, (t, e) in zip(fs.cands, [(t, e) for t in sp.TIERS for e in rec["layer0"][t]["entries"]]):
            if P == "fast" and i in live:
                sids = next(x["sids"] for x in live[i]["layer0"][t]["entries"] if x["words"] == e["words"])
            else:
                sids = sorted({s for w in e["words"] for s in spc.tiers[t].postings.get(w, ())})
            cands.append(CB.Cand(c.origin, c.words, c.centres, c.stability, c.arrangements, tuple(sids)))
        fs2 = CB.Source(fs.name, fs.verdict, tuple(cands), fs.abstentions, fs.read)
        asm = CB.assembled_source(fs2, spc, index=ix)
        rest = [layers_src(rec), win_src(WIN["plain"][i], "plain"), win_src(WIN["window"][i], "window")]
        q = bank[i]["question"]
        off = CB.combine(q, [fs] + rest)
        on = CB.combine(q, [fs2, asm] + rest)
        n += 1
        strings += len(asm.cands)
        with_block += bool(asm.cands)
        ans_off += off.verdict == CB.ANSWER
        ans_on += on.verdict == CB.ANSWER
        changed += off.verdict != on.verdict
        answer_changed += off.answer_obj()["answer"] != on.answer_obj()["answer"]
        flat_single_with_block += (len(fs.cands) == 1 and bool(asm.cands))
    tot[P] = dict(questions=n, with_block=with_block, strings=strings, verdict_changed=changed, answer_changed=answer_changed, answer_off=ans_off, answer_on=ans_on,
                  flat_single_with_block=flat_single_with_block)
    print(P, tot[P], flush=True)
json.dump(tot, open(os.path.join(HERE, "results/verdict_replay.json"), "w"), sort_keys=True, indent=1)
