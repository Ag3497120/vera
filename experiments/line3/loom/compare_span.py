"""LOOM-span: compare the three measurements of the same 30 runs (results_h55 = first Haiku 5.5 measurement, results_h55b = after LOOM-batch, results_h55c =
after LOOM-span) under the EXACT-MATCH headline and print / write the tables of results_h55c/COMPARE.md.

    python experiments/line3/loom/compare_span.py [--a results_h55] [--b results_h55b] [--c results_h55c] [--write]

Every run is scored by rescore.rescore_dir (the ledger is VERIFIED first, then scored under experiments/line3/loom/score.py as it is now), so all three measurements
are judged by one rule: hit_exact (headline), hit_cited, hits_text (secondary).  Reads the results JSON files and the ledgers they name; calls nothing, writes
only COMPARE_TABLES.txt with --write (never overwritten).  The narrative of COMPARE.md is written by hand around these tables.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import statistics
import sys
from collections import Counter
from typing import Dict, List, Optional, Tuple

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


rescore = _load("loom_rescore", "rescore.py")
TASKS = ["I2-001", "I2-041", "I2-008", "I2-034", "I2-013", "R2-I013", "I2-025", "UF-001", "UF-015", "R2-U003"]
MODES = ["record_only", "constructed_allowed", "free_text"]
SHORT = {"record_only": "ro", "constructed_allowed": "ca", "free_text": "ctl"}
LABELS = ("h55", "h55b", "h55c")
WEAVES = ("weave_sentence", "weave_span")


def ledger_rows(r: dict) -> List[dict]:
    with open(os.path.join(r["run_dir"], "ops.jsonl"), encoding="utf-8") as f:
        return [json.loads(ln) for ln in f if ln.strip()]


def facts(r: dict) -> dict:
    o = r["result"]
    rows = ledger_rows(r)
    model = [x for x in rows if x["actor"] == "model"]
    bo = o["op_counts"]["by_op"]
    f: Dict = {"kind": r["kind"], "status": r["status"], "exact": r["hit_exact"], "cited": r["hit_cited"], "hits_text": r["hits_text"], "excess": r["excess_chars"],
               "text": r["answer_line"] if r["mode"] == "free_text" else r["text"], "ops": o["op_counts"]["by_class"].get("ops", 0),
               "lookups": o["op_counts"]["by_class"].get("lookups", 0), "reads": bo.get("read", 0), "emits": bo.get("emit", 0),
               "weaves": sum(bo.get(k, 0) for k in WEAVES), "refusals": dict(o["refusals"] or {}), "turns": o["driver_report"]["turns"],
               "calls": o["driver_report"]["tool_calls"], "usage": o["driver_report"].get("usage"), "wall_ns": (o.get("wall") or {}).get("driver_ns"),
               "sc": o["self_corrections"]["counts"], "cons_permille": ((o.get("score") or {}).get("share_permille") or {}).get("constructed")}
    f["n_ref"] = sum(f["refusals"].values())
    f["drops"] = sum(1 for x in model if x["op"] == "drop" and x["result"].get("ok"))
    f["unseats"] = sum(1 for x in model if x["op"] == "unseat" and x["result"].get("ok"))
    f["weaves_ok"] = sum(1 for x in model if x["op"] in WEAVES and x["result"].get("ok"))
    f["span_refused"] = Counter(x["result"].get("refusal") for x in model if x["op"] == "weave_span" and not x["result"].get("ok"))
    seen = emit_ref = 0
    for x in model:
        res = x["result"]
        if x["op"] == "weave_sentence" and res.get("ok"):
            seen += any(y["type"] == "unstable_cross" for y in res["readout"]["refusals"])
        elif x["op"] == "read" and res.get("ok"):
            seen += any(y["type"] == "unstable_cross" for y in res["refusals"])
        elif x["op"] == "emit" and res.get("ok") is False and res.get("refusal") == "unstable_cross":
            emit_ref += 1
    f["unstable_seen"], f["unstable_emit_refused"] = seen, emit_ref
    f["constructed_ok"] = sum(1 for x in model if x["op"] == "add" and x["args"].get("kind") == "constructed" and x["result"].get("ok"))
    f["constructed_refused"] = sum(1 for x in model if x["op"] == "add" and x["args"].get("kind") == "constructed" and not x["result"].get("ok"))
    f["unlinked"] = sum(1 for x in model if x["op"] in ("read", "emit") and any(y.get("type") == "unlinked_cross" for y in (
        (x["result"].get("refusals") or []) if x["result"].get("ok") else x["result"].get("detail", {}).get("refusals", []))))
    f["notes_rows"] = sum(1 for x in rows if x["actor"] == "loom")
    f["note_types"] = Counter(n["type"] for x in rows if x["actor"] == "loom" for n in x["args"]["notes"])
    return f


def yn(v) -> str:
    return "-" if v is None else ("Y" if v else "N")


def med(xs):
    return statistics.median(xs) if xs else None


def refs(f: dict) -> str:
    return "0" if not f["refusals"] else "%d (%s)" % (f["n_ref"], ", ".join("%s %d" % (k, v) for k, v in sorted(f["refusals"].items())))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    for flag, lab in (("--a", "h55"), ("--b", "h55b"), ("--c", "h55c")):
        ap.add_argument(flag, dest=lab, default="experiments/line3/loom/results_" + lab)
    ap.add_argument("--write", action="store_true", help="write the tables to <c>/COMPARE_TABLES.txt (never overwritten)")
    a = ap.parse_args(argv)
    bank = rescore.score.load_bank(rescore.BANK)
    gold = rescore.score.load_gold()
    F: Dict[str, Dict[Tuple[str, str], dict]] = {}
    for lab in LABELS:
        F[lab] = {(r["base"], r["mode"]): facts(r) for r in rescore.rescore_dir(getattr(a, lab), bank, gold)}
        assert len(F[lab]) == 30, (lab, len(F[lab]))
    out: List[str] = []
    p = out.append

    p("PER TASK x MODE  (a = h55, b = h55b, c = h55c; every cell is a / b / c; exact = hit_exact (HEADLINE), cited = hit_cited, text = hits_text (substring))")
    p("| task | mode | status a / b / c | exact | cited | text | ops | weaves | drops | unseats | refusals c | output c |")
    p("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for t in TASKS:
        for m in MODES:
            fs = [F[l][(t, m)] for l in LABELS]
            def tri(key, fmt=lambda v: str(v)):
                return " / ".join(fmt(f[key]) for f in fs)
            weave_cell = "n/a" if m == "free_text" else tri("weaves")
            out_c = fs[2]["text"]
            p("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                t, SHORT[m], " / ".join(f["status"] for f in fs), tri("exact", yn), tri("cited", yn), tri("hits_text", yn), tri("ops"), weave_cell,
                "n/a" if m == "free_text" else tri("drops"), "n/a" if m == "free_text" else tri("unseats"), refs(fs[2]),
                "(none)" if out_c is None else "「%s」" % out_c.replace("|", "/").replace("\n", " ")[:50]))
    p("")

    p("TOTALS (answerable = 7 tasks, unans = 3 tasks, per mode)")
    p("| mode | meas. | exact /7 | cited (extra) | hits_text /7 | emitted, not exact | unans abstained /3 | unans no output | unans answered | runs that hit lookup_cap | median ops (ans.) | median lookups (ans.) | weaves (ok) | drops | unseats | turns | tool calls |")
    p("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for m in MODES:
        for lab in LABELS:
            fs = [F[lab][(t, m)] for t in TASKS]
            ans = [f for f in fs if f["kind"] == "answerable"]
            un = [f for f in fs if f["kind"] == "unans"]
            p("| %s | %s | **%d** | %d | %d | %d | %d | %d | %d | %d | %s | %s | %s | %d | %d | %d | %d |" % (
                SHORT[m], lab, sum(1 for f in ans if f["exact"]), sum(1 for f in ans if f["cited"]), sum(1 for f in ans if f["hits_text"]),
                sum(1 for f in ans if f["status"] == "miss"), sum(1 for f in un if f["status"] == "abstained_correct"),
                sum(1 for f in un if f["status"] == "no_output"), sum(1 for f in un if f["status"] == "answered_unans"),
                sum(1 for f in fs if f["refusals"].get("lookup_cap")), med([f["ops"] for f in ans]), med([f["lookups"] for f in ans]),
                "n/a" if m == "free_text" else "%d (%d)" % (sum(f["weaves"] for f in fs), sum(f["weaves_ok"] for f in fs)),
                sum(f["drops"] for f in fs), sum(f["unseats"] for f in fs), sum(f["turns"] for f in fs), sum(f["calls"] for f in fs)))
    p("")

    p("HEADLINE (answerable exact hits /7)")
    p("| | record_only | constructed_allowed | control (free text) |")
    p("|---|---|---|---|")
    for lab in LABELS:
        cells = []
        for m in MODES:
            ans = [F[lab][(t, m)] for t in TASKS[:7]]
            cells.append("%d/7" % sum(1 for f in ans if f["exact"]))
        p("| %s | %s |" % (lab, " | ".join(cells)))
    p("")

    p("OTHER COUNTS (loom modes only: ro + ca, 20 runs; answerable = 14)")
    for lab in LABELS:
        fs = [F[lab][(t, m)] for t in TASKS for m in MODES[:2]]
        ans = [f for f in fs if f["kind"] == "answerable"]
        agg = Counter()
        for f in fs:
            for k, v in f["refusals"].items():
                agg[k] += v
        p("%s: refusal totals %s; answerable runs with >= 1 refusal %d/14; unstable_cross shown in a read%s in %d answerable runs, emit refused for it %d; constructed adds ok %d / refused %d; "
          "emit attempts %d; reads %d; unseat ops %d; drops %d; read/emit refusals naming unlinked_cross %d; weave calls %d (ok %d, in %d runs); note rows %d, notes %s" % (
              lab, dict(sorted(agg.items())), sum(1 for f in ans if f["n_ref"]), " or a weave read-out" if lab != "h55c" else "", sum(1 for f in ans if f["unstable_seen"]),
              sum(f["unstable_emit_refused"] for f in ans), sum(f["constructed_ok"] for f in fs), sum(f["constructed_refused"] for f in fs),
              sum(f["emits"] for f in fs), sum(f["reads"] for f in fs), sum(f["unseats"] for f in fs), sum(f["drops"] for f in fs), sum(f["unlinked"] for f in fs),
              sum(f["weaves"] for f in fs), sum(f["weaves_ok"] for f in fs), sum(1 for f in fs if f["weaves"]), sum(f["notes_rows"] for f in fs),
              dict(sum((f["note_types"] for f in fs), Counter()))))
        p("%s: self-corrections over the 20 loom runs: plan_change_after_empty %d, unseat_swap_before_close %d, recovery_after_refusal %d of %d recoverable refusals" % (
            lab, sum(f["sc"]["plan_change_after_empty"] for f in fs), sum(f["sc"]["unseat_swap_before_close"] for f in fs),
            sum(f["sc"]["recovery_after_refusal"] for f in fs), sum(f["sc"]["refusals_recoverable"] for f in fs)))
    sp = Counter()
    for t in TASKS:
        for m in MODES[:2]:
            sp.update(F["h55c"][(t, m)]["span_refused"])
    p("h55c weave_span refusals by type: %s" % dict(sorted(sp.items())))
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
        with open(os.path.join(ROOT, a.h55c, "COMPARE_TABLES.txt"), "x", encoding="utf-8") as fh:
            fh.write(txt + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
