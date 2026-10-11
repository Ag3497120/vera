"""G3-k: bank questions through ask(structure="combined", grammar="on"|"off") -- the committed defaults of the combined list (flat 3 tiers + layers
(stable-seats-path, variant A, compress) + windows (RUN; plain and window-evidence; representative members) + the G3-j assembly block), only `grammar` differs.

usage: measure_k.py PRESET OUT.jsonl --cache DIR --grammar on|off [--bank bank3|bank2] [--corpus fulllead] [--workers 10] [--ids a,b,..] [--kinds k1,k2]
                    [--limit N] [--resume] [--check]
  PRESET  fast | standard | full | <nodes>     --cache  the flat ordered placement cache dir (+ the window placements, loaded or placed once)
Record per question (jsonl): id, kind, question, gold, preset, grammar, ms, verdict, answer (CombinedAnswer.answer_obj(): header (with the `grammar` row when on),
blocks, entries with block / origins / marks / members (each with `via_standin` when on), grammar_form, standins), config, head, load1, pid.  A failing
question is {"id", "error"}; --resume keeps the valid records of the same preset and grammar and skips their ids."""
import argparse, json, multiprocessing as mp, os, sys, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)
from verantyx.line3 import ask as A            # noqa: E402
from verantyx.line3 import slide_query as SQ   # noqa: E402

ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
ap.add_argument("preset")
ap.add_argument("out")
ap.add_argument("--cache", required=True)
ap.add_argument("--grammar", choices=["on", "off"], required=True)
ap.add_argument("--standins", choices=["on", "off"], default="on",
                help="with --grammar on: off = the ORDER ONLY (the intake is made, then its stand-ins are dropped: form, slot and the read order stay, no unit is added) -- attribution run")
ap.add_argument("--flat-order", dest="flat_order", choices=["eq_first", "qcount_first"], default="qcount_first",
                help="with --grammar on (G3-k2, L-819): the flat plane's read order. DEFAULT HERE = qcount_first so that the G3-k records are reproducible with the old command lines; the G3-k2 runs pass --flat-order eq_first (the library default)")
ap.add_argument("--bank", choices=["bank3", "bank2"], default="bank3")
ap.add_argument("--corpus", default="fulllead")
ap.add_argument("--workers", type=int, default=1)
ap.add_argument("--ids", default="all")
ap.add_argument("--kinds", default="all")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--resume", action="store_true")
ap.add_argument("--check", action="store_true")
ARGS = ap.parse_args()
PRESET, OUT = ARGS.preset, ARGS.out
CACHE = os.path.expanduser(ARGS.cache)
DATA = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")
BANK = os.path.join(ROOT, "experiments/line3", ARGS.bank, ARGS.bank + ".tsv")
G = {}


def _head():
    try:
        import subprocess
        return subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or None
    except Exception:
        return None


def _open_index():
    idx = A.Index.from_jsonl(DATA, CACHE, A.DEFAULT_LEVEL, A.TIERS, group_insert="ordered", order="forward")
    short = {t: (len(idx.stores[t]._loaded), len(idx.space.tiers[t].units())) for t in idx.tiers}
    if any(a != b for a, b in short.values()):
        sys.exit("the placement cache in %s is incomplete (loaded, units): %s" % (CACHE, short))
    return idx, short


def _do(row):
    qid, kind, _c, subj, question, gold = row[:6]
    kw = {"nodes": int(PRESET)} if PRESET.isdigit() else {"effort": PRESET}
    t0 = time.monotonic()
    extra = {}
    if ARGS.grammar == "on" and ARGS.standins == "off":
        import dataclasses
        from verantyx.line3 import wiring as W
        gi = W.intake(G["idx"].space, question, W.context_of(G["idx"])[0])
        extra["grammar_intake"] = dataclasses.replace(gi, words=(), standins=())
    if ARGS.grammar == "on":
        extra["flat_order"] = ARGS.flat_order
    c = A.ask(G["idx"], question, structure="combined", grammar=ARGS.grammar, **extra, **kw)          # every other option = the committed default
    ms = int((time.monotonic() - t0) * 1000)
    return {"id": qid, "kind": kind, "question": question, "gold": gold, "preset": PRESET, "grammar": ARGS.grammar, "standins": ARGS.standins, "flat_order": ARGS.flat_order if ARGS.grammar == "on" else None, "ms": ms, "verdict": c.verdict,
            "answer": c.answer_obj(), "agreement": c.agreement(), "config": dict(c.config), "head": G["head"], "pid": os.getpid(),
            "load1": round(os.getloadavg()[0], 2)}


def _work(row):
    try:
        return _do(row)
    except Exception:
        return {"id": row[0], "error": traceback.format_exc()}


