#!/usr/bin/env python3
"""G4-d: gate G-2 (docs/LINE3_G4_GROWTH_METER.md 9 ticket 7, L-G4-32): build the frozen stacks of the 300 fulllead articles and measure how many
crosses close early, before any question runs.

  build    arm A (foundation ON, tiers RUN/WORD/CHAR, level mid, order forward): `stack.extend` article by article (steps.json order), one jsonl
           line per step (every step, all tiers), a snapshot (`stack.save`) at each of the 66 measured steps, resumable.
  check-b  arm B (CHAR only, dictionary-free): a CHAR-only stack of the first N articles built in a process in which fugashi / unidic_lite
           cannot be imported, compared (state_sha256, ledger sha256, state bytes) with the CHAR tier of arm A's snapshot at step N.
  fold     T-G4-4 (the "no lookahead" half): a stack built from prefix_k alone (steps.py prefix(k) bytes), in this process (run it with another
           PYTHONHASHSEED than the build), against the step-k snapshot of the cache (`stack.load` recomputes its identities).
  report   gate2_A.md from the jsonl.

  PYTHONPATH=<worktree> PYTHONHASHSEED=0 python experiments/line3/g4/gate2_build.py build --cache /Users/motonisihikoudai/Projects/vera-impl/cache/g4_stack_A
  python gate2_build.py check-b --cache <A> [--articles 8]
  PYTHONHASHSEED=1 python gate2_build.py fold --cache <A> --k 13 [--workers 2]
  python gate2_build.py report

Never opens vera-impl/hidden.  No network.  The seconds are out of band (never in a state or a ledger byte).
"""
import argparse
import importlib.util
import json
import os
import resource
import signal
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, ROOT)

from verantyx.line3 import placement as pl            # noqa: E402
from verantyx.line3 import space as sp                # noqa: E402
from verantyx.line3 import stack as st                # noqa: E402

DATA = os.path.join(ROOT, "experiments", "line3", "bank2", "data", "fulllead_sents.jsonl")
RESULTS = os.path.join(HERE, "results")
CACHE_A = "/Users/motonisihikoudai/Projects/vera-impl/cache/g4_stack_A"
CACHE_B = "/Users/motonisihikoudai/Projects/vera-impl/cache/g4_stack_B"
TIERS = sp.TIERS
FOUNDATION, LEVEL, ORDER = "on", "mid", "forward"
REASONS = st.CLOSE_REASONS


