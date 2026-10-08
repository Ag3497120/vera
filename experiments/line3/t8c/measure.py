"""T8c: the 90 S300 questions at an effort preset: layer 0 (layers off) read once and reused (`base=`), then compress layers with
bagA = T8 bag (A), pathA = T8b path words (A), stableA / stableB = T8c last-stable-state path words (L-340..).  No gold decision here.
usage: measure.py EFFORT OUT [WORKERS=1] [IDS=all]"""
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
EXTRA = sys.argv[5] if len(sys.argv) > 5 else "0"
DATA = os.path.join(ROOT, "experiments/line3/data/S300.jsonl")
G = {}
CONFIGS = [("bagA", "compress", ("A",), "bag"), ("pathA", "compress", ("A",), "path"),
           ("stableA", "compress", ("A",), "stable"), ("stableB", "compress", ("B",), "stable")]


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
    for name, gran, vs, cand in CONFIGS:
        opts = M.LayerOptions(variants=vs, granularity=gran, feedback="none", candidate=cand,
                              bounds=M.bounds_for(None if EFFORT.isdigit() else EFFORT, int(EFFORT) if EFFORT.isdigit() else None))
        t1 = time.monotonic()
        c = M.ask_layered(idx, question, options=opts, base=c0, **kw)
        ms = int((time.monotonic() - t1) * 1000)
        tiers = {}
        for tl in c.layers:
            tiers[tl.tier] = {
                "triggered": tl.triggered, "ms": tl.ms,
                "runs": [{"variant": r.variant, "k": r.k, "bundles": r.n_bundles, "read": len(r.read),
                          "left_unread": r.left_unread, "partial": r.partial, "verdict": r.verdict, "ms": r.ms,
                          "limit": r.layer_limit, "boundaries": [d["boundary"] | {"seed": d["seed"], "layer": d["layer"], "listed": d["listed"]} for d in r.boundaries], "without_path_words": r.without_path_words, "candidate": r.candidate,
                          "trace": r.trace["fraction"], "trace_ok": r.trace["ok"], "trace_failures": r.trace["failures"],
                          "entries": [{"words": list(e.words), "centres": list(e.centres), "count": e.arrangements,
                                       "stability": A._fs(e.stability), "bundles": len(e.bundles),
                                       "sources": len(e.source_sids), "reads": len(e.path_from),
                                       "all_words_sourced": all(ss for _, ss in (e.word_sources or ()))}
                                      for e in r.entries]}
                         for r in tl.runs]}
        rec["on"][name] = {"ms": ms, "tiers": tiers, "stacked": c.stacked}
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
            print("%d/%d %s l0 %.1fs %s" % (n, len(rows), rec["id"], rec["ms_layer0"] / 1000,
                                           " ".join("%s %.1fs" % (k, v["ms"] / 1000) for k, v in rec["on"].items())),
                  file=sys.stderr, flush=True)
    print("done %d in %.0fs" % (n, time.time() - t0), file=sys.stderr)
