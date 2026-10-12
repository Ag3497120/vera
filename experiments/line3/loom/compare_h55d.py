"""LOOM-span (after the review): compare the FOUR measurements of the same 30 runs -- results_h55 (first), h55b (LOOM-batch), h55c (LOOM-span), h55d (LOOM-span
after the review: first/last, letters-only hit_cited, no swap for a quoted stretch, the over-extension rule and QUESTION_ECHO) -- under the EXACT-MATCH headline.

    python experiments/line3/loom/compare_h55d.py [--write]

Every run is scored by rescore.rescore_dir (the ledger is VERIFIED first, then scored under experiments/line3/loom/score.py as it is now), so all four measurements are
judged by one rule.  The per-run facts are those of compare_span.facts plus: `over` (an answerable loom run that EMITTED a text which holds a gold alternative and is
longer than it: hits_text and not hit_exact), `echo_notes` (distinct QUESTION_ECHO notes the ledger shows; only a notes.v2 run can show any), and `echo_units`
(the units of the FINAL thread, replayed, that the QUESTION_ECHO definition would flag; computed the same way for every measurement, so the older ones can be
compared).  Reads results and ledgers; writes only COMPARE_TABLES.txt with --write (never overwritten).  The narrative of COMPARE.md is written by hand.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import statistics
import sys
from collections import Counter
from typing import Dict, List, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load(name: str, fname: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, fname))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


cs = _load("loom_compare_span", "compare_span.py")
rescore = cs.rescore
from verantyx.loom import ledger as lg            # noqa: E402
from verantyx.loom import notes as notelib        # noqa: E402

LABELS = ("h55", "h55b", "h55c", "h55d")
TASKS, MODES, SHORT = cs.TASKS, cs.MODES, cs.SHORT
yn, med, refs = cs.yn, cs.med, cs.refs


def facts(r: dict) -> dict:
    f = cs.facts(r)
    rows = cs.ledger_rows(r)
    f["over"] = bool(r["mode"] != "free_text" and r["kind"] == "answerable" and r["text"] is not None and r["hits_text"] and not r["hit_exact"])
    f["echo_notes"] = notelib.note_summary(rows)["by_type"].get("QUESTION_ECHO", 0)
    f["echo_units"] = None
    if r["mode"] != "free_text" and r["text"] is not None and r["kind"] == "answerable":
        rep = lg.replay(r["run_dir"])
        run = rep.run
        linked = [run.state.crosses[c] for c in run.state.thread]
        f["echo_units"] = [n["unit"] for n in notelib.question_echo(run, linked)]
    f["question"] = None
    return f


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    for lab in LABELS:
        ap.add_argument("--" + lab, dest=lab, default="experiments/line3/loom/results_" + lab)
    ap.add_argument("--write", action="store_true", help="write the tables to <h55d>/COMPARE_TABLES.txt (never overwritten)")
    a = ap.parse_args(argv)
    bank = rescore.score.load_bank(rescore.BANK)
    gold = rescore.score.load_gold()
    F: Dict[str, Dict[Tuple[str, str], dict]] = {}
    for lab in LABELS:
        F[lab] = {(r["base"], r["mode"]): facts(r) for r in rescore.rescore_dir(getattr(a, lab), bank, gold)}
        assert len(F[lab]) == 30, (lab, len(F[lab]))
    out: List[str] = []
    p = out.append

    p("PER TASK x MODE  (every cell is h55 / h55b / h55c / h55d; exact = hit_exact (HEADLINE), cited = hit_cited (letters only), over = emitted a longer text that holds the gold)")
    p("| task | mode | status | exact | cited | over (d) | ops | weaves | refusals d | echo units in final thread (d) | output d |")
    p("|---|---|---|---|---|---|---|---|---|---|---|")
    for t in TASKS:
        for m in MODES:
            fs = [F[l][(t, m)] for l in LABELS]

            def quad(key, fmt=lambda v: str(v)):
                return " / ".join(fmt(f[key]) for f in fs)
            out_d = fs[3]["text"]
            p("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                t, SHORT[m], " / ".join(f["status"] for f in fs), quad("exact", yn), quad("cited", yn), "-" if m == "free_text" else yn(fs[3]["over"]),
                quad("ops"), "n/a" if m == "free_text" else quad("weaves"), refs(fs[3]),
                "-" if fs[3]["echo_units"] is None else ",".join(fs[3]["echo_units"]) or "0",
                "(none)" if out_d is None else "「%s」" % out_d.replace("|", "/").replace("\n", " ")[:50]))
    p("")

    p("HEADLINE (answerable exact hits /7) and the secondary counts")
    p("| | record_only exact | constructed_allowed exact | control exact | loom cited (14) | loom over-extended (14) | loom emitted (14) | unans abstained (loom 6 + control 3) |")
    p("|---|---|---|---|---|---|---|---|")
    for lab in LABELS:
        cells = []
        for m in MODES:
            ans = [F[lab][(t, m)] for t in TASKS[:7]]
            cells.append("%d/7" % sum(1 for f in ans if f["exact"]))
        loom = [F[lab][(t, m)] for t in TASKS[:7] for m in MODES[:2]]
        un = [F[lab][(t, m)] for t in TASKS[7:] for m in MODES]
        p("| %s | %s | %d | %d | %d | %d/9 |" % (lab, " | ".join(cells), sum(1 for f in loom if f["cited"]), sum(1 for f in loom if f["over"]),
                                                   sum(1 for f in loom if f["text"] is not None), sum(1 for f in un if f["status"] == "abstained_correct")))
    p("")

    p("OVER-EXTENSION BEFORE / AFTER (answerable loom runs that EMITTED a text holding the gold, longer than it; excess = normalised characters beyond the gold)")
    for lab in LABELS:
        ov = [(t, m, F[lab][(t, m)]) for t in TASKS[:7] for m in MODES[:2] if F[lab][(t, m)]["over"]]
        p("%s: %d of 14 -- %s" % (lab, len(ov), "; ".join("%s %s 「%s」 +%d" % (t, SHORT[m], f["text"], f["excess"]) for t, m, f in ov)))
    p("")

    p("QUESTION_ECHO")
    for lab in LABELS:
        loom = [F[lab][(t, m)] for t in TASKS for m in MODES[:2]]
        em = [f for f in loom if f["echo_units"] is not None]
        p("%s: QUESTION_ECHO notes shown in the ledgers (distinct, 20 loom runs) %d; runs with >= 1 echo note %d; units of the FINAL thread that the definition would flag (answerable loom runs that emitted: %d): %d units in %d runs"
          % (lab, sum(f["echo_notes"] for f in loom), sum(1 for f in loom if f["echo_notes"]), len(em), sum(len(f["echo_units"]) for f in em),
             sum(1 for f in em if f["echo_units"])))
    p("")

    p("TOTALS (answerable = 7 tasks, unans = 3 tasks, per mode)")
    p("| mode | meas. | exact /7 | cited | over | hits_text /7 | emitted, not exact | unans abstained /3 | unans no output | unans answered | median ops (ans.) | median lookups (ans.) | weaves (ok) | drops | unseats | turns | tool calls |")
    p("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for m in MODES:
        for lab in LABELS:
            fs = [F[lab][(t, m)] for t in TASKS]
            ans = [f for f in fs if f["kind"] == "answerable"]
            un = [f for f in fs if f["kind"] == "unans"]
            p("| %s | %s | **%d** | %d | %d | %d | %d | %d | %d | %d | %s | %s | %s | %d | %d | %d | %d |" % (
                SHORT[m], lab, sum(1 for f in ans if f["exact"]), sum(1 for f in ans if f["cited"]), sum(1 for f in ans if f["over"]), sum(1 for f in ans if f["hits_text"]),
                sum(1 for f in ans if f["status"] == "miss"), sum(1 for f in un if f["status"] == "abstained_correct"),
                sum(1 for f in un if f["status"] == "no_output"), sum(1 for f in un if f["status"] == "answered_unans"), med([f["ops"] for f in ans]), med([f["lookups"] for f in ans]),
                "n/a" if m == "free_text" else "%d (%d)" % (sum(f["weaves"] for f in fs), sum(f["weaves_ok"] for f in fs)),
                sum(f["drops"] for f in fs), sum(f["unseats"] for f in fs), sum(f["turns"] for f in fs), sum(f["calls"] for f in fs)))
    p("")

    p("OTHER COUNTS (loom modes only: ro + ca, 20 runs; answerable = 14)")
    for lab in LABELS:
        fs = [F[lab][(t, m)] for t in TASKS for m in MODES[:2]]
        ans = [f for f in fs if f["kind"] == "answerable"]
        agg = Counter()
        for f in fs:
            for k, v in f["refusals"].items():
                agg[k] += v
        p("%s: refusal totals %s; answerable runs with >= 1 refusal %d/14; unstable_cross shown in %d answerable runs, emit refused for it %d; constructed adds ok %d / refused %d; "
          "emit attempts %d; reads %d; unseat ops %d; drops %d; weave calls %d (ok %d, in %d runs); note rows %d, notes %s" % (
              lab, dict(sorted(agg.items())), sum(1 for f in ans if f["n_ref"]), sum(1 for f in ans if f["unstable_seen"]), sum(f["unstable_emit_refused"] for f in ans),
              sum(f["constructed_ok"] for f in fs), sum(f["constructed_refused"] for f in fs), sum(f["emits"] for f in fs), sum(f["reads"] for f in fs),
              sum(f["unseats"] for f in fs), sum(f["drops"] for f in fs), sum(f["weaves"] for f in fs), sum(f["weaves_ok"] for f in fs), sum(1 for f in fs if f["weaves"]),
              sum(f["notes_rows"] for f in fs), dict(sum((f["note_types"] for f in fs), Counter()))))
    for lab in ("h55c", "h55d"):
        sp = Counter()
        for t in TASKS:
            for m in MODES[:2]:
                sp.update(F[lab][(t, m)]["span_refused"])
        p("%s weave_span refusals by type: %s" % (lab, dict(sorted(sp.items()))))
    p("")

    p("P-LOOM inputs (exact rule)")
    for lab in LABELS:
        ro = [F[lab][(t, "record_only")] for t in TASKS[:7]]
        ca = [F[lab][(t, "constructed_allowed")] for t in TASKS[:7]]
        ctl = [F[lab][(t, "free_text")] for t in TASKS]
        un_ro = [F[lab][(t, "record_only")] for t in TASKS[7:]]
        un_ca = [F[lab][(t, "constructed_allowed")] for t in TASKS[7:]]
        p("%s P1 ro exact %d/7 (of which at the first emit attempt %d; hits_text %d/7); P2 ca exact %d/7 (hits_text %d/7), median constructed share of emitted text (permille) %s; "
          "P3 unans abstained ro %d/3 (+%d no output), ca %d/3; P4 control exact %d/7 (hits_text %d/7), unans 不明 %d/3" % (
              lab, sum(1 for f in ro if f["exact"]), sum(1 for f in ro if f["exact"] and f["emits"] == 1), sum(1 for f in ro if f["hits_text"]),
              sum(1 for f in ca if f["exact"]), sum(1 for f in ca if f["hits_text"]),
              med([f["cons_permille"] for f in ca + ro if f["cons_permille"] is not None]),
              sum(1 for f in un_ro if f["status"] == "abstained_correct"), sum(1 for f in un_ro if f["status"] == "no_output"),
              sum(1 for f in un_ca if f["status"] == "abstained_correct"),
              sum(1 for f in ctl[:7] if f["exact"]), sum(1 for f in ctl[:7] if f["hits_text"]), sum(1 for f in ctl[7:] if f["status"] == "abstained_correct")))
        ans_loom = [F[lab][(t, m)] for t in TASKS[:7] for m in MODES[:2]]
        p("%s P5 ops per answerable loom run: median %s (min %s, max %s); answerable loom runs with >= 1 refusal %d/14; with unstable_cross shown %d/14" % (
            lab, med([f["ops"] for f in ans_loom]), min(f["ops"] for f in ans_loom), max(f["ops"] for f in ans_loom), sum(1 for f in ans_loom if f["n_ref"]),
            sum(1 for f in ans_loom if f["unstable_seen"])))
        wall = lambda f: f["wall_ns"] or 0
        ratios = []
        for t in TASKS:
            c = wall(F[lab][(t, "free_text")])
            for m in MODES[:2]:
                if c:
                    ratios.append(wall(F[lab][(t, m)]) * 100 // c)
        p("%s P6 loom wall / control wall per task (percent): median %s, min %s, max %s; control median wall %.1f s, loom median wall %.1f s" % (
            lab, med(ratios), min(ratios), max(ratios), statistics.median(wall(F[lab][(t, "free_text")]) for t in TASKS) / 1e9,
            statistics.median(wall(F[lab][(t, m)]) for t in TASKS for m in MODES[:2]) / 1e9))
    p("")

    p("TOKENS (API-reported usage, testimony of the provider; h55 recorded none)")
    for lab in LABELS[1:]:
        ub = [F[lab][(t, m)]["usage"] for t in TASKS for m in MODES]
        if all(ub):
            p("%s: input %d, output %d, calls %d; by mode: %s; largest run %d input tokens (%s)" % (
                lab, sum(u["input_tokens"] for u in ub), sum(u["output_tokens"] for u in ub), sum(u["calls"] for u in ub),
                ", ".join("%s in %d out %d" % (SHORT[m], sum(F[lab][(t, m)]["usage"]["input_tokens"] for t in TASKS),
                                               sum(F[lab][(t, m)]["usage"]["output_tokens"] for t in TASKS)) for m in MODES),
                max(F[lab][k]["usage"]["input_tokens"] for k in F[lab]), max(F[lab], key=lambda k: F[lab][k]["usage"]["input_tokens"])))
        else:
            p("%s: not recorded" % lab)
    txt = "\n".join(out)
    print(txt)
    if a.write:
        with open(os.path.join(ROOT, a.h55d, "COMPARE_TABLES.txt"), "x", encoding="utf-8") as fh:
            fh.write(txt + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