# ------------------------------------------------------------------------------------------------------------------------------
# steps.py (a script, not a package) and the documents
# ------------------------------------------------------------------------------------------------------------------------------
def load_steps_module():
    spec = importlib.util.spec_from_file_location("g4_steps", os.path.join(HERE, "steps.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def prefix_function():
    """steps.py prefix(k) -> (sha256, bytes), built from its own loader (steps.main() is not called: it rewrites steps.json)."""
    m = load_steps_module()
    rows, article_list, _cum = m.load_fulllead_sentences()
    return m.create_prefix_writer(rows, article_list, {t: i for i, t in enumerate(article_list)}), article_list


def rusage():
    a, b = resource.getrusage(resource.RUSAGE_SELF), resource.getrusage(resource.RUSAGE_CHILDREN)
    return a.ru_utime + a.ru_stime + b.ru_utime + b.ru_stime, max(a.ru_maxrss, b.ru_maxrss) / (1024.0 ** 3)     # macOS: bytes


def median(xs):
    return statistics.median(xs) if xs else None


# ------------------------------------------------------------------------------------------------------------------------------
# one record per step
# ------------------------------------------------------------------------------------------------------------------------------
def tier_record(prev: "st.StackState", state: "st.StackState", tier: str, stats_tier: dict, max_class: int) -> dict:
    """Everything one tier says about one step: ledger entry of the step + the state after it (+ the state before it for what was frozen)."""
    e = json.loads(state.ledger[tier][-1])
    step = state.step
    cr, old = state.crosses[tier], prev.crosses[tier]
    total = len(cr)
    carried = len(old)                                                    # crosses that existed before this step
    opened = len(e["opened"])
    assert total - carried == opened
    clo = e["closed"]
    c_birth = [c for c in clo if c["at"] == "birth"]
    c_grow = [c for c in clo if c["at"] == "grow"]
    by_reason = {r: sum(1 for c in clo if c["reason"] == r) for r in REASONS}
    by_reason_birth = {r: sum(1 for c in c_birth if c["reason"] == r) for r in REASONS}
    closed_all = [c for c in cr.values() if c.closed]
    closed_birth_cum = sum(1 for c in closed_all if c.closed_at == c.opened_at)
    grown = e["grown"]
    fills = sum(len(g["filled"]) for g in grown)
    changed = [g for g in grown if g["arr"][0] != g["arr"][1]]            # 充填 or 絞り (arr_sha moved)
    narrowed = [g for g in grown if g["narrowed"]]
    d_new = sum(g["dropped_new"] for g in grown)
    d_rec = sum(g["dropped_recount"] for g in grown)
    old_seats = new_seats = 0
    for g in grown:
        old_seats += len(old[g["seed"]].seated)
        new_seats += len(cr[g["seed"]].seated)
    rearranged_carried = len(changed)                                     # carried crosses whose arr_sha moved
    sizes_all = [len(c.seated) for c in cr.values()]
    sizes_closed = [len(c.seated) for c in closed_all]
    classes = [len(c.members) for c in cr.values()]
    left_after_units = sum(e["left_after"].values())
    seats_birth = sum(1 for s in e["seats"] if s["kind"] == st.BIRTH)
    seats_fill = sum(1 for s in e["seats"] if s["kind"] == st.FILL)
    n_open = total - len(closed_all)
    return {
        "crosses": total, "carried": carried, "opened": opened, "touched": e["touched"], "unchanged": e["unchanged"],
        "closed_step": len(clo), "closed_birth": len(c_birth), "closed_grow": len(c_grow),
        "closed_reason": by_reason, "closed_reason_birth": by_reason_birth,
        "cum_closed": len(closed_all), "cum_closed_birth": closed_birth_cum, "cum_closed_later": len(closed_all) - closed_birth_cum,
        "cum_open": n_open, "cum_closed_share": len(closed_all) / total if total else None,
        "cum_closed_birth_share": closed_birth_cum / total if total else None,
        "cum_closed_reason": {r: sum(1 for c in closed_all if c.closed_reason == r) for r in REASONS},
        "grown": len(grown), "grown_filled": sum(1 for g in grown if g["filled"]), "fills": fills,
        "narrowed": len(narrowed), "narrowed_new": sum(1 for g in grown if g["dropped_new"]), "narrowed_recount": sum(1 for g in grown if g["dropped_recount"]),
        "dropped": sum(g["dropped"] for g in grown), "dropped_new": d_new, "dropped_recount": d_rec,
        "rearranged_carried": rearranged_carried,
        "frozen_share": (carried - rearranged_carried) / carried if carried else None,       # carried crosses with arr_sha unchanged
        "frozen_seat_share": old_seats / new_seats if new_seats else None,                   # grown crosses: seats held before the step / after it
        "left_after_crosses": len(e["left_after"]), "left_after_units": left_after_units,
        "seats_birth": seats_birth, "seats_fill": seats_fill,
        "size_median": median(sizes_all), "size_max": max(sizes_all) if sizes_all else None,
        "size_closed_median": median(sizes_closed), "class_median": median(classes), "class_max": max(classes) if classes else None,
        "class_over_90pct_max": sum(1 for n in classes if n > 0.9 * max_class),
        "tasks": stats_tier.get("tasks"), "tasks_open": stats_tier.get("open"), "tasks_grow": stats_tier.get("grow"), "tasks_left": stats_tier.get("left"),
        "pool_wall_s": round(stats_tier.get("wall_s", 0.0), 2),
        "cpu_open_s": round(stats_tier.get("cpu_open_s", 0.0), 2), "cpu_grow_s": round(stats_tier.get("cpu_grow_s", 0.0), 2),
        "cpu_left_s": round(stats_tier.get("cpu_left_s", 0.0), 2),
        "state_sha256": state.shas[tier],
    }


# ------------------------------------------------------------------------------------------------------------------------------
# build
# ------------------------------------------------------------------------------------------------------------------------------
def dir_bytes(paths):
    return sum(os.path.getsize(p) for p in paths if os.path.exists(p))


def saved_files(root, state):
    d = st._cfg_dir(root, state.foundation, state.level, state.order)
    p12 = state.prefix_sha256[:12]
    out = [os.path.join(d, "docs_%s.jsonl" % p12), os.path.join(d, "manifest.jsonl")]
    for t in state.tier_names:
        out += [os.path.join(d, "%s_state_%s.jsonl.gz" % (t, p12)), os.path.join(d, "%s_ledger_%s.jsonl" % (t, p12))]
    return out


def cmd_build(a):
    os.makedirs(RESULTS, exist_ok=True)
    stepsj = json.load(open(os.path.join(HERE, "steps.json"), encoding="utf-8"))
    measured = set(stepsj["measured_steps"])
    fib = set(stepsj["fibonacci_steps"])
    docs = st.load_docs(DATA)
    assert len(docs) == stepsj["num_articles"] == 300, len(docs)
    assert [st.doc_title(d) for d in docs] == [x["title"] for x in stepsj["articles"]], "document order differs from steps.json"
    prefix, _ = prefix_function()
    for k in sorted(fib):                                                 # the prefix key is steps.py prefix(k)[0] (L-G4-60)
        assert st.prefix_sha256(docs[:k]) == prefix(k)[0], "prefix sha of %d differs from steps.py" % k
    upto = min(a.upto, len(docs))
    tag = a.tag
    jpath = os.path.join(a.out_dir, "gate2_%s.jsonl" % tag)
    rows = []
    state = None
    if a.resume and os.path.exists(os.path.join(st._cfg_dir(a.cache, FOUNDATION, LEVEL, ORDER), "manifest.jsonl")):
        mp_ = os.path.join(st._cfg_dir(a.cache, FOUNDATION, LEVEL, ORDER), "manifest.jsonl")
        ents = [json.loads(l) for l in open(mp_, encoding="utf-8").read().splitlines() if l.strip()]
        cand = sorted((e["step"] for e in ents if set(e["tiers"]) >= set(TIERS) and e["step"] <= upto), reverse=True)
        old_rows = [json.loads(l) for l in open(jpath, encoding="utf-8").read().splitlines() if l.strip()] if os.path.exists(jpath) else []
        have = {r["step"] for r in old_rows}
        for s in cand:
            if all(i in have for i in range(1, s + 1)):
                state = st.load(a.cache, prefix(s)[0], FOUNDATION, TIERS, LEVEL, ORDER)
                rows = [r for r in old_rows if r["step"] <= s]
                print("RESUME from step %d (%d rows kept of %d)" % (s, len(rows), len(old_rows)), flush=True)
                break
    if state is None:
        state = st.empty_state(FOUNDATION, TIERS, LEVEL, ORDER)
    with open(jpath, "w", encoding="utf-8") as f:                         # rewrite what is kept (rows beyond the resume point are dropped)
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    stop = {"flag": False}
    main_pid = os.getpid()

    def on_signal(signum, _frame):
        if os.getpid() != main_pid:                                      # a fork-pool worker inherits the handler: Pool.terminate() must still kill it
            os._exit(1)
        stop["flag"] = True

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    max_class = pl.budget_level(LEVEL).max_class
    wall_before = sum(r["wall_s"] for r in rows)
    t_start = time.time()
    c_start, _ = rusage()
    saved_bytes = 0
    save_mode = a.save
    print("build: tiers=%s foundation=%s level=%s workers=%d upto=%d save=%s from step %d  load1=%.1f" % (
        ",".join(TIERS), FOUNDATION, LEVEL, a.workers, upto, save_mode, state.step, os.getloadavg()[0]), flush=True)
    reason_stop = None
    while state.step < upto:
        doc = docs[state.step]
        stats = {}
        prev = state
        c0, _ = rusage()
        t0 = time.time()
        state = st.extend(prev, doc, a.workers, stats)
        wall = time.time() - t0
        cpu, rss = rusage()
        cpu -= c0
        step = state.step
        row = {"step": step, "title": st.doc_title(doc), "sentences": len(doc), "sent_cum": sum(len(d) for d in state.lines),
               "measured": step in measured, "fibonacci": step in fib, "wall_s": round(wall, 2), "cpu_s": round(cpu, 2),
               "cpu_main_s": round(stats["cpu_main_s"], 2), "maxrss_gb": round(rss, 2), "tiers": {}}
        for t in TIERS:
            row["tiers"][t] = tier_record(prev, state, t, stats["tiers"][t], max_class)
        row["cpu_tasks_s"] = round(sum(r["cpu_open_s"] + r["cpu_grow_s"] + r["cpu_left_s"] for r in row["tiers"].values()), 2)
        want_save = save_mode != "none" and ((save_mode == "measured" and step in measured) or step in fib or (save_mode == "all"))
        elapsed = wall_before + (time.time() - t_start)
        capped = a.max_wall_h and elapsed > a.max_wall_h * 3600
        if stop["flag"] or capped or step == upto:
            want_save = True                                              # a resume point / the last state, even if not a measured step
            row["resume_point"] = True
            reason_stop = "SIGTERM/SIGINT" if stop["flag"] else ("wall cap %.1f h" % a.max_wall_h if capped else None)
        if want_save:
            ts0 = time.time()
            st.save(state, a.cache)
            saved_bytes += dir_bytes([p for p in saved_files(a.cache, state) if not p.endswith("manifest.jsonl")])
            row["saved"] = True
            row["save_s"] = round(time.time() - ts0, 1)
            if save_mode == "measured" and saved_bytes > a.max_cache_gb * 1e9:
                save_mode = "fib"
                print("!! cache above %.0f GB: from here only the Fibonacci steps are saved" % a.max_cache_gb, flush=True)
        with open(jpath, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
        rows.append(row)
        parts = []
        for t in TIERS:
            r = row["tiers"][t]
            parts.append("%s %d (+%d) cl %d/%d g %d fill %d nar %d cum %.1f%%" % (
                t, r["crosses"], r["opened"], r["closed_birth"], r["closed_grow"], r["grown"], r["fills"], r["narrowed"],
                100.0 * r["cum_closed_share"]))
        print("step %3d %-14s sent %2d wall %7.1f cpu %7.1f rss %.1fG %s| %s%s" % (
            step, row["title"][:14], row["sentences"], wall, cpu, rss, "SAVED " if row.get("saved") else "", " | ".join(parts),
            "  [measured]" if row["measured"] else ""), flush=True)
        if reason_stop:
            print("STOP (%s) at step %d; state saved as a resume point" % (reason_stop, step), flush=True)
            break
    wall_all = time.time() - t_start
    cpu_all = rusage()[0] - c_start
    print("DONE step %d  wall %.1f s  cpu %.1f s (this invocation)  saved_bytes %.2f GB  stop=%s" % (
        state.step, wall_all, cpu_all, saved_bytes / 1e9, reason_stop), flush=True)
    with open(os.path.join(a.out_dir, "gate2_%s_tail.json" % tag), "w", encoding="utf-8") as f:
        json.dump({"step": state.step, "stop": reason_stop, "wall_s": round(wall_all, 1), "cpu_s": round(cpu_all, 1),
                   "saved_bytes": saved_bytes, "state_sha256": dict(state.shas), "workers": a.workers,
                   "ledger_sha256": {t: state.ledger_sha256(t) for t in TIERS}}, f, indent=1)
    return 0


# ------------------------------------------------------------------------------------------------------------------------------
# arm B: CHAR only, dictionary-free
# ------------------------------------------------------------------------------------------------------------------------------
CHAR_PROG = """
import sys, json
for m in ("fugashi", "unidic_lite", "unidic"):
    sys.modules[m] = None
from verantyx.line3 import stack as st
a = json.loads(sys.stdin.read())
docs = st.load_docs(a["data"])[:a["n"]]
s = st.build(docs, foundation="on", tiers=("CHAR",), level=a["level"], workers=a["workers"], save_root=a["root"], save_steps=[a["n"]])
assert not any(m in sys.modules and sys.modules[m] is not None for m in ("fugashi", "unidic_lite"))
print(json.dumps({"sha": s.shas["CHAR"], "step": s.step, "ledger": s.ledger_sha256("CHAR"), "prefix": s.prefix_sha256,
                  "state_bytes_sha": __import__("hashlib").sha256(s.state_bytes("CHAR")).hexdigest()}))
"""


def cmd_check_b(a):
    n = a.articles
    os.makedirs(a.b_cache, exist_ok=True)
    t0 = time.time()
    out = subprocess.run([sys.executable, "-c", CHAR_PROG], input=json.dumps({"data": DATA, "n": n, "level": LEVEL, "workers": a.workers,
                                                                              "root": a.b_cache}),
                         cwd=ROOT, capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED="0"))
    if out.returncode != 0:
        print(out.stderr)
        return 1
    got = json.loads(out.stdout.strip().splitlines()[-1])
    wall = time.time() - t0
    prefix, _ = prefix_function()
    sha = prefix(n)[0]
    A = st.load(a.cache, sha, FOUNDATION, TIERS, LEVEL, ORDER)
    import hashlib
    res = {"articles": n, "prefix_sha256": sha, "b_state_sha256": got["sha"], "a_char_state_sha256": A.shas["CHAR"],
           "b_ledger_sha256": got["ledger"], "a_char_ledger_sha256": A.ledger_sha256("CHAR"),
           "state_bytes_equal": got["state_bytes_sha"] == hashlib.sha256(A.state_bytes("CHAR")).hexdigest(),
           "wall_s": round(wall, 1), "b_built_with_fugashi_unidic_lite_blocked": True}
    res["equal"] = (res["b_state_sha256"] == res["a_char_state_sha256"] and res["b_ledger_sha256"] == res["a_char_ledger_sha256"]
                    and res["state_bytes_equal"] and got["prefix"] == sha)
    # B's own CHAR-only snapshot, loaded back (no dictionary): the loader must accept it with tiers=("CHAR",) and give the same identity
    B = st.load(a.b_cache, sha, FOUNDATION, ("CHAR",), LEVEL, ORDER)
    res["b_snapshot_reload_equal"] = B.shas["CHAR"] == A.shas["CHAR"]
    # A's cache serves B: load with tiers=("CHAR",) from A's manifest
    A_char = st.load(a.cache, sha, FOUNDATION, ("CHAR",), LEVEL, ORDER)
    res["a_cache_served_with_tiers_CHAR_equal"] = A_char.shas["CHAR"] == A.shas["CHAR"]
    print(json.dumps(res, indent=1))
    with open(os.path.join(a.out_dir, "gate2_B_check.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    return 0 if res["equal"] else 2


# ------------------------------------------------------------------------------------------------------------------------------
# fold (T-G4-4): a stack from prefix_k alone == the step-k snapshot
# ------------------------------------------------------------------------------------------------------------------------------
def cmd_fold(a):
    k = a.k
    prefix, _ = prefix_function()
    sha, content = prefix(k)
    scratch = os.path.join(a.scratch, "prefix_%d.jsonl" % k)
    os.makedirs(a.scratch, exist_ok=True)
    with open(scratch, "wb") as f:
        f.write(content)
    docs = st.load_docs(scratch)                                          # from the prefix FILE alone, no row of a later article
    assert len(docs) == k and st.prefix_sha256(docs) == sha
    t0 = time.time()
    c0, _ = rusage()
    alone = st.build(docs, FOUNDATION, TIERS, LEVEL, workers=a.workers, order=ORDER)
    wall, cpu = time.time() - t0, rusage()[0] - c0
    snap = st.load(a.cache, sha, FOUNDATION, TIERS, LEVEL, ORDER)         # recomputes the identities: an integrity check of the cache file
    res = {"k": k, "prefix_sha256": sha, "pythonhashseed": os.environ.get("PYTHONHASHSEED"), "wall_s": round(wall, 1), "cpu_s": round(cpu, 1),
           "workers": a.workers, "tiers": {}}
    ok = True
    for t in TIERS:
        r = {"state_sha256_alone": alone.shas[t], "state_sha256_snapshot": snap.shas[t],
             "state_bytes_equal": alone.state_bytes(t) == snap.state_bytes(t), "ledger_equal": alone.ledger[t] == snap.ledger[t],
             "ledger_bytes": sum(len(x) + 1 for x in snap.ledger[t])}
        r["equal"] = r["state_sha256_alone"] == r["state_sha256_snapshot"] and r["state_bytes_equal"] and r["ledger_equal"]
        ok &= r["equal"]
        res["tiers"][t] = r
    ok &= alone.prefix_sha256 == snap.prefix_sha256 == sha and alone.titles == snap.titles
    res["equal"] = ok
    print(json.dumps(res, indent=1))
    with open(os.path.join(a.out_dir, "gate2_fold_k%d.json" % k), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    return 0 if ok else 2


def cmd_resume_check(a):
    """The other half of T-G4-4: load the snapshot of step k (written by the build process), extend with the next article(s) in THIS process
    (another hash seed) up to the next saved step, and compare with that snapshot."""
    stepsj = json.load(open(os.path.join(HERE, "steps.json"), encoding="utf-8"))
    docs = st.load_docs(DATA)
    prefix, _ = prefix_function()
    k, j = a.k, a.to
    s = st.load(a.cache, prefix(k)[0], FOUNDATION, TIERS, LEVEL, ORDER)
    t0 = time.time()
    for i in range(k, j):
        s = st.extend(s, docs[i], a.workers)
    wall = time.time() - t0
    ref = st.load(a.cache, prefix(j)[0], FOUNDATION, TIERS, LEVEL, ORDER)
    res = {"from": k, "to": j, "pythonhashseed": os.environ.get("PYTHONHASHSEED"), "wall_s": round(wall, 1), "tiers": {}}
    ok = True
    for t in TIERS:
        r = {"state_sha256_extended": s.shas[t], "state_sha256_snapshot": ref.shas[t], "state_bytes_equal": s.state_bytes(t) == ref.state_bytes(t),
             "ledger_equal": s.ledger[t] == ref.ledger[t]}
        r["equal"] = r["state_sha256_extended"] == r["state_sha256_snapshot"] and r["state_bytes_equal"] and r["ledger_equal"]
        ok &= r["equal"]
        res["tiers"][t] = r
    res["equal"] = ok
    print(json.dumps(res, indent=1))
    with open(os.path.join(a.out_dir, "gate2_resume_k%d_to%d.json" % (k, j)), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1)
    return 0 if ok else 2


# ------------------------------------------------------------------------------------------------------------------------------
# report
# ------------------------------------------------------------------------------------------------------------------------------
def pct(x, d=1):
    return "-" if x is None else ("%." + str(d) + "f") % (100.0 * x)


def fnum(x, d=1):
    return "-" if x is None else ("%." + str(d) + "f") % x


def hms(s):
    s = int(round(s))
    return "%d h %02d min %02d s" % (s // 3600, (s % 3600) // 60, s % 60)


def read_json(path):
    return json.load(open(path, encoding="utf-8")) if os.path.exists(path) else None


def cmd_report(a):
    jpath = os.path.join(a.out_dir, "gate2_%s.jsonl" % a.tag)
    rows = [json.loads(l) for l in open(jpath, encoding="utf-8").read().splitlines() if l.strip()]
    last = rows[-1]
    stepsj = json.load(open(os.path.join(HERE, "steps.json"), encoding="utf-8"))
    out = []
    w = out.append
    wall = sum(r["wall_s"] for r in rows)
    cpu = sum(r["cpu_s"] for r in rows)
    reached = last["step"]
    fib_reached = max([r["step"] for r in rows if r["fibonacci"]] or [0])
    w("# Gate G-2 (G4-d): the stack of fulllead, arm A -- how many crosses close early\n")
    w("Arm A = foundation ON, tiers RUN / WORD / CHAR, level mid, order forward (steps.json), `stack.extend` article by article, quotient off, "
      "`group_insert=ordered`, `on_collapse=stop`, PYTHONHASHSEED=0, 4 workers. Built by `experiments/line3/g4/gate2_build.py build`; the numbers below "
      "are computed from the ledger entry and the state of every step (`gate2_%s.jsonl`, one line per step, every step)." % a.tag)
    w("\n- Steps built: **%d of %d** articles (%d sentences); Fibonacci steps reached: up to %d; measured steps in this table: %d of %d."
      % (reached, stepsj["num_articles"], last["sent_cum"], fib_reached, sum(1 for r in rows if r["measured"]), stepsj["num_measured_steps"]))
    w("- Cost of the pass (sum over the steps): wall **%s** (%d s), CPU **%s** (%d s; getrusage self + children, %.1f cores on average); maximum RSS of the driver %.1f GB."
      % (hms(wall), wall, hms(cpu), cpu, cpu / wall if wall else 0, max(r["maxrss_gb"] for r in rows)))
    w("- Per-step wall: median %.1f s, max %.1f s (step %d)." % (statistics.median(r["wall_s"] for r in rows), max(r["wall_s"] for r in rows),
                                                              max(rows, key=lambda r: r["wall_s"])["step"]))
    w("\n## Definitions\n")
    w("- **closed** = the cross hit its first budget collapse (`max_class` 1000, `max_states` 20000, `max_moves` 400000 at level mid) and stays closed for good (N-05). "
      "**closed at birth** = `closed_at == opened_at` (the one-shot build of the unit's cross collapsed); **closed later** = closed while being grown, at a step after its birth.")
    w("- **cum closed share** = closed crosses / all crosses of the prefix (cumulative, at the end of the step); **at-birth share** = crosses closed at birth / all crosses.")
    w("- **grown** = open crosses whose seed is in the document and which had a candidate to seat (`grown[]` of the ledger); **fills** = units seated into them (充填); "
      "**narrowed** = crosses with at least one member of the old class without a descendant (絞り); **dropped** = such members, split by `dropped_split` (L-G4-70) into "
      "*new* (dropped by the new units) and *recount* (the member's key fell behind under the new counts before any unit was seated).")
    w("- **frozen share** (the plan does not define it; this report defines two, both per step): (1) `frozen_share` = of the crosses that existed before the step, the share whose "
      "`arr_sha` did not change in the step (no 充填, no 絞り); (2) `frozen seats` = for the crosses grown in the step, the units seated before the step / the units seated after it "
      "(the share of the seats the step had to keep). A closed cross is frozen for good; the closed share is a separate column.")
    w("- CPU per step = getrusage (self + children) delta; wall = the `extend` call (space rebuild, adhesion, the three tiers one after the other, the snapshot is not in it).")
    # ---- headline
    w("\n## Headline\n")
    w("| tier | crosses | closed | closed share | closed at birth | at-birth share of all crosses | at-birth share of the closed | closed later | open |")
    w("|---|---|---|---|---|---|---|---|---|")
    for t in TIERS:
        r = last["tiers"][t]
        w("| %s | %d | %d | %s %% | %d | %s %% | %s %% | %d | %d |" % (t, r["crosses"], r["cum_closed"], pct(r["cum_closed_share"]), r["cum_closed_birth"],
                                                                    pct(r["cum_closed_birth_share"]), pct(r["cum_closed_birth"] / r["cum_closed"] if r["cum_closed"] else None),
                                                                    r["cum_closed_later"], r["cum_open"]))
    tot = {k: sum(last["tiers"][t][k] for t in TIERS) for k in ("crosses", "cum_closed", "cum_closed_birth", "cum_closed_later", "cum_open")}
    w("| all | %d | %d | %s %% | %d | %s %% | %s %% | %d | %d |" % (tot["crosses"], tot["cum_closed"], pct(tot["cum_closed"] / tot["crosses"]), tot["cum_closed_birth"],
                                                                  pct(tot["cum_closed_birth"] / tot["crosses"]), pct(tot["cum_closed_birth"] / tot["cum_closed"]),
                                                                  tot["cum_closed_later"], tot["cum_open"]))
    w("\nBy reason at step %d (cumulative, closed crosses): " % reached + "; ".join(
        "%s %s" % (t, ", ".join("%s %d" % (k, v) for k, v in last["tiers"][t]["cum_closed_reason"].items())) for t in TIERS) + ".")
    w("\nReference (not the same thing: the one-shot F1 build, foundation ON, quotient ON, the whole corpus, from `gate1_full_report.txt`, G-1): crosses stopped by the budget RUN 2038 of 3653 (55.8 %%), "
      "WORD 2542 of 3557 (71.5 %%), CHAR 926 of 1358 (68.2 %%); the same builds with the foundation OFF (f1b caches) 52.4 %%, 68.0 %%, 72.8 %%. The stack (quotient off, L-G4-25) at step %d closes %s / %s / %s %%." % (
          reached, pct(last["tiers"]["RUN"]["cum_closed_share"]), pct(last["tiers"]["WORD"]["cum_closed_share"]), pct(last["tiers"]["CHAR"]["cum_closed_share"])))
    w("Growth over the whole pass (sum of the steps): " + "; ".join(
        "%s grown %d, fills %d, narrowed %d (new %d / recount %d crosses), dropped members %d (new %d / recount %d)" % (
            t, sum(r["tiers"][t]["grown"] for r in rows), sum(r["tiers"][t]["fills"] for r in rows), sum(r["tiers"][t]["narrowed"] for r in rows),
            sum(r["tiers"][t]["narrowed_new"] for r in rows), sum(r["tiers"][t]["narrowed_recount"] for r in rows), sum(r["tiers"][t]["dropped"] for r in rows),
            sum(r["tiers"][t]["dropped_new"] for r in rows), sum(r["tiers"][t]["dropped_recount"] for r in rows)) for t in TIERS) + ".")
    w("Seats taken over the whole pass: " + "; ".join("%s births %d, fills %d" % (t, sum(r["tiers"][t]["seats_birth"] for r in rows), sum(r["tiers"][t]["seats_fill"] for r in rows)) for t in TIERS) + ".")
    # ---- is growth exercised at all? (from the final snapshot of the cache)
    try:
        docs = st.load_docs(DATA)
        fin = st.load(a.cache, st.prefix_sha256(docs[:reached]), FOUNDATION, TIERS, LEVEL, ORDER)
    except Exception as ex:                                                # noqa: BLE001  (a partial run whose last step was not saved)
        fin = None
        w("\n(growth table skipped: the step-%d snapshot could not be loaded: %s)" % (reached, ex))
    if fin is not None:
        w("\n## Is growth exercised? (the state at step %d)\n" % fin.step)
        w("*touched later* = the seed occurs in a document after the one that opened its cross (the cross is a `grow` task if open, a `left` task if closed); "
          "*ever grown* = at least one unit was seated after birth (`seated` holds a step above `opened_at`); *ever narrowed* = a `grown[]` entry with `narrowed` in the ledger; "
          "*median size* = units seated.\n")
        w("| tier | crosses | never touched after birth | touched later: open | touched later: closed | ever grown | ever narrowed | open at the end | median size all / open / closed |")
        w("|---|---|---|---|---|---|---|---|---|")
        for t in TIERS:
            cr = fin.crosses[t]
            touched, narrowed = set(), set()
            for l in fin.ledger[t]:
                e = json.loads(l)
                for u in e["units"]:
                    if u in cr and cr[u].opened_at < e["step"]:
                        touched.add(u)
                narrowed.update(g["seed"] for g in e["grown"] if g["narrowed"])
            closed = [c for c in cr.values() if c.closed]
            opn = [c for c in cr.values() if not c.closed]
            grown = [c for c in cr.values() if any(s_ > c.opened_at for _u, s_ in c.seated)]
            w("| %s | %d | %d (%s %%) | %d of %d open (%s %%) | %d of %d closed (%s %%) | %d (%s %%) | %d | %d | %s / %s / %s |" % (
                t, len(cr), len(cr) - len(touched), pct((len(cr) - len(touched)) / len(cr)),
                sum(1 for c in opn if c.seed in touched), len(opn), pct(sum(1 for c in opn if c.seed in touched) / len(opn) if opn else None),
                sum(1 for c in closed if c.seed in touched), len(closed), pct(sum(1 for c in closed if c.seed in touched) / len(closed) if closed else None),
                len(grown), pct(len(grown) / len(cr)), len(narrowed), len(opn),
                fnum(median([len(c.seated) for c in cr.values()]), 1), fnum(median([len(c.seated) for c in opn]), 1), fnum(median([len(c.seated) for c in closed]), 1)))
        tot_cr = sum(len(fin.crosses[t]) for t in TIERS)
        w("\nAll tiers: %d crosses, %d ever grown (%s %%). Units recorded as left (`left`, never seated) on closed crosses: %s." % (
            tot_cr, sum(sum(1 for c in fin.crosses[t].values() if any(s_ > c.opened_at for _u, s_ in c.seated)) for t in TIERS),
            pct(sum(sum(1 for c in fin.crosses[t].values() if any(s_ > c.opened_at for _u, s_ in c.seated)) for t in TIERS) / tot_cr),
            "; ".join("%s %d" % (t, sum(len(c.left) for c in fin.crosses[t].values())) for t in TIERS)))
    # ---- Fibonacci summary
    fibs = [r for r in rows if r["fibonacci"]]
    w("\n## Fibonacci summary (%d rows)\n" % len(fibs))
    w("Closure at the Fibonacci steps: crosses / cumulative closed share % / closed at birth share % / closed later (count) / open (count).\n")
    w("| step | article | sent | RUN | WORD | CHAR | wall s | CPU s |")
    w("|---|---|---|---|---|---|---|---|")
    for r in fibs:
        cells = []
        for t in TIERS:
            x = r["tiers"][t]
            cells.append("%d / %s / %s / %d / %d" % (x["crosses"], pct(x["cum_closed_share"]), pct(x["cum_closed_birth_share"]), x["cum_closed_later"], x["cum_open"]))
        w("| %d | %s | %d | %s | %.0f | %.0f |" % (r["step"], r["title"], r["sent_cum"], " | ".join(cells), r["wall_s"], r["cpu_s"]))
    w("\nGrowth in the Fibonacci step itself (grown / fills / narrowed (new+recount members dropped) / frozen share % / frozen seats %):\n")
    w("| step | RUN | WORD | CHAR |")
    w("|---|---|---|---|")
    for r in fibs:
        cells = []
        for t in TIERS:
            x = r["tiers"][t]
            cells.append("%d / %d / %d (%d+%d) / %s / %s" % (x["grown"], x["fills"], x["narrowed"], x["dropped_new"], x["dropped_recount"], pct(x["frozen_share"]), pct(x["frozen_seat_share"])))
        w("| %d | %s |" % (r["step"], " | ".join(cells)))
    # ---- closure curve
    w("\n## Closure curve (cumulative closed share of the crosses, at the measured steps)\n")
    w("```")
    w("step  sent  closed share of the crosses in %, one bar per tier (each # = 2.5 %)")
    for r in rows:
        if not r["measured"]:
            continue
        bars = " ".join("%s %5.1f %-40s" % (t[0], 100.0 * r["tiers"][t]["cum_closed_share"], "#" * int(round(100.0 * r["tiers"][t]["cum_closed_share"] / 2.5))) for t in TIERS)
        w("%4d %5d  %s" % (r["step"], r["sent_cum"], bars))
    w("```")
    # ---- per tier per measured step
    for t in TIERS:
        w("\n## %s: every measured step\n" % t)
        w("opened = new crosses this step; closed = closed this step (birth + grow; by reason mc = max_class, ms = max_states, mm = max_moves); cum = cumulative; "
          "grown = crosses grown with candidates; fills = units seated; nar = crosses narrowed; drop n/r = members dropped (new / recount); "
          "frz = frozen share %; fseat = frozen seats %; med = median units seated; clsmax = largest class (max_class 1000).\n")
        w("| step | article | sent | crosses | opened | closed birth+grow | mc/ms/mm | cum closed | cum % | at-birth % | later | grown | fills | nar | drop n/r | frz % | fseat % | med | clsmax | wall s | CPU s |")
        w("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for r in rows:
            if not r["measured"]:
                continue
            x = r["tiers"][t]
            cr = x["closed_reason"]
            w("| %d | %s | %d | %d | %d | %d+%d | %d/%d/%d | %d | %s | %s | %d | %d | %d | %d | %d/%d | %s | %s | %s | %d | %.0f | %.0f |" % (
                r["step"], r["title"], r["sent_cum"], x["crosses"], x["opened"], x["closed_birth"], x["closed_grow"], cr["max_class"], cr["max_states"], cr["max_moves"],
                x["cum_closed"], pct(x["cum_closed_share"]), pct(x["cum_closed_birth_share"]), x["cum_closed_later"], x["grown"], x["fills"], x["narrowed"],
                x["dropped_new"], x["dropped_recount"], pct(x["frozen_share"]), pct(x["frozen_seat_share"]), fnum(x["size_median"], 0), x["class_max"],
                r["wall_s"], r["cpu_s"]))
    # ---- cost
    w("\n## Cost per step (all steps summarised; every step is in the jsonl)\n")
    w("| step range | steps | wall | CPU | tasks open / grow / left (sum over tiers) |")
    w("|---|---|---|---|---|")
    edges = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 300]
    lo = 1
    for hi in edges:
        grp = [r for r in rows if lo <= r["step"] <= hi]
        if grp:
            w("| %d-%d | %d | %s | %s | %d / %d / %d |" % (lo, hi, len(grp), hms(sum(r["wall_s"] for r in grp)), hms(sum(r["cpu_s"] for r in grp)),
                                                          sum(r["tiers"][t]["tasks_open"] for r in grp for t in TIERS), sum(r["tiers"][t]["tasks_grow"] for r in grp for t in TIERS),
                                                          sum(r["tiers"][t]["tasks_left"] for r in grp for t in TIERS)))
        lo = hi + 1
    cpu_split = {t: [sum(r["tiers"][t]["cpu_open_s"] for r in rows), sum(r["tiers"][t]["cpu_grow_s"] for r in rows), sum(r["tiers"][t]["cpu_left_s"] for r in rows)] for t in TIERS}
    w("\nTask CPU by tier (open / grow / left, s): " + "; ".join("%s %.0f / %.0f / %.0f" % (t, *cpu_split[t]) for t in TIERS) + ".")
    saved = [r for r in rows if r.get("saved")]
    resume = [r["step"] for r in rows if r.get("resume_point") and not r["measured"]]
    w("\nSnapshots saved at %d steps (%s); resume points saved outside the measured set: %s." % (len(saved), "the measured steps", resume or "none"))
    # ---- checks
    w("\n## Fold check (T-G4-4) and arm B\n")
    for k in (13, 34):
        f = read_json(os.path.join(a.out_dir, "gate2_fold_k%d.json" % k))
        if f is None:
            w("- fold k=%d: not run" % k)
        else:
            w("- fold k=%d (a stack built from prefix_%d.jsonl alone, PYTHONHASHSEED=%s, wall %.0f s, CPU %.0f s) vs the step-%d snapshot of the cache: **%s** (%s)." % (
                k, k, f["pythonhashseed"], f["wall_s"], f["cpu_s"], k, "EQUAL" if f["equal"] else "DIFFERENT",
                "; ".join("%s state_sha256 %s.. bytes %s ledger %s" % (t, f["tiers"][t]["state_sha256_alone"][:12], f["tiers"][t]["state_bytes_equal"], f["tiers"][t]["ledger_equal"]) for t in TIERS)))
    for fn in sorted(os.listdir(a.out_dir)):
        if fn.startswith("gate2_resume_k") and fn.endswith(".json"):
            f = read_json(os.path.join(a.out_dir, fn))
            w("- resume check %d -> %d (load the step-%d snapshot, extend article by article in another process, PYTHONHASHSEED=%s): **%s**" % (
                f["from"], f["to"], f["from"], f["pythonhashseed"], "EQUAL" if f["equal"] else "DIFFERENT"))
    b = read_json(os.path.join(a.out_dir, "gate2_B_check.json"))
    if b is None:
        w("- arm B check: not run")
    else:
        w("- arm B (CHAR only, fugashi / unidic_lite not importable) first %d articles vs A's CHAR tier at step %d: **%s** (state_sha256 %s.., ledger_sha256 %s.., state bytes equal %s); "
          "A's cache served with tiers=(CHAR,): %s." % (b["articles"], b["articles"], "EQUAL" if b["equal"] else "DIFFERENT", b["b_state_sha256"][:16], b["b_ledger_sha256"][:16],
                                                           b["state_bytes_equal"], b["a_cache_served_with_tiers_CHAR_equal"]))
    tail = read_json(os.path.join(a.out_dir, "gate2_%s_tail.json" % a.tag))
    if tail:
        w("\nFinal state at step %d: " % tail["step"] + "; ".join("%s %s.." % (t, tail["state_sha256"][t][:16]) for t in TIERS) + ".")
    with open(os.path.join(a.out_dir, "gate2_%s.md" % a.tag), "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    print("wrote", os.path.join(a.out_dir, "gate2_%s.md" % a.tag), "(%d lines)" % len(out))
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--cache", default=CACHE_A)
    b.add_argument("--out-dir", default=RESULTS)
    b.add_argument("--tag", default="A")
    b.add_argument("--workers", type=int, default=4)
    b.add_argument("--upto", type=int, default=300)
    b.add_argument("--save", default="measured", choices=["measured", "fib", "all", "none"])
    b.add_argument("--resume", action="store_true")
    b.add_argument("--max-wall-h", type=float, default=4.0)
    b.add_argument("--max-cache-gb", type=float, default=60.0)
    c = sub.add_parser("check-b")
    c.add_argument("--cache", default=CACHE_A)
    c.add_argument("--b-cache", default=CACHE_B)
    c.add_argument("--articles", type=int, default=8)
    c.add_argument("--workers", type=int, default=1)
    c.add_argument("--out-dir", default=RESULTS)
    f = sub.add_parser("fold")
    f.add_argument("--cache", default=CACHE_A)
    f.add_argument("--k", type=int, required=True)
    f.add_argument("--workers", type=int, default=1)
    f.add_argument("--scratch", default="/Users/motonisihikoudai/Projects/vera-impl/cache/g4_scratch")
    f.add_argument("--out-dir", default=RESULTS)
    r = sub.add_parser("resume-check")
    r.add_argument("--cache", default=CACHE_A)
    r.add_argument("--k", type=int, required=True)
    r.add_argument("--to", type=int, required=True)
    r.add_argument("--workers", type=int, default=1)
    r.add_argument("--out-dir", default=RESULTS)
    q = sub.add_parser("report")
    q.add_argument("--out-dir", default=RESULTS)
    q.add_argument("--tag", default="A")
    q.add_argument("--cache", default=CACHE_A)
    a = ap.parse_args(argv)
    return {"build": cmd_build, "check-b": cmd_check_b, "fold": cmd_fold, "resume-check": cmd_resume_check, "report": cmd_report}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
