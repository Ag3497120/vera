"""G3-e2: bank2 questions of fulllead through the question path over sliding windows with the three switches of the owner's decision after the S1
audit: `--answer-shape unit|path` (the end unit of the section walk, or the units of the walked path), `--read-order qcount_first|grammar_first`
(windows holding more question units first, or the grammar order first) and `--z-deep slide|order` (a placement switch, passed to
slide_query.WindowIndex.from_jsonl: another slide spec, another cache file).  A descendant of s1/measure_slide.py (via g3/c4/measure_c4.py, which
replaced slide.default_spec to reach z_deep: not needed any more).

usage: measure_e2.py PRESET OUT.jsonl --cache DIR [--z-deep slide|order] [--answer-shape unit|path] [--read-order qcount_first|grammar_first]
                        [--agreement three|two_if_single_edge] [--members all|representative] [--within qcount|none] [--hold seats|sentences]
                        [--standins off|on] [--strict abstain|mark] [--skip exact|none] [--place-kw JSON] [--workers 1] [--ids all] [--kinds all]
                        [--limit N] [--resume] [--check] [--build]
  PRESET  fast | standard | full | <nodes>   (windows read: 4 / 10 / unbounded)
  --cache the window cache directory (a file for another corpus / slide spec / place spec is REFUSED; without --build a missing file stops the run)
Records (one line per question): id, kind, question, gold, preset, config, head, load1, pid, ms, verdict, form, read, abstention_counts, entries (slim:
axis, unit, window, words, arrangements, centres, path_words, stable_strict, source_sids, ratios, trace).  Grading is summarize_e2.py's (t9/scorer.py)."""
import argparse, hashlib, json, multiprocessing as mp, os, sys, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)
from verantyx.line3 import slide_query as Q   # noqa: E402
from verantyx.line3 import slide as SL        # noqa: E402

ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
ap.add_argument("preset")
ap.add_argument("out")
ap.add_argument("--cache", required=True)
ap.add_argument("--z-deep", default="slide", choices=list(Q.Z_DEEPS), dest="z_deep")
ap.add_argument("--answer-shape", default="unit", choices=list(Q.ANSWER_SHAPES), dest="answer_shape")
ap.add_argument("--read-order", default="qcount_first", choices=list(Q.READ_ORDERS), dest="read_order")
ap.add_argument("--agreement", default="three", choices=["three", "two_if_single_edge"])
ap.add_argument("--members", default="all", choices=["all", "representative"])
ap.add_argument("--within", default="qcount", choices=["qcount", "none"])
ap.add_argument("--hold", default="seats", choices=["seats", "sentences"])
ap.add_argument("--standins", default="off", choices=["off", "on"])
ap.add_argument("--strict", default="abstain", choices=["abstain", "mark"])
ap.add_argument("--skip", default="exact", choices=["exact", "none"])
ap.add_argument("--place-kw", default="{}", help="JSON of slide_place.make_spec switches (default: the module's committed defaults)")
ap.add_argument("--workers", type=int, default=1)
ap.add_argument("--ids", default="all")
ap.add_argument("--kinds", default="intra2,unans")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--resume", action="store_true")
ap.add_argument("--check", action="store_true")
ap.add_argument("--build", action="store_true")
ARGS = ap.parse_args()
PRESET, OUT = ARGS.preset, ARGS.out
CACHE = os.path.expanduser(ARGS.cache)
DATA = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")
BANK = os.path.join(ROOT, "experiments/line3/bank2/bank2.tsv")
G = {}
CONFIG = {"z_deep": ARGS.z_deep, "answer_shape": ARGS.answer_shape, "read_order": ARGS.read_order, "agreement": ARGS.agreement, "members": ARGS.members, "within": ARGS.within, "hold": ARGS.hold, "standins": ARGS.standins,
          "strict": ARGS.strict, "skip": ARGS.skip, "place_kw": json.loads(ARGS.place_kw)}


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


