"""T10: bank2 questions of one corpus through the flat ask (layers off) and the layers on, under a chosen initial placement
(group_insert / order / on_collapse) read from a placement cache.  t9/measure_ask.py's logic, parametrised.

usage: measure_ask.py CORPUS PRESET OUT.jsonl --cache DIR [--group-insert ordered] [--order forward] [--on-collapse stop]
                      [--layers ssp,path | none] [--workers 1] [--ids all] [--kinds all] [--limit N] [--resume] [--check]
  CORPUS  fulllead | s3000        PRESET  fast | standard | full | <nodes>
  --layers  comma list, run IN THIS ORDER on top of the same layer-0 result (base=): ssp = stable-seats-path, path = the default
            path candidates; none = flat only.  Each config builds its own layer-1 crosses (measured: the second is not warm;
            the record keeps `layer_order`).
  --check   load the index, assert the cache is complete for every tier, list the question ids, exit (a few seconds).
  --resume  keep the valid records already in OUT, skip their ids, append the rest (a killed sweep continues).
Layer 0 is read once per question and reused by every layers config, as t9/measure_ask.py.  The upper-layer stacks are NOT cleared
between questions (as t9).  The placement cache must be COMPLETE: the question path reads every cross of a tier, and an
incomplete cache would build crosses on demand (hours; L-477), so the run refuses to start on an incomplete cache.
Records: t9's fields plus gi / order / oc / head / load1 / pid / layer_order; a failing question is recorded as {"id", "error"}."""
import argparse, json, multiprocessing as mp, os, sys, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from verantyx.line3 import ask as A          # noqa: E402
from verantyx.line3 import matryoshka as M   # noqa: E402

ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
ap.add_argument("corpus", choices=["fulllead", "s3000"])
ap.add_argument("preset")
ap.add_argument("out")
ap.add_argument("--cache", required=True)
ap.add_argument("--group-insert", default="ordered", choices=["whole", "ordered"])
ap.add_argument("--order", default="forward", choices=["forward", "reverse"])
ap.add_argument("--on-collapse", default="stop", choices=["stop", "skip"])
ap.add_argument("--layers", default="ssp,path")
ap.add_argument("--workers", type=int, default=1)
ap.add_argument("--ids", default="all")
ap.add_argument("--kinds", default="all")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--resume", action="store_true")
ap.add_argument("--check", action="store_true")
ARGS = ap.parse_args()
CORPUS, PRESET, OUT = ARGS.corpus, ARGS.preset, ARGS.out
CACHE = os.path.expanduser(ARGS.cache)
DATA = {"fulllead": os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl"),
        "s3000": os.path.join(ROOT, "experiments/line3/data/S3000.jsonl")}[CORPUS]
BANK = os.path.join(ROOT, "experiments/line3/bank2/bank2.tsv")
CONFIG_OF = {"path": ("path", "path"), "ssp": ("seatsPath", "stable-seats-path")}
LAYERS = [] if ARGS.layers in ("none", "") else ARGS.layers.split(",")
for _l in LAYERS:
    if _l not in CONFIG_OF:
        ap.error("--layers: %s not in path, ssp, none" % _l)
CONFIGS = [CONFIG_OF[l] for l in LAYERS]
G = {}


def _head():
    try:
        return open(os.path.join(ROOT, "PRO_HEAD")).read().strip()
    except OSError:
        pass
    try:
        import subprocess
        return subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or None
    except Exception:
        return None


def _ent(e):
    return {"words": list(e.words), "centres": list(e.centres), "count": e.count, "stability": A._fs(e.stability)}


def _open_index():
    kw = {"group_insert": ARGS.group_insert, "order": ARGS.order}
    if ARGS.on_collapse != "stop":                         # F1c option; absent from older trees, "stop" is their only behaviour
        kw["on_collapse"] = ARGS.on_collapse
    idx = A.Index.from_jsonl(DATA, CACHE, A.DEFAULT_LEVEL, A.TIERS, **kw)
    short = {t: (len(idx.stores[t]._loaded), len(idx.space.tiers[t].units())) for t in idx.tiers}
    if any(a != b for a, b in short.values()):
        sys.exit("the placement cache in %s is incomplete or missing for %s/%s/%s (loaded, units): %s"
                 % (CACHE, ARGS.group_insert, ARGS.order, ARGS.on_collapse, short))
    return idx, short