def _read_valid(path):
    keep = []
    if os.path.exists(path):
        for l in open(path, encoding="utf-8"):
            try:
                r = json.loads(l)
            except ValueError:
                continue                                     # a line cut by a kill
            if "error" not in r and r.get("preset") == PRESET and r.get("grammar") == ARGS.grammar and r.get("standins", "on") == ARGS.standins and (ARGS.grammar != "on" or r.get("flat_order", "qcount_first") == ARGS.flat_order):
                keep.append(r)
    return keep


if __name__ == "__main__":
    rows = [l.rstrip("\n").split("\t") for l in open(BANK, encoding="utf-8") if not l.startswith("#") and l.strip()]
    n_all = len(rows)
    rows = [r for r in rows if r[2] == ARGS.corpus]
    if ARGS.ids != "all":
        want = ARGS.ids.split(",")
        rows = [r for r in rows if r[0] in want]
    if ARGS.kinds != "all":
        rows = [r for r in rows if r[1] in ARGS.kinds.split(",")]
    if ARGS.limit:
        rows = rows[:ARGS.limit]
    t0 = time.time()
    G["idx"], short = _open_index()
    G["head"] = _head()
    from verantyx.line3 import wiring as W
    W.context_of(G["idx"])                                   # the span index and the particle records (whole-word stems) are built once here and inherited by fork
    t1 = time.time()
    wi = SQ.window_index_for(G["idx"], workers=max(1, ARGS.workers))
    print("index + flat cache load %.1fs; windows ready %.1fs (%d windows, z_deep %s); %s grammar=%s; %d of %d bank rows (%s); flat cache complete %s; "
          "workers %d; PYTHONHASHSEED=%s" % (t1 - t0, time.time() - t1, len(wi.windows), wi.z_deep, PRESET, ARGS.grammar, len(rows), n_all, ARGS.corpus, short,
                                             ARGS.workers, os.environ.get("PYTHONHASHSEED")), file=sys.stderr, flush=True)
    if ARGS.check:
        print(" ".join(r[0] for r in rows))
        sys.exit(0)
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    done = _read_valid(OUT) if ARGS.resume else []
    have = {r["id"] for r in done}
    todo = [r for r in rows if r[0] not in have]
    with open(OUT, "w", encoding="utf-8") as f:
        for r in done:
            f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
    import hashlib
    code = {}
    for n in ("grammar", "wiring", "cycle", "ask", "combined", "slide_query", "slide_flat", "matryoshka"):
        code[n] = hashlib.sha256(open(os.path.join(ROOT, "verantyx/line3", n + ".py"), "rb").read()).hexdigest()
    with open(OUT + ".meta.json", "w", encoding="utf-8") as f:
        json.dump({"argv": sys.argv, "head": G["head"], "cache": CACHE, "cache_files": sorted(os.listdir(CACHE)), "data": DATA, "bank": BANK,
                   "grammar": ARGS.grammar, "flat_order": ARGS.flat_order if ARGS.grammar == "on" else None, "started": time.strftime("%Y-%m-%d %H:%M:%S"), "resumed_ids": len(done), "pyhashseed": os.environ.get("PYTHONHASHSEED"),
                   "python": sys.version.split()[0], "window_corpus_sha256": wi.space.sha256(), "window_z_deep": wi.z_deep,
                   "window_slide_spec_sha256": wi.slide.spec.sha256(), "window_place_spec_sha256": wi.spec.sha256(), "code_sha256": code,
                   "ids": [r[0] for r in rows]}, f, indent=1, default=str)
    print("%d to do, %d kept from an earlier run" % (len(todo), len(done)), file=sys.stderr, flush=True)
    if not todo:
        print("done 0 (0 errors): nothing to do", file=sys.stderr)
        sys.exit(0)
    if ARGS.workers <= 1:
        it = map(_work, todo)
    else:
        it = mp.get_context("fork").Pool(ARGS.workers).imap_unordered(_work, todo)
    n = nerr = 0
    with open(OUT, "a", encoding="utf-8") as f:
        for rec in it:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n"); f.flush(); n += 1
            if "error" in rec:
                nerr += 1
                print("%d/%d %s ERROR %s" % (n, len(todo), rec["id"], rec["error"].strip().splitlines()[-1]), file=sys.stderr, flush=True)
                continue
            print("%d/%d %s %s %.1fs listed %d load %.1f" % (n, len(todo), rec["id"], rec["verdict"], rec["ms"] / 1000,
                  rec["answer"]["listed"], rec["load1"]), file=sys.stderr, flush=True)
    print("done %d (%d errors) in %.0fs" % (n, nerr, time.time() - t0), file=sys.stderr)
