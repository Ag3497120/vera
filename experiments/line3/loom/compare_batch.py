"""LOOM-batch: compare two measurements of the same 30 runs (default: results_h55 = the first Haiku 5.5 measurement, results_h55b = after LOOM-batch)
and print / write the tables of results_h55b/COMPARE.md.  Reads the results JSON files and the ledgers they name; opens nothing else, calls nothing.

    python experiments/line3/loom/compare_batch.py [--a results_h55] [--b results_h55b] [--write]

The numbers are exact integers (counts, medians of integers, milli-fractions); the narrative of COMPARE.md is written by hand around these tables.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import statistics
from collections import Counter
from typing import Dict, List, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
TASKS = ["I2-001", "I2-041", "I2-008", "I2-034", "I2-013", "R2-I013", "I2-025", "UF-001", "UF-015", "R2-U003"]
MODES = ["record_only", "constructed_allowed", "free_text"]
SHORT = {"record_only": "ro", "constructed_allowed": "ca", "free_text": "ctl"}
STATE_CHANGING = {"add", "open_cross", "seat", "seat_run", "weave_sentence", "unseat", "swap", "extend", "topic", "set_depth", "link", "unlink"}


def load(d: str) -> Dict[Tuple[str, str], dict]:
    out = {}
    for f in sorted(glob.glob(os.path.join(ROOT, d, "*.json"))):
        o = json.load(open(f, encoding="utf-8"))
        out[(o["base"], o["mode"])] = o
    return out


def ledger_rows(o: dict) -> List[dict]:
    return [json.loads(l) for l in open(os.path.join(ROOT, o["ledger"]), encoding="utf-8") if l.strip()]


def facts(o: dict) -> dict:
    rs = [r for r in ledger_rows(o) if r["actor"] == "model"]
    bo = o["op_counts"]["by_op"]
    f = {"status": o["score"]["status"], "hit": o["score"]["hits_text"], "kind": o["score"]["kind"], "excess": o["score"]["excess_chars"],
         "ops": o["op_counts"]["by_class"].get("ops", 0), "lookups": o["op_counts"]["by_class"].get("lookups", 0), "reads": bo.get("read", 0),
         "emits": bo.get("emit", 0), "weave": bo.get("weave_sentence", 0), "refusals": dict(o["refusals"]), "turns": o["driver_report"]["turns"],
         "calls": o["driver_report"]["tool_calls"], "sc": o["self_corrections"]["counts"], "text": o["score"]["text"],
         "cons_permille": (o["score"].get("share_permille") or {}).get("constructed"), "wall_ns": (o.get("wall") or {}).get("driver_ns"),
         "usage": o["driver_report"].get("usage")}
    f["n_ref"] = sum(f["refusals"].values())
    # a dry-run / weave read-out that showed unstable_cross, and an emit refused for it
    seen = emit_ref = 0
    for r in rs:
        res = r["result"]
        if r["op"] == "weave_sentence" and res.get("ok"):
            seen += any(x["type"] == "unstable_cross" for x in res["readout"]["refusals"])
        elif r["op"] == "read" and res.get("ok"):
            seen += any(x["type"] == "unstable_cross" for x in res["refusals"])
        elif r["op"] == "emit" and res.get("ok") is False and res.get("refusal") == "unstable_cross":
            emit_ref += 1
    f["unstable_seen"], f["unstable_emit_refused"] = seen, emit_ref
    f["constructed_ok"] = sum(1 for r in rs if r["op"] == "add" and r["args"].get("kind") == "constructed" and r["result"].get("ok"))
    f["constructed_refused"] = sum(1 for r in rs if r["op"] == "add" and r["args"].get("kind") == "constructed" and not r["result"].get("ok"))
    f["unseat_after_weave"] = 0
    wv = [r["i"] for r in rs if r["op"] == "weave_sentence"]
    if wv:
        f["unseat_after_weave"] = sum(1 for r in rs if r["op"] == "unseat" and r["i"] > wv[0] and r["result"].get("ok"))
    f["unlinked_hits"] = sum(1 for r in rs if r["op"] in ("read", "emit") and any(x.get("type") == "unlinked_cross"
                             for x in ((r["result"].get("refusals") or []) if r["result"].get("ok") else r["result"].get("detail", {}).get("refusals", []))))
    return f


def refs(f: dict) -> str:
    if not f["refusals"]:
        return "0"
    return "%d (%s)" % (f["n_ref"], ", ".join("%s %d" % (k, v) for k, v in sorted(f["refusals"].items())))


def sc(f: dict) -> str:
    c = f["sc"]
    return "%d/%d/%d" % (c["plan_change_after_empty"], c["unseat_swap_before_close"], c["recovery_after_refusal"])


def med(xs):
    return statistics.median(xs) if xs else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", default="experiments/line3/loom/results_h55")
    ap.add_argument("--b", default="experiments/line3/loom/results_h55b")
    ap.add_argument("--write", action="store_true", help="write the tables to <b>/COMPARE_TABLES.txt")
    a = ap.parse_args(argv)
    A, B = load(a.a), load(a.b)
    FA = {k: facts(o) for k, o in A.items()}
    FB = {k: facts(o) for k, o in B.items()}
    out: List[str] = []
    p = out.append
    p("PER TASK x MODE  (a = %s, b = %s)" % (os.path.basename(a.a), os.path.basename(a.b)))
    p("| task | mode | status a -> b | hit a -> b | ops a -> b | lookups a -> b | refusals a | refusals b | weave_sentence b | plan/unseat+swap/recovery a -> b |")
    p("|---|---|---|---|---|---|---|---|---|---|")
    for t in TASKS:
        for m in MODES:
            x, y = FA[(t, m)], FB[(t, m)]
            hit = lambda f: "-" if f["kind"] == "unans" else ("yes" if f["hit"] else "no")
            p("| %s | %s | %s -> %s | %s -> %s | %d -> %d | %d -> %d | %s | %s | %s | %s -> %s |" % (
                t, SHORT[m], x["status"], y["status"], hit(x), hit(y), x["ops"], y["ops"], x["lookups"], y["lookups"], refs(x), refs(y),
                ("%d" % y["weave"]) if m != "free_text" else "n/a", sc(x), sc(y)))
    p("")
    p("TOTALS")
    p("| mode | measurement | answerable hits_text /7 | emitted-but-wrong | unans abstained_correct /3 | unans no_output | unans emitted | runs that hit a lookup cap | median ops (answerable) | median lookups (answerable) | turns | tool calls |")
    p("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for m in MODES:
        for lab, F in (("a", FA), ("b", FB)):
            fs = [F[(t, m)] for t in TASKS]
            ans = [f for f in fs if f["kind"] == "answerable"]
            un = [f for f in fs if f["kind"] == "unans"]
            p("| %s | %s | %d | %d | %d | %d | %d | %d | %s | %s | %d | %d |" % (
                SHORT[m], lab, sum(1 for f in ans if f["hit"]), sum(1 for f in ans if f["status"] in ("miss", "wrong")),
                sum(1 for f in un if f["status"] == "abstained_correct"), sum(1 for f in un if f["status"] == "no_output"),
                sum(1 for f in un if f["status"] in ("emitted", "hit", "miss", "wrong")),
                sum(1 for f in fs if f["refusals"].get("lookup_cap")), med([f["ops"] for f in ans]), med([f["lookups"] for f in ans]),
                sum(f["turns"] for f in fs), sum(f["calls"] for f in fs)))
    p("")
    p("OTHER COUNTS (loom modes only: ro + ca, 20 runs; answerable = 14)")
    for lab, F in (("a", FA), ("b", FB)):
        fs = [F[(t, m)] for t in TASKS for m in MODES[:2]]
        ans = [f for f in fs if f["kind"] == "answerable"]
        agg = Counter()
        for f in fs:
            for k, v in f["refusals"].items():
                agg[k] += v
        p("%s: refusal totals %s; answerable runs with >= 1 refusal %d/14; with unstable_cross shown in a read/weave read-out %d, emit refused unstable_cross %d; "
          "constructed adds ok %d / refused %d; emit attempts total %d; reads total %d; unseat ops after the first weave %d; "
          "read/emit refusals naming unlinked_cross %d; weave_sentence calls %d (runs using it %d)" % (
              lab, dict(sorted(agg.items())), sum(1 for f in ans if f["n_ref"]), sum(1 for f in ans if f["unstable_seen"]),
              sum(f["unstable_emit_refused"] for f in ans), sum(f["constructed_ok"] for f in fs), sum(f["constructed_refused"] for f in fs),
              sum(f["emits"] for f in fs), sum(f["reads"] for f in fs), sum(f["unseat_after_weave"] for f in fs), sum(f["unlinked_hits"] for f in fs),
              sum(f["weave"] for f in fs), sum(1 for f in fs if f["weave"])))
        p("%s: self-corrections summed over the 20 loom runs: plan_change_after_empty %d, unseat_swap_before_close %d, recovery_after_refusal %d of %d recoverable refusals" % (
            lab, sum(f["sc"]["plan_change_after_empty"] for f in fs), sum(f["sc"]["unseat_swap_before_close"] for f in fs),
            sum(f["sc"]["recovery_after_refusal"] for f in fs), sum(f["sc"]["refusals_recoverable"] for f in fs)))
    p("")
    p("P-LOOM inputs")
    for lab, F in (("a", FA), ("b", FB)):
        ro = [F[(t, "record_only")] for t in TASKS[:7]]
        ca = [F[(t, "constructed_allowed")] for t in TASKS[:7]]
        ctl = [F[(t, "free_text")] for t in TASKS]
        p("%s P1 ro hits %d/7, of which emitted at the first emit attempt %d; P2 ca hits %d/7, median constructed share of emitted text (permille) %s; "
          "P4 control answerable %d/7, unans 不明 %d/3" % (
              lab, sum(1 for f in ro if f["hit"]), sum(1 for f in ro if f["hit"] and f["emits"] == 1), sum(1 for f in ca if f["hit"]),
              med([f["cons_permille"] for f in ca + ro if f["cons_permille"] is not None]),
              sum(1 for f in ctl[:7] if f["hit"]), sum(1 for f in ctl[7:] if f["status"] == "abstained_correct")))
        wall = lambda f: f["wall_ns"] or 0
        ratios = []
        for t in TASKS:
            c = wall(F[(t, "free_text")])
            for m in MODES[:2]:
                if c:
                    ratios.append(wall(F[(t, m)]) * 100 // c)
        p("%s P6 loom wall / control wall per task (percent), median %s, min %s, max %s; control median wall %.1f s, loom median wall %.1f s" % (
            lab, med(ratios), min(ratios), max(ratios), statistics.median(wall(F[(t, "free_text")]) for t in TASKS) / 1e9,
            statistics.median(wall(F[(t, m)]) for t in TASKS for m in MODES[:2]) / 1e9))
    ub = [FB[(t, m)]["usage"] for t in TASKS for m in MODES]
    if all(u for u in ub):
        p("COST b (API-reported tokens): input %d, output %d, calls %d; by mode: %s" % (
            sum(u["input_tokens"] for u in ub), sum(u["output_tokens"] for u in ub), sum(u["calls"] for u in ub),
            ", ".join("%s in %d out %d" % (SHORT[m], sum(FB[(t, m)]["usage"]["input_tokens"] for t in TASKS), sum(FB[(t, m)]["usage"]["output_tokens"] for t in TASKS))
                      for m in MODES)))
    p("COST a: the first measurement's driver reports hold no token counts (the driver did not record usage then); turns and tool calls are in the totals table.")
    txt = "\n".join(out)
    print(txt)
    if a.write:
        open(os.path.join(ROOT, a.b, "COMPARE_TABLES.txt"), "w", encoding="utf-8").write(txt + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
