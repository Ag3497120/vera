"""G3-h: bank2 questions of fulllead through the window-flat read (slide_flat.ask_flat) on ONE window cache of the G3-h grid
{arm_cap budget | x} x {z_deep slide | order | order_window} x {seat_empty_axis allow | deny}.  A descendant of g3/s1flat/measure_flat.py (same read, same
record, same scorer): the window index is loaded ONCE for the cell and the question runs (preset x evidence) are made one after the other on it.

usage: measure_h.py --cache DIR --arm-cap budget|x --z-deep slide|order|order_window --seat-empty allow|deny --out-dir DIR
                    [--runs fast:plain,fast:window,standard:plain,standard:window] [--workers 6] [--ids all] [--kinds intra2,unans] [--limit N]
                    [--resume] [--build] [--check]
  --cache   the window cache directory (the file name carries the slide and place spec shas, so one directory holds every cell; a file for another corpus /
            slide spec / place spec is REFUSED; without --build a missing file stops the run)
Output: DIR/h_<preset>_<cap>_<zdeep>_<seat>_<evidence>.jsonl (+ .meta.json): one line per question as measure_flat.py writes it (members = the first member of each
growth, search budget 512/64, both seats of a shared unit, read order qcount_first, the per-axis labels attached)."""
import argparse, hashlib, json, multiprocessing as mp, os, sys, time, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(HERE))))
sys.path.insert(0, ROOT)
from verantyx.line3 import cycle as cy        # noqa: E402
from verantyx.line3 import slide_flat as F    # noqa: E402
from verantyx.line3 import slide_place as SP  # noqa: E402
from verantyx.line3 import slide_query as Q   # noqa: E402

ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
ap.add_argument("--cache", required=True)
ap.add_argument("--arm-cap", default="budget", choices=list(SP.ARM_CAPS), dest="arm_cap")
ap.add_argument("--z-deep", default="slide", choices=list(Q.Z_DEEPS), dest="z_deep")
ap.add_argument("--seat-empty", default="allow", choices=list(SP.SEAT_EMPTY), dest="seat_empty")
ap.add_argument("--out-dir", required=True)
ap.add_argument("--runs", default="fast:plain,fast:window,standard:plain,standard:window")
ap.add_argument("--budget", default="512,64")
ap.add_argument("--workers", type=int, default=1)
ap.add_argument("--ids", default="all")
ap.add_argument("--kinds", default="intra2,unans")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--resume", action="store_true")
ap.add_argument("--check", action="store_true")
ap.add_argument("--build", action="store_true")
ARGS = ap.parse_args()
CACHE = os.path.expanduser(ARGS.cache)
DATA = os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl")
BANK = os.path.join(ROOT, "experiments/line3/bank2/bank2.tsv")
G = {}
_ms, _me = (int(x) for x in ARGS.budget.split(","))
CELL = "%s_%s_%s" % (ARGS.arm_cap, ARGS.z_deep, ARGS.seat_empty)


def config(evidence):
    return {"z_deep": ARGS.z_deep, "arm_cap": ARGS.arm_cap, "seat_empty_axis": ARGS.seat_empty, "members": "representative",
            "budget": [_ms, _me], "two_seat": "both", "read_order": "qcount_first", "strict": "abstain", "labels": True,
            "label_agreement": "three", "evidence": evidence}