def _do(row):
    qid, kind, _c, subj, question, gold = row[:6]
    idx = G["idx"]
    kw = {"nodes": int(PRESET)} if PRESET.isdigit() else {"effort": PRESET}
    t0 = time.monotonic()
    c0 = A.ask(idx, question, **kw)
    ms0 = int((time.monotonic() - t0) * 1000)
    rec = {"id": qid, "kind": kind, "corpus": CORPUS, "question": question, "gold": gold, "preset": PRESET, "ms_layer0": ms0,
           "gi": ARGS.group_insert, "order": ARGS.order, "oc": ARGS.on_collapse, "head": G["head"], "pid": os.getpid(),
           "layer_order": LAYERS, "verdict0": c0.verdict,
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
    rec["load1"] = round(os.getloadavg()[0], 2)
    return rec


def _work(row):
    try:
        return _do(row)
    except Exception:                                        # one bad question must not end a multi-hour sweep
        return {"id": row[0], "error": traceback.format_exc()}


def _read_valid(path):
    keep = []
    if os.path.exists(path):
        for l in open(path, encoding="utf-8"):
            try:
                r = json.loads(l)
            except ValueError:
                continue                                     # a line cut by a kill
            if "error" not in r and r.get("preset") == PRESET:
                keep.append(r)
    return keep


if __name__ == "__main__":
    rows = [l.rstrip("\n").split("\t") for l in open(BANK, encoding="utf-8") if not l.startswith("#") and l.strip()]
    rows = [r for r in rows if r[2] == CORPUS]
    if ARGS.ids != "all":
        rows = [r for r in rows if r[0] in ARGS.ids.split(",")]
    if ARGS.kinds != "all":
        rows = [r for r in rows if r[1] in ARGS.kinds.split(",")]
    if ARGS.limit:
        rows = rows[:ARGS.limit]
    t0 = time.time()
    G["idx"], short = _open_index()
    G["head"] = _head()
    print("index + cache load %.1fs; %s; %d questions; cache complete (loaded, units) %s; layers %s; workers %d; PYTHONHASHSEED=%s"
          % (time.time() - t0, CORPUS + "/" + PRESET, len(rows), short, LAYERS or "none", ARGS.workers,
             os.environ.get("PYTHONHASHSEED")), file=sys.stderr, flush=True)
    if ARGS.check:
        print(" ".join(r[0] for r in rows))
        sys.exit(0)
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    done = _read_valid(OUT) if ARGS.resume else []
    have = {r["id"] for r in done}
    todo = [r for r in rows if r[0] not in have]
    with open(OUT, "w", encoding="utf-8") as f:                  # rewritten without cut lines and errors, then appended
        for r in done:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    with open(OUT + ".meta.json", "w", encoding="utf-8") as f:
        json.dump({"argv": sys.argv, "head": G["head"], "cache": CACHE, "cache_files": sorted(os.listdir(CACHE)),
                   "data": DATA, "started": time.strftime("%Y-%m-%d %H:%M:%S"), "resumed_ids": len(done),
                   "pyhashseed": os.environ.get("PYTHONHASHSEED"), "python": sys.version.split()[0]}, f, indent=1)
    print("%d to do, %d kept from an earlier run" % (len(todo), len(done)), file=sys.stderr, flush=True)
    if ARGS.workers <= 1:
        it = map(_work, todo)
    else:
        it = mp.get_context("fork").Pool(ARGS.workers).imap_unordered(_work, todo)     # the loaded index is inherited by fork
    n = nerr = 0
    with open(OUT, "a", encoding="utf-8") as f:
        for rec in it:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n"); f.flush(); n += 1
            if "error" in rec:
                nerr += 1
                print("%d/%d %s ERROR %s" % (n, len(todo), rec["id"], rec["error"].strip().splitlines()[-1]), file=sys.stderr, flush=True)
                continue
            print("%d/%d %s l0 %.1fs %s load %.1f" % (n, len(todo), rec["id"], rec["ms_layer0"] / 1000,
                  " ".join("%s +%.1fs" % (k, v["ms"] / 1000) for k, v in rec["on"].items()), rec["load1"]), file=sys.stderr, flush=True)
    print("done %d (%d errors) in %.0fs" % (n, nerr, time.time() - t0), file=sys.stderr)