def _slim(e):
    return {"axis": e["axis"], "unit": e["unit"], "window": e["window"]["n"], "wsids": e["window"]["sids"], "words": e["words"], "arrangements": e["arrangements"],
            "centres": e["centres"], "path_words": e["path_words"], "stable_strict": e["stable_strict"], "source_sids": e["source_sids"],
            "ratios": {k: (None if v is None else "%d/%d" % (v.numerator, v.denominator)) for k, v in e["ratios"].items()},
            "members_agreeing": e["members_agreeing"], "members_read": e["members_read"], "class_size": e["class_size"],
            "trace_ok": e["trace"]["ok"], "via_standin": e["via_standin"], "grounded": e["grounded"]}


def _do(row):
    qid, kind, _c, subj, question, gold = row[:6]
    kw = {"nodes": int(PRESET)} if PRESET.isdigit() else {"effort": PRESET}
    t0 = time.monotonic()
    r = Q.ask_slide(G["wi"], question, agreement=ARGS.agreement, members=ARGS.members, within=ARGS.within, hold=ARGS.hold,
                    standins=ARGS.standins, strict=ARGS.strict, skip=ARGS.skip,
                    answer_shape=ARGS.answer_shape, read_order=ARGS.read_order, **kw)
    ms = int((time.monotonic() - t0) * 1000)
    return {"id": qid, "kind": kind, "corpus": "fulllead", "question": question, "gold": gold, "preset": PRESET, "config": CONFIG,
            "head": G["head"], "pid": os.getpid(), "ms": ms, "verdict": r.verdict, "form": r.intake.form_obj(),
            "units": list(r.intake.units), "read": r.read_obj(), "abstention_counts": r.abstention_counts(),
            "windows": [{"n": x.window, "members": x.members_read, "ms": x.ms, "trace_ok": x.trace_ok} for x in r.reads],
            "entries": [_slim(e) for e in r.entries], "abstentions": list(r.abstentions),
            "load1": round(os.getloadavg()[0], 2)}


def _work(row):
    try:
        return _do(row)
    except Exception:                                        # one bad question must not end a sweep
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
    G["wi"] = Q.WindowIndex.from_jsonl(DATA, CACHE, place_kw=CONFIG["place_kw"], build=ARGS.build, workers=ARGS.workers,
                                       log=lambda m: print(m, file=sys.stderr, flush=True), z_deep=ARGS.z_deep)
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
        json.dump({"argv": sys.argv, "head": G["head"], "cache": CACHE, "cache_files": sorted(os.listdir(CACHE)), "data": DATA,
                   "config": CONFIG, "corpus_sha256": wi.space.sha256(), "slide_spec_sha256": wi.slide.spec.sha256(),
                   "place_spec_sha256": wi.spec.sha256(), "window_cache_header": {k: v for k, v in wi.header.items() if k != "windows"},
                   "started": time.strftime("%Y-%m-%d %H:%M:%S"), "resumed_ids": len(done),
                   "pyhashseed": os.environ.get("PYTHONHASHSEED"), "python": sys.version.split()[0],
                   "code_sha256": {n: hashlib.sha256(open(os.path.join(ROOT, "verantyx/line3", n), "rb").read()).hexdigest()
                                   for n in ("slide_query.py", "ask.py", "slide_place.py", "slide_ratios.py", "slide.py", "grammar.py")}},
                  f, indent=1, default=str)
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
            print("%d/%d %s %.1fs %s windows %d/%d entries %d load %.1f" % (n, len(todo), rec["id"], rec["ms"] / 1000, rec["verdict"],
                  rec["read"]["windows_read"], rec["read"]["candidate_windows"], len(rec["entries"]), rec["load1"]), file=sys.stderr, flush=True)
    print("done %d (%d errors) in %.0fs" % (n, nerr, time.time() - t0), file=sys.stderr)