def _head():
    try:
        import subprocess
        return subprocess.run(["git", "-C", ROOT, "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip() or None
    except Exception:
        return None


def _slim(e):
    lab = e.get("axis_labels")
    return {"window": e["window"]["n"], "wsids": e["window"]["sids"], "words": e["words"], "arrangements": e["arrangements"], "centres": e["centres"],
            "centre_sentence": e["centre_sentence"], "stable_strict": e["stable_strict"], "source_sids": e["source_sids"],
            "stability": e["stability"], "origin_members": len(e["origin_members"]), "members_read": e["members_read"], "class_size": e["class_size"],
            "starts": e["starts"], "trace_ok": e["trace"]["ok"], "constructed_edge_words": e["trace"]["constructed_edge_words"],
            "growth_members": e["growth_members"],
            "axes": None if lab is None else {a: [lab[a]["agreed"], lab[a]["of"], sorted(lab[a]["units"])] for a in lab}}


def _do(arg):
    preset, evidence, row = arg
    qid, kind, _c, subj, question, gold = row[:6]
    kw = {"nodes": int(preset)} if preset.isdigit() else {"effort": preset}
    t0 = time.monotonic()
    r = F.ask_flat(G["wi"], question, members="representative", strict="abstain", budget=cy.QueryBudget(_ms, _me), two_seat="both",
                   read_order="qcount_first", labels=True, label_agreement="three", evidence=evidence, **kw)
    ms = int((time.monotonic() - t0) * 1000)
    return {"id": qid, "kind": kind, "corpus": "fulllead", "question": question, "gold": gold, "preset": preset, "config": config(evidence),
            "head": G["head"], "pid": os.getpid(), "ms": ms, "verdict": r.verdict, "form": r.intake.form_obj(),
            "units": list(r.intake.units), "read": r.read_obj(), "abstention_counts": r.abstention_counts(),
            "windows": [{"n": x.window, "members": x.members_read, "class_size": x.class_size, "starts": x.starts, "ms": x.ms, "trace_ok": x.trace_ok,
                         "tally": dict(x.tally)} for x in r.reads],
            "entries": [_slim(e) for e in r.entries], "abstentions": list(r.abstentions),
            "load1": round(os.getloadavg()[0], 2)}


def _work(arg):
    try:
        return _do(arg)
    except Exception:                                        # one bad question must not end a sweep
        return {"id": arg[2][0], "error": traceback.format_exc()}


def _read_valid(path, preset, evidence):
    keep = []
    if os.path.exists(path):
        for l in open(path, encoding="utf-8"):
            try:
                r = json.loads(l)
            except ValueError:
                continue
            if "error" not in r and r.get("preset") == preset and r.get("config") == config(evidence):
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
    place_kw = {"arm_cap": ARGS.arm_cap, "seat_empty_axis": ARGS.seat_empty}
    G["wi"] = Q.WindowIndex.from_jsonl(DATA, CACHE, build=ARGS.build, workers=ARGS.workers, place_kw=place_kw,
                                       log=lambda m: print(m, file=sys.stderr, flush=True), z_deep=ARGS.z_deep)
    G["head"] = _head()
    wi = G["wi"]
    print("[%s] window index load %.1fs; %d windows; corpus %s slide %s place %s; %d questions; workers %d; PYTHONHASHSEED=%s"
          % (CELL, time.time() - t0, len(wi.windows), wi.space.sha256()[:12], wi.slide.spec.sha256()[:12], wi.spec.sha256()[:12], len(rows),
             ARGS.workers, os.environ.get("PYTHONHASHSEED")), file=sys.stderr, flush=True)
    if ARGS.check:
        print(" ".join(r[0] for r in rows))
        sys.exit(0)
    os.makedirs(ARGS.out_dir, exist_ok=True)
    for run in ARGS.runs.split(","):
        preset, evidence = run.split(":")
        OUT = os.path.join(ARGS.out_dir, "h_%s_%s_%s.jsonl" % (preset, CELL, evidence))
        t1 = time.time()
        done = _read_valid(OUT, preset, evidence) if ARGS.resume else []
        have = {r["id"] for r in done}
        todo = [r for r in rows if r[0] not in have]
        with open(OUT, "w", encoding="utf-8") as f:
            for r in done:
                f.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
        with open(OUT + ".meta.json", "w", encoding="utf-8") as f:
            json.dump({"argv": sys.argv, "head": G["head"], "cache": CACHE, "cache_file": [x for x in sorted(os.listdir(CACHE)) if x.startswith(
                           "slidewin_%s_RUN_%s_%s" % (wi.space.sha256()[:12], wi.slide.spec.sha256()[:12], wi.spec.sha256()[:12]))],
                       "data": DATA, "config": config(evidence), "preset": preset, "corpus_sha256": wi.space.sha256(),
                       "slide_spec_sha256": wi.slide.spec.sha256(), "place_spec_sha256": wi.spec.sha256(),
                       "window_cache_header": {k: v for k, v in wi.header.items() if k != "windows"},
                       "started": time.strftime("%Y-%m-%d %H:%M:%S"), "resumed_ids": len(done),
                       "pyhashseed": os.environ.get("PYTHONHASHSEED"), "python": sys.version.split()[0],
                       "code_sha256": {n: hashlib.sha256(open(os.path.join(ROOT, "verantyx/line3", n), "rb").read()).hexdigest()
                                       for n in ("slide_flat.py", "slide_query.py", "cycle.py", "readout.py", "trace_check.py", "slide_place.py",
                                                 "slide_ratios.py", "slide.py", "grammar.py")}},
                      f, indent=1, default=str)
        print("[%s %s %s] %d to do, %d kept from an earlier run" % (CELL, preset, evidence, len(todo), len(done)), file=sys.stderr, flush=True)
        args = [(preset, evidence, r) for r in todo]
        pool = None
        if ARGS.workers <= 1:
            it = map(_work, args)
        else:
            pool = mp.get_context("fork").Pool(ARGS.workers)         # the loaded index is inherited by fork
            it = pool.imap_unordered(_work, args)
        n = nerr = 0
        with open(OUT, "a", encoding="utf-8") as f:
            for rec in it:
                f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n"); f.flush(); n += 1
                if "error" in rec:
                    nerr += 1
                    print("%d/%d %s ERROR %s" % (n, len(todo), rec["id"], rec["error"].strip().splitlines()[-1]), file=sys.stderr, flush=True)
        if pool:
            pool.close(); pool.join()
        print("[%s %s %s] done %d (%d errors) in %.0fs; load %.1f" % (CELL, preset, evidence, n, nerr, time.time() - t1, os.getloadavg()[0]),
              file=sys.stderr, flush=True)
