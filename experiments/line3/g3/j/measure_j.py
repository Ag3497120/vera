"""G3-j measurement: the F2 assembly applied to the FLAT block of the combined list (combined.assembled_source: layer 0, scope all, no bridging):
how many of the 18 golds of bank2 intra2 that are not one unit of any tier (t9/audit/tokenisation.jsonl) are inside a string of the block flat/assembled, at
fast and standard, with the chance control (the other 17 golds against this question's strings).

Flat records used (each entry's words and the sentences `source_sids` it cites are needed; the T10 records keep no sentences, measure_ask._ent):
  T9   t9/audit/raw/ask_fulllead_{fast,standard}.jsonl      real sids (the records F2's L-491 used); T9 placement (group_insert whole)
  T10L results/live_flat_<preset>.jsonl (live_flat.py)        T10's index / cache / options re-run flat-only for the 18 questions, real sids
  T10P t10/results/ask_fulllead_<preset>_ordered-stop.jsonl   the T10 records themselves with PROXY sids: for each entry the sentences in which any of its words is a unit
                                                              of its tier (a superset of the live source_sids: the strings are a superset of the live block's)
usage: PYTHONPATH=. PYTHONHASHSEED=0 python measure_j.py > results/measure_j.txt"""
import json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "experiments/line3/t9"))
import scorer as S
from verantyx.line3 import combined as CB
from verantyx.line3 import granularity as GR
from verantyx.line3 import space as sp

AUD = os.path.join(ROOT, "experiments/line3/t9/audit")
RES = os.path.join(HERE, "results")
spc = sp.build_space(sp.load_jsonl(os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")))
ix = GR.SpanIndex(spc)
tok = [json.loads(l) for l in open(os.path.join(AUD, "tokenisation.jsonl"), encoding="utf-8")]
non = [r for r in tok if not any(r[t]["one_unit"] for t in sp.TIERS)]
ids = [r["id"] for r in non]
golds = {r["id"]: r["gold"] for r in non}
assert len(ids) == 18


def jl(path):
    return {r["id"]: r for r in (json.loads(l) for l in open(path, encoding="utf-8")) if "error" not in r}


def flat_src(rec, proxy=False):
    cands = []
    for t in sp.TIERS:
        for e in rec["layer0"][t]["entries"]:
            if proxy:
                sids = sorted({s for w in e["words"] for s in spc.tiers[t].postings.get(w, ())})
            else:
                sids = e["sids"]
            cands.append(CB.Cand(CB.flat_origin(t), tuple(e["words"]), source_sids=tuple(sids)))
    return CB.Source(CB.FLAT, CB.CHOICE if len(cands) > 1 else CB.ANSWER if cands else "UNKNOWN", tuple(cands))


def excess(gold, text):
    t = S.norm(text)
    return min(len(t) - len(g) for g in S.golds(gold) if g in t)


def run(label, recs, proxy=False):
    """recs: id -> record.  Returns a dict of the numbers and prints the per-question rows."""
    strings, hits, exc, exact, ntr, bad, ent, best = {}, [], {}, [], {}, 0, {}, {}
    t0 = time.time()
    for qid in ids:
        fs = flat_src(recs[qid], proxy)
        a = CB.assembled_source(fs, spc, index=ix)
        strings[qid] = [c.words[0] for c in a.cands]
        ent[qid] = len(fs.cands)
        bad += sum(0 if c.trace_ok else 1 for c in a.cands)
        h = [s for s in strings[qid] if S.hits_text(golds[qid], s)]
        if h:
            hits.append(qid)
            exc[qid] = min(excess(golds[qid], s) for s in h)
            best[qid] = min(h, key=lambda s: (excess(golds[qid], s), s))
        if any(S.norm(s) in S.golds(golds[qid]) for s in strings[qid]):
            exact.append(qid)
    ctl = sum(1 for q in ids for o in ids if o != q and any(S.hits_text(golds[o], s) for s in strings[q]))
    # the flat entries themselves hold the gold? (no: not one unit; shown for context, the word rule of the T9 scorer)
    in_entries = [q for q in ids if any(S.hits_words(golds[q], e["words"]) for t in sp.TIERS for e in recs[q]["layer0"][t]["entries"])]
    n = sorted(len(strings[q]) for q in ids)
    print("%-14s hits %2d/18 %s | exact %d | excess %s | strings/question median %d max %d | control %d/306 | trace not ok %d | flat entries hold gold %d | %.0fs" % (
        label, len(hits), hits, len(exact), sorted(exc.values()), n[len(n) // 2], n[-1], ctl, bad, len(in_entries), time.time() - t0), flush=True)
    return {"label": label, "hits": hits, "exact": exact, "excess": exc, "n": {q: len(strings[q]) for q in ids}, "best": best, "control": ctl, "bad": bad,
            "entries": ent, "in_entries": in_entries}


out = {}
print("non-unit golds:", ids)
for preset in ("fast", "standard"):
    print("\n== %s ==" % preset)
    t9 = jl(os.path.join(AUD, "raw/ask_fulllead_%s.jsonl" % preset))
    out["T9/" + preset] = run("T9 real sids", t9)
    lp = os.path.join(RES, "live_flat_%s.jsonl" % preset)
    if os.path.exists(lp):
        live = jl(lp)
        if all(q in live for q in ids):
            out["T10L/" + preset] = run("T10 live", live)
        else:
            print("T10 live: %d of 18 done" % sum(q in live for q in ids))
    t10 = jl(os.path.join(ROOT, "experiments/line3/t10/results/ask_fulllead_%s_ordered-stop.jsonl" % preset))
    out["T10P/" + preset] = run("T10 proxy sids", t10, proxy=True)
    # live vs recorded T10 (the live run must be the same flat read)
    if "T10L/" + preset in out:
        same = sum(1 for q in ids if all([(e["words"], e["stability"]) for e in live[q]["layer0"][t]["entries"]] ==
                                         [(e["words"], e["stability"]) for e in t10[q]["layer0"][t]["entries"]] for t in sp.TIERS))
        print("live entries (words, stability) equal to the recorded T10: %d / 18 questions" % same)
        out["T10L/" + preset]["equal_to_t10"] = same

print("\n== effect on the verdict (T9 records of the 69 intra2 questions; the flat block alone + the assembled block) ==")
for preset in ("fast", "standard"):
    t9 = jl(os.path.join(AUD, "raw/ask_fulllead_%s.jsonl" % preset))
    single = flips = 0
    for qid, rec in sorted(t9.items()):
        fs = flat_src(rec)
        if len(fs.cands) != 1:
            continue
        single += 1
        a = CB.assembled_source(fs, spc, index=ix)
        v = CB.combine("q", [fs, a]).verdict
        flips += v == CB.CHOICE
    print("%s: questions with exactly one flat entry (flat ANSWER): %d; with an assembled string beside it (-> CHOICE of 2): %d" % (preset, single, flips))
    out["verdict/" + preset] = {"single_flat": single, "to_choice": flips}
json.dump(out, open(os.path.join(RES, "measure_j.json"), "w"), ensure_ascii=False, sort_keys=True, indent=1)
