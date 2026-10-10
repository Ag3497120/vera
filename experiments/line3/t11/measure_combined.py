"""T11: bank3 (the "unknown abilities" bank) fulllead questions through ask(structure="combined") -- the committed defaults:
flat 3 tiers (ordered/forward/stop placement cache) + layers (stable-seats-path, variant A, compress) + windows (RUN; plain and window-evidence;
representative members; the committed window defaults), ONE labelled list (merge="none": per-origin blocks, also_in marks).

usage: measure_combined.py PRESET OUT.jsonl --cache DIR [--workers 10] [--ids all] [--kinds all] [--limit N] [--resume] [--check]
  PRESET  fast | standard | full | <nodes>   (the amount of inference of EVERY source: crosses per tier / layer bounds / windows)
  --cache the flat ordered cache directory (placements_*_{RUN,WORD,CHAR}_mid_ordered-forward.pkl); the window placements (slidewin_*.pkl) are
          loaded from the same directory, or placed once in the parent (workers = --workers) and written there.
Only corpus=fulllead rows of bank3.tsv (s3000 rows need an S3000 ordered cache that does not exist: skipped).
Record (one line per question): id, kind, question, gold, preset, ms, verdict, answer (CombinedAnswer.answer_obj(): header, blocks, entries with
block / origins / words / also_in, per_source_listed, sources, cited), agreement, head, load1, pid.  A failing question = {"id","error"}."""
import argparse, json, multiprocessing as mp, os, sys, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)
from verantyx.line3 import ask as A            # noqa: E402
from verantyx.line3 import slide_query as SQ   # noqa: E402

ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
ap.add_argument("preset")
ap.add_argument("out")
ap.add_argument("--cache", required=True)
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
BANK = os.path.join(ROOT, "experiments/line3/bank3/bank3.tsv")
G = {}


def _head():
    try:
        return open(os.path.join(ROOT, "PRO_HEAD")).read().strip()
    except OSError:
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
    c = A.ask(G["idx"], question, structure="combined", **kw)          # every other option = the committed default
    ms = int((time.monotonic() - t0) * 1000)
    return {"id": qid, "kind": kind, "question": question, "gold": gold, "preset": PRESET, "ms": ms, "verdict": c.verdict,
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
            if "error" not in r and r.get("preset") == PRESET:
                keep.append(r)
    return keep


if __name__ == "__main__":
    rows = [l.rstrip("\n").split("\t") for l in open(BANK, encoding="utf-8") if not l.startswith("#") and l.strip()]
    n_all = len(rows)
    rows = [r for r in rows if r[2] == "fulllead"]
    if ARGS.ids != "all":
        rows = [r for r in rows if r[0] in ARGS.ids.split(",")]
    if ARGS.kinds != "all":
        rows = [r for r in rows if r[1] in ARGS.kinds.split(",")]
    if ARGS.limit:
        rows = rows[:ARGS.limit]
    t0 = time.time()
    G["idx"], short = _open_index()
    G["head"] = _head()
    t1 = time.time()
    wi = SQ.window_index_for(G["idx"], workers=max(1, ARGS.workers))   # loads (or places once, parent) the windows; ask() finds it on the index
    print("index + flat cache load %.1fs; windows ready %.1fs (%d windows, z_deep %s); %s; %d of %d bank rows (fulllead); flat cache complete %s; "
          "workers %d; PYTHONHASHSEED=%s" % (t1 - t0, time.time() - t1, len(wi.windows), wi.z_deep, PRESET, len(rows), n_all, short, ARGS.workers,
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
        json.dump({"argv": sys.argv, "head": G["head"], "cache": CACHE, "cache_files": sorted(os.listdir(CACHE)), "data": DATA, "bank": BANK,
                   "started": time.strftime("%Y-%m-%d %H:%M:%S"), "resumed_ids": len(done), "pyhashseed": os.environ.get("PYTHONHASHSEED"),
                   "python": sys.version.split()[0], "window_corpus_sha256": wi.space.sha256(), "window_z_deep": wi.z_deep,
                   "window_slide_spec_sha256": wi.slide.spec.sha256(), "window_place_spec_sha256": wi.spec.sha256(),
                   "window_switches": wi.header.get("switches") if getattr(wi, "header", None) else None}, f, indent=1, default=str)
    print("%d to do, %d kept from an earlier run" % (len(todo), len(done)), file=sys.stderr, flush=True)
    if ARGS.workers <= 1:
        it = map(_work, todo)
    else:
        it = mp.get_context("fork").Pool(ARGS.workers).imap_unordered(_work, todo)     # the loaded indexes are inherited by fork
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
