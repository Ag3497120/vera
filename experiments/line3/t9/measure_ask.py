"""T9: bank2 questions of one corpus through the flat ask (layers off) and the layers on (path, stable-seats-path).
usage: measure_ask.py CORPUS PRESET OUT.jsonl [WORKERS=1] [IDS=all] [KINDS=all]     CORPUS: fulllead | s3000
Layer 0 is read once per question and reused (base=) by both layer configs, exactly as t8e/measure.py.
Placement cache dir: $T9_CACHE (default: the T9 scratch dir); crosses not cached are built on demand.
Records carry every entry (tier, k, words) of the flat list and of each layer config; summarize.py grades."""
import json, multiprocessing as mp, os, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from verantyx.line3 import ask as A          # noqa: E402
from verantyx.line3 import matryoshka as M   # noqa: E402

CORPUS, PRESET, OUT = sys.argv[1:4]
workers = int(sys.argv[4]) if len(sys.argv) > 4 else 1
ids = sys.argv[5] if len(sys.argv) > 5 else "all"
kinds = sys.argv[6] if len(sys.argv) > 6 else "all"
CACHE = os.environ.get("T9_CACHE", os.path.join(os.environ.get("TMPDIR", "/tmp"), "t9cache"))
DATA = {"fulllead": os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl"),
        "s3000": os.path.join(ROOT, "experiments/line3/data/S3000.jsonl")}[CORPUS]
BANK = os.path.join(ROOT, "experiments/line3/bank2/bank2.tsv")
G = {}
CONFIGS = [("path", "path"), ("seatsPath", "stable-seats-path")]


def _ent(e):
    return {"words": list(e.words), "centres": list(e.centres), "count": e.count, "stability": A._fs(e.stability)}


def _work(row):
    qid, kind, _c, subj, question, gold = row[:6]
    idx = G["idx"]
    kw = {"nodes": int(PRESET)} if PRESET.isdigit() else {"effort": PRESET}
    t0 = time.monotonic()
    c0 = A.ask(idx, question, **kw)
    ms0 = int((time.monotonic() - t0) * 1000)
    rec = {"id": qid, "kind": kind, "corpus": CORPUS, "question": question, "gold": gold, "preset": PRESET, "ms_layer0": ms0,
           "layer0": {o.tier: {"verdict": o.verdict, "ms": o.ms, "entries": [_ent(e) for e in o.entries], "read": o.read_counts}
                      for o in c0.outcomes}, "on": {}}
    for name, cand in CONFIGS:
        opts = M.LayerOptions(variants=("A",), granularity="compress", feedback="none", candidate=cand,
                              bounds=M.bounds_for(None if PRESET.isdigit() else PRESET, int(PRESET) if PRESET.isdigit() else None))
        t1 = time.monotonic()
        c = M.ask_layered(idx, question, options=opts, base=c0, **kw)
        ms = int((time.monotonic() - t1) * 1000)
        tiers = {}
        for tl in c.layers:
            tiers[tl.tier] = {"triggered": tl.triggered, "ms": tl.ms,
                              "runs": [{"k": r.k, "bundles": r.n_bundles, "partial": r.partial, "verdict": r.verdict, "ms": r.ms,
                                        "trace": r.trace["fraction"], "trace_ok": r.trace["ok"],
                                        "entries": [{"words": list(e.words), "bundles": len(e.bundles)} for e in r.entries]}
                                       for r in tl.runs]}
        rec["on"][name] = {"ms": ms, "tiers": tiers}
    return rec


def _init():
    G["idx"] = A.Index.from_jsonl(DATA, CACHE)


if __name__ == "__main__":
    rows = [l.rstrip("\n").split("\t") for l in open(BANK, encoding="utf-8") if not l.startswith("#") and l.strip()]
    rows = [r for r in rows if r[2] == CORPUS]
    if ids != "all":
        rows = [r for r in rows if r[0] in ids.split(",")]
    if kinds != "all":
        rows = [r for r in rows if r[1] in kinds.split(",")]
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    t0 = time.time()
    if workers <= 1:
        _init(); it = map(_work, rows)
    else:
        it = mp.get_context("fork").Pool(workers, initializer=_init).imap_unordered(_work, rows)
    n = 0
    with open(OUT, "w", encoding="utf-8") as f:
        for rec in it:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n"); f.flush(); n += 1
            print("%d/%d %s l0 %.1fs %s" % (n, len(rows), rec["id"], rec["ms_layer0"] / 1000,
                  " ".join("%s %.1fs" % (k, v["ms"] / 1000) for k, v in rec["on"].items())), file=sys.stderr, flush=True)
    print("done %d in %.0fs" % (n, time.time() - t0), file=sys.stderr)
