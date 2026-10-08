"""T8: the 90 S300 questions with layers OFF (layer 0 = the T7b result) and layers ON, all three tiers, at an effort preset.
usage: measure.py EFFORT OUT [WORKERS=1] [IDS=all] [FEEDBACK=none]
Per question: layer 0 (entries per tier, ms); then for each granularity (same = bundle every stable state, compress = only
the ones the question touched) both query variants (A: the initial query is passed on with the lower answer, B: the lower
answer only) with their entries, triggers, layers built, partial marks, trace fractions, ms.  No gold-based decision here
(summarize.py grades).  Layer 0 is read once and reused for every layered run of the question (`base=`)."""
import json
import multiprocessing as mp
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from verantyx.line3 import ask as A                                   # noqa: E402
from verantyx.line3 import matryoshka as M                            # noqa: E402

SCRATCH = ("/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/"
           "d52dc51d-8cb5-4487-931c-cc143bce928f/scratchpad/line3/t7")
EFFORT = sys.argv[1]
OUT = sys.argv[2]
workers = int(sys.argv[3]) if len(sys.argv) > 3 else 1
ids = sys.argv[4] if len(sys.argv) > 4 else "all"
FEEDBACK = sys.argv[5] if len(sys.argv) > 5 else "none"
DATA = os.path.join(ROOT, "experiments/line3/data/S300.jsonl")
G = {}


def _ent(e):
    return {"words": list(e.words), "centres": list(e.centres), "count": e.count, "stability": A._fs(e.stability)}


def _work(row):
    qid, kind, subj, question, gold = row[:5]
    idx = G["idx"]
    kw = {"nodes": int(EFFORT)} if EFFORT.isdigit() else {"effort": EFFORT}
    t0 = time.monotonic()
    c0 = A.ask(idx, question, **kw)
    ms0 = int((time.monotonic() - t0) * 1000)
    rec = {"id": qid, "kind": kind, "question": question, "gold": gold, "effort": EFFORT, "ms_layer0": ms0,
           "layer0": {o.tier: {"verdict": o.verdict, "entries": [_ent(e) for e in o.entries], "ms": o.ms,
                               "read": o.read_counts} for o in c0.outcomes},
           "on": {}}
    for gran in M.GRANULARITIES:
        opts = M.LayerOptions(variants=M.VARIANTS, granularity=gran, feedback=FEEDBACK,
                              bounds=M.bounds_for(None if EFFORT.isdigit() else EFFORT, int(EFFORT) if EFFORT.isdigit() else None))
        t1 = time.monotonic()
        c = M.ask_layered(idx, question, options=opts, base=c0, **kw)
        ms = int((time.monotonic() - t1) * 1000)
        tiers = {}
        for tl in c.layers:
            tiers[tl.tier] = {
                "triggered": tl.triggered, "growth_budget": len(tl.triggers["growth_budget"]),
                "query_no_fixed_point": len(tl.triggers["query_no_fixed_point"]), "crosses_read": tl.triggers["crosses_read"],
                "choice": {k: tl.choice[k] for k in ("bundles_if_compress", "bundles_if_same")},
                "fixed_point": tl.fixed_point, "ms": tl.ms,
                "runs": [{"variant": r.variant, "k": r.k, "bundles": r.n_bundles, "read": len(r.read),
                          "left_unread": r.left_unread, "partial": r.partial, "members_read": r.members_read,
                          "members_total": r.members_total, "verdict": r.verdict, "ms": r.ms,
                          "full": len(r.full_crosses), "no_fixed_point": r.no_fixed_point, "limit": r.layer_limit,
                          "trace": r.trace["fraction"], "trace_ok": r.trace["ok"],
                          "entries": [{"words": list(e.words), "centres": list(e.centres), "count": e.arrangements,
                                       "stability": A._fs(e.stability), "bundles": len(e.bundles)} for e in r.entries]}
                         for r in tl.runs]}
        rec["on"][gran] = {"ms": ms, "tiers": tiers, "stacked": c.stacked}
    return rec


def _init():
    G["idx"] = A.Index.from_jsonl(DATA, SCRATCH)


if __name__ == "__main__":
    rows = [l.rstrip("\n").split("\t") for l in open(os.path.join(ROOT, "experiments/line3/questions.tsv"), encoding="utf-8")][1:]
    if ids != "all":
        rows = [r for r in rows if r[0] in ids.split(",")]
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    t0 = time.time()
    if workers <= 1:
        _init()
        it, pool = map(_work, rows), None
    else:
        pool = mp.get_context("fork").Pool(workers, initializer=_init)
        it = pool.imap_unordered(_work, rows)
    n = 0
    with open(OUT, "w", encoding="utf-8") as f:
        for rec in it:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")
            f.flush()
            n += 1
            print("%d/%d %s l0 %.1fs same %.1fs cmp %.1fs" % (n, len(rows), rec["id"], rec["ms_layer0"] / 1000,
                                                              rec["on"]["same"]["ms"] / 1000, rec["on"]["compress"]["ms"] / 1000),
                  file=sys.stderr, flush=True)
    print("done %d in %.0fs" % (n, time.time() - t0), file=sys.stderr)
