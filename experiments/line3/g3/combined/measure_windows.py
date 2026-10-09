"""G3-g: the LIVE window part of the combined list.  bank2 fulllead questions through slide_flat.ask_flat (the windows read as flat crosses, G3-f) with
the sources' per-word sentences on (`word_sources`), one evidence variant per run; the records hold everything combined.window_source_of needs to
rebuild the window source, so that summarize_combined.py can replay them through the combiner.  Descendant of g3/s1flat/measure_flat.py.

usage: measure_windows.py PRESET OUT.jsonl --cache DIR --evidence plain|window [--z-deep slide|order] [--members representative|all]
                          [--workers 1] [--ids all] [--kinds intra2,unans] [--limit N] [--resume] [--check]
  PRESET  fast | standard | full | <nodes>   (windows read: 4 / 10 / unbounded)
  --cache the window cache directory (the G3-c3 default placements, z_deep slide); a file for another corpus / slide spec / place spec is REFUSED; a
          missing file stops the run (this script never places windows)
Records (one line per question): id, kind, question, gold, preset, config, head, load1, pid, ms, verdict, read, abstentions, reads_trace, entries (the
FlatAnswer entry dicts, with word_sources), n_windows."""
import argparse, hashlib, json, multiprocessing as mp, os, sys, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)
from verantyx.line3 import slide_flat as F    # noqa: E402
from verantyx.line3 import slide_query as Q   # noqa: E402

ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
ap.add_argument("preset")
ap.add_argument("out")
ap.add_argument("--cache", required=True)
ap.add_argument("--evidence", required=True, choices=list(F.EVIDENCES))
ap.add_argument("--z-deep", default="slide", choices=list(Q.Z_DEEPS), dest="z_deep")
ap.add_argument("--members", default="representative", choices=list(F.MEMBERS))
ap.add_argument("--workers", type=int, default=1)
ap.add_argument("--ids", default="all")
ap.add_argument("--kinds", default="intra2,unans")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--resume", action="store_true")
ap.add_argument("--check", action="store_true")
ARGS = ap.parse_args()
PRESET, OUT = ARGS.preset, ARGS.out
CACHE = os.path.expanduser(ARGS.cache)
DATA = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")
BANK = os.path.join(ROOT, "experiments/line3/bank2/bank2.tsv")
CONFIG = {"z_deep": ARGS.z_deep, "members": ARGS.members, "evidence": ARGS.evidence, "read_order": "qcount_first", "word_sources": True}
G = {}


def _head():
    try:
        import subprocess
        return subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or None
    except Exception:
        return None


def _do(row):
    qid, kind, _c, subj, question, gold = row[:6]
    kw = {"nodes": int(PRESET)} if PRESET.isdigit() else {"effort": PRESET}
    t0 = time.monotonic()
    r = F.ask_flat(G["wi"], question, members=ARGS.members, evidence=ARGS.evidence, word_sources=True, **kw)
    ms = int((time.monotonic() - t0) * 1000)
    return {"id": qid, "kind": kind, "corpus": "fulllead", "question": question, "gold": gold, "preset": PRESET, "config": CONFIG,
            "head": G["head"], "pid": os.getpid(), "ms": ms, "verdict": r.verdict, "read": r.read_obj(), "n_windows": len(r.reads),
            "reads_trace": [[x.trace_checks, bool(x.trace_ok), bool(x.entries)] for x in r.reads],
            "entries": list(r.entries), "abstentions": list(r.abstentions), "load1": round(os.getloadavg()[0], 2)}


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
                continue
            if "error" not in r and r.get("preset") == PRESET and r.get("config") == CONFIG:
                keep.append(r)
    return keep


if __name__ == "__main__":
    rows = [l.rstrip("\n").split("\t") for l in open(BANK, encoding="utf-8") if not l.startswith("#") and l.strip()]
    rows = [r for r in rows if r[2] == "fulllead"]
    if ARGS.ids != "all":
        rows = [r for r in rows if r[0] in ARGS.ids.split(",")]
    if ARGS.kinds != "all":
        rows = [r for r in rows if r[1] in ARGS.kinds.split(",")]
    if ARGS.limit:
        rows = rows[:ARGS.limit]
    t0 = time.time()
    G["wi"] = Q.WindowIndex.from_jsonl(DATA, CACHE, build=False, z_deep=ARGS.z_deep)
    G["head"] = _head()
    wi = G["wi"]
    print("window index load %.1fs; %d windows; corpus %s slide %s place %s; %d questions; workers %d; PYTHONHASHSEED=%s"
          % (time.time() - t0, len(wi.windows), wi.space.sha256()[:12], wi.slide.spec.sha256()[:12], wi.spec.sha256()[:12], len(rows),
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
    with open(OUT + ".meta.json", "w", encoding="utf-8") as f:
        json.dump({"argv": sys.argv, "head": G["head"], "cache": CACHE, "cache_files": sorted(os.listdir(CACHE)), "data": DATA, "config": CONFIG,
                   "corpus_sha256": wi.space.sha256(), "slide_spec_sha256": wi.slide.spec.sha256(), "place_spec_sha256": wi.spec.sha256(),
                   "started": time.strftime("%Y-%m-%d %H:%M:%S"), "resumed_ids": len(done), "pyhashseed": os.environ.get("PYTHONHASHSEED"),
                   "python": sys.version.split()[0],
                   "code_sha256": {n: hashlib.sha256(open(os.path.join(ROOT, "verantyx/line3", n), "rb").read()).hexdigest()
                                   for n in ("combined.py", "slide_flat.py", "slide_query.py", "cycle.py", "readout.py", "trace_check.py",
                                             "slide_place.py", "slide_ratios.py", "slide.py", "grammar.py")}}, f, indent=1, default=str)
    print("%d to do, %d kept from an earlier run" % (len(todo), len(done)), file=sys.stderr, flush=True)
    it = map(_work, todo) if ARGS.workers <= 1 else mp.get_context("fork").Pool(ARGS.workers).imap_unordered(_work, todo)
    n = nerr = 0
    with open(OUT, "a", encoding="utf-8") as f:
        for rec in it:
            f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n"); f.flush(); n += 1
            if "error" in rec:
                nerr += 1
                print("%d/%d %s ERROR %s" % (n, len(todo), rec["id"], rec["error"].strip().splitlines()[-1]), file=sys.stderr, flush=True)
                continue
            print("%d/%d %s %.1fs %s windows %d entries %d load %.1f" % (n, len(todo), rec["id"], rec["ms"] / 1000, rec["verdict"],
                  rec["n_windows"], len(rec["entries"]), rec["load1"]), file=sys.stderr, flush=True)
    print("done %d (%d errors) in %.0fs" % (n, nerr, time.time() - t0), file=sys.stderr)
