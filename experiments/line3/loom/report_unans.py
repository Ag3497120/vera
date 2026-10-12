"""LOOM-control: the tables of the unanswerable-question measurement (L-LOOM-154).

    python experiments/line3/loom/report_unans.py [--bank tasks_unans.jsonl] [--runs runs_unans] [--results results_unans] [--write]

Reads the task bank, VERIFIES every ledger of the runs folder (`score.score_run`: chain + replay) and scores it with `score.py` as it is now (status, stop layer, the
counts the layer rests on); the token / wall numbers come from the results files (API-reported usage, testimony).  Prints the tables; with --write they go to
`<results>/REPORT_TABLES.txt` (never overwritten).  The narrative of REPORT.md is written by hand.  Nothing here calls a model or reads a gold (an unanswerable item has none).
The same command reads the adversarial bank (`--bank tasks_unans_adv.jsonl --runs runs_unans_adv --results results_unans_adv`).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import statistics
import sys
from collections import Counter, OrderedDict
from typing import Any, Dict, List, Optional

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


S = _load("loom_score", "score.py")
MODES = ("record_only", "constructed_allowed", "free_text", "no_tools")
LOOM_MODES = ("record_only", "constructed_allowed")
OWNER_NAMED = ("not_a_record", "constructed_forbidden", "unstable_cross")       # the refusal types the owner named for route (1)


def med(xs: List[int]) -> str:
    if not xs:
        return "-"
    m = statistics.median(xs)
    return str(int(m)) if m == int(m) else "%.1f" % m


def rng(xs: List[int]) -> str:
    return "-" if not xs else "%d-%d" % (min(xs), max(xs))


def collect(bank_path: str, runs: str, results: str) -> List[dict]:
    bank = S.load_bank(bank_path)
    gold = S.load_gold()
    out: List[dict] = []
    for row in bank.values():
        label = row["control"] if row.get("control") in S.CONTROLS else row["mode"]
        base = row.get("base") or row["task_id"].replace("/", "_")
        name = "%s.%s.api" % (base, label)
        rd = os.path.join(runs, name)
        rj = os.path.join(results, name + ".json")
        if not os.path.isdir(rd):
            out.append({"base": base, "mode": label, "missing": True, "question": row["text"]})
            continue
        rs = S.score_run(rd, bank, gold)
        et = 0                                       # `read` on an empty thread: ok, with `refusals: [empty_thread]` INSIDE the result (not a refused op, not a build attempt)
        if rs.verify_status == "OK":
            for r in S._rows_of(rd):
                if r["actor"] == "model" and r["op"] == "read" and r["result"].get("ok") is True and any(x.get("type") == "empty_thread" for x in r["result"].get("refusals") or []):
                    et += 1
        res = json.load(open(rj, encoding="utf-8")) if os.path.isfile(rj) else {}
        dr = res.get("driver_report") or {}
        out.append({"base": base, "mode": label, "missing": False, "question": row["text"], "status": rs.status, "outcome": rs.outcome, "verified": rs.verify_status == "OK" and rs.replay_verified,
                    "layer": rs.stop_layer, "L": rs.layer or {}, "text": rs.text, "answer_line": rs.answer_line, "control": rs.control, "kind": rs.kind,
                    "usage": dr.get("usage") or {}, "ended": dr.get("ended"), "wall_ns": (res.get("wall") or {}).get("driver_ns"),
                    "abstain_type": rs.abstain_type, "turns": dr.get("turns"), "empty_thread_reads": et})
    return out


def tables(R: List[dict]) -> str:
    out: List[str] = []
    p = out.append
    have = [r for r in R if not r["missing"]]
    p("RUNS: %d of %d in the bank; ledgers verified and replayed IDENTICAL: %d" % (len(have), len(R), sum(1 for r in have if r["verified"])))
    bad = [r for r in have if not r["verified"]]
    if bad:
        p("NOT VERIFIED: " + ", ".join("%s.%s" % (r["base"], r["mode"]) for r in bad))
    by: Dict[str, List[dict]] = OrderedDict((m, [r for r in have if r["mode"] == m]) for m in MODES)
    items = []
    for r in R:
        if r["base"] not in items:
            items.append(r["base"])

    p("")
    p("TABLE 1  What each condition did on the unanswerable items (every item is unanswerable: any output is a confident wrong answer)")
    p("| condition | n | answered / emitted text (confident wrong) | abstained (correct) | no output | not verified |")
    p("|---|---|---|---|---|---|")
    for m in MODES:
        rr = by[m]
        ans = sum(1 for r in rr if r["status"] == "answered_unans")
        ab = sum(1 for r in rr if r["status"] == "abstained_correct")
        no = sum(1 for r in rr if r["status"] == "no_output")
        nv = sum(1 for r in rr if r["status"] == "run_not_verified")
        tag = {"free_text": " (control, lookups)", "no_tools": " (control, no tools)"}.get(m, " (loom)")
        p("| %s%s | %d | %d | %d | %d | %d |" % (m, tag, len(rr), ans, ab, no, nv))

    p("")
    p("TABLE 2  The stop layer of each loom mode (L_meta = abstained with 0 weave/seat/add/emit attempts: the model's own re-check; L_struct = >=1 structural refusal, then abstained / no output; "
      "L_none_marked = emitted text with a constructed unit; L_none = emitted record-only text; L_other = outside the four)")
    p("| condition | n | L_meta | L_struct | L_none_marked | L_none | L_other | runs with a weave / seat / add / emit attempt | runs with >=1 structural refusal |")
    p("|---|---|---|---|---|---|---|---|---|")
    for m in LOOM_MODES + ("free_text", "no_tools"):
        rr = by[m]
        c = Counter(r["layer"] for r in rr)
        att = sum(1 for r in rr if r["L"].get("build_attempts", 0) > 0)
        st = sum(1 for r in rr if r["L"].get("struct_refusals_total", 0) > 0)
        p("| %s | %d | %d | %d | %d | %d | %d | %d | %d |" % (m, len(rr), c["L_meta"], c["L_struct"], c["L_none_marked"], c["L_none"], c["L_other"], att, st))
    p("(for the two controls the layer is read from the answer line: answered = L_none, 不明 = L_meta; there is no loom to refuse)")

    p("")
    p("TABLE 3  Route (1), the structural refusal: every loom run with a build attempt, the refusal types and how it ended")
    p("| run | stop layer | weave attempts | emit attempts | refusals (all) | structural refusals by type | outcome |")
    p("|---|---|---|---|---|---|---|")
    n3 = 0
    for m in LOOM_MODES:
        for r in by[m]:
            if r["L"].get("build_attempts", 0) > 0 or r["L"].get("struct_refusals_total", 0) > 0:
                n3 += 1
                L = r["L"]
                p("| %s.%s | %s%s | %d | %d | %d | %s | %s |" % (r["base"], m, r["layer"], (" (" + L["stop_layer_detail"] + ")") if L.get("stop_layer_detail") else "", L["weave_attempts"], L["emit_attempts"],
                                                                L["refusals"], json.dumps(L["struct_refusals"], ensure_ascii=False, sort_keys=True), r["status"] +
                                                                ((": " + r["text"]) if r["text"] else "")))
    if not n3:
        p("| (none: no loom run made any weave / seat / add / emit attempt) | | | | | | |")
    types = Counter()
    for m in LOOM_MODES:
        for r in by[m]:
            types.update(r["L"].get("struct_refusals", {}))
    p("structural refusal types over all loom runs: %s ; owner-named types (%s) fired: %s" % (
        json.dumps(dict(sorted(types.items())), ensure_ascii=False), ", ".join(OWNER_NAMED), json.dumps({t: types.get(t, 0) for t in OWNER_NAMED})))

    p("")
    p("TABLE 4  Route (2), the model's own re-check: what a run did BEFORE it ended (counts of model rows up to the closing row; per run: median, min-max)")
    p("| condition | n | lookups (median, range) | empty lookups | read_sentence | read | weave attempts | refusals | lookups of the abstained runs (median) |")
    p("|---|---|---|---|---|---|---|---|---|")
    for m in MODES:
        rr = by[m]
        g = lambda k: [r["L"].get(k, 0) for r in rr]
        ab = [r["L"].get("lookups", 0) for r in rr if r["status"] == "abstained_correct"]
        p("| %s | %d | %s (%s) | %s (%s) | %s (%s) | %s (%s) | %s (%s) | %s (%s) | %s (n=%d) |" % (
            m, len(rr), med(g("lookups")), rng(g("lookups")), med(g("empty_lookups")), rng(g("empty_lookups")), med(g("read_sentences")), rng(g("read_sentences")),
            med(g("reads")), rng(g("reads")), med(g("weave_attempts")), rng(g("weave_attempts")), med(g("refusals")), rng(g("refusals")), med(ab), len(ab)))
    p("totals (lookups / empty lookups / read_sentence / read / weave attempts): " + "; ".join(
        "%s %d/%d/%d/%d/%d" % (m, sum(r["L"].get("lookups", 0) for r in by[m]), sum(r["L"].get("empty_lookups", 0) for r in by[m]), sum(r["L"].get("read_sentences", 0) for r in by[m]),
                               sum(r["L"].get("reads", 0) for r in by[m]), sum(r["L"].get("weave_attempts", 0) for r in by[m])) for m in MODES))

    et = {m: sum(1 for r in by[m] if r.get("empty_thread_reads")) for m in LOOM_MODES}
    p("loom runs that called `read` on an EMPTY thread before abstaining (ok result carrying `empty_thread` inside; not a refused op, not a build attempt, the layer stays L_meta): " + "; ".join(
        "%s %d of %d" % (m, et[m], len(by[m])) for m in LOOM_MODES) + " ; " + (", ".join("%s.%s" % (r["base"], r["mode"]) for m in LOOM_MODES for r in by[m] if r.get("empty_thread_reads")) or "none"))

    p("")
    p("TABLE 5  Tokens (API-reported usage, testimony of the provider) and time")
    p("| condition | n | input tokens | output tokens | API calls | input per run (median) | input per run (max) | wall per run (median s) |")
    p("|---|---|---|---|---|---|---|---|")
    tot = Counter()
    for m in MODES:
        rr = by[m]
        i = [r["usage"].get("input_tokens", 0) for r in rr]
        o = [r["usage"].get("output_tokens", 0) for r in rr]
        c = [r["usage"].get("calls", 0) for r in rr]
        w = [int(r["wall_ns"] / 1e9) for r in rr if r["wall_ns"] is not None]
        tot.update({"i": sum(i), "o": sum(o), "c": sum(c)})
        p("| %s | %d | %s | %s | %d | %s | %s | %s |" % (m, len(rr), format(sum(i), ","), format(sum(o), ","), sum(c), format(int(statistics.median(i)) if i else 0, ","),
                                                         format(max(i) if i else 0, ","), med(w)))
    p("| all | %d | %s | %s | %d | | | |" % (len(have), format(tot["i"], ","), format(tot["o"], ","), tot["c"]))
    cr = sum(r["usage"].get("cache_read_input_tokens", 0) for r in have)
    cc = sum(r["usage"].get("cache_creation_input_tokens", 0) for r in have)
    p("cache read / creation input tokens (all runs): %s / %s" % (format(cr, ","), format(cc, ",")))
    ends = Counter((r["mode"], r["ended"]) for r in have)
    p("driver endings: " + "; ".join("%s %s %d" % (m, e, n) for (m, e), n in sorted(ends.items(), key=lambda kv: (MODES.index(kv[0][0]), str(kv[0][1])))))

    p("")
    p("TABLE 6  Per item: what each condition ended with (M = L_meta abstain, S = L_struct abstain, N = L_none_marked emit, E = L_none emit / control answered, O = L_other, - = missing; "
      "controls: 不明 = M, answered = E)")
    p("| item | question | record_only | constructed_allowed | free_text (lookups) | no_tools |")
    p("|---|---|---|---|---|---|")
    code = {"L_meta": "M", "L_struct": "S", "L_none_marked": "N", "L_none": "E", "L_other": "O"}
    cell = {(r["base"], r["mode"]): r for r in R}
    for b in items:
        cs = []
        for m in MODES:
            r = cell.get((b, m))
            if r is None or r["missing"]:
                cs.append("-")
                continue
            c = code.get(r["layer"], "?")
            cs.append(c + (": " + ((r["answer_line"] if r["control"] else r["text"]) or "")[:40].replace("|", "/") if c in "NE" else ""))
        q = cell[(b, MODES[0])]["question"]
        p("| %s | %s | %s |" % (b, q, " | ".join(cs)))

    p("")
    p("TABLE 7  The two controls against each other (the lookup control = free_text, the no-tools control = no_tools), per item")
    both = [b for b in items if (b, "free_text") in cell and (b, "no_tools") in cell and not cell[(b, "free_text")]["missing"] and not cell[(b, "no_tools")]["missing"]]
    ft_ab = lambda b: cell[(b, "free_text")]["layer"] == "L_meta"
    nt_ab = lambda b: cell[(b, "no_tools")]["layer"] == "L_meta"
    p("| | no_tools abstained | no_tools answered |")
    p("|---|---|---|")
    p("| free_text abstained | %d | %d |" % (sum(1 for b in both if ft_ab(b) and nt_ab(b)), sum(1 for b in both if ft_ab(b) and not nt_ab(b))))
    p("| free_text answered | %d | %d |" % (sum(1 for b in both if not ft_ab(b) and nt_ab(b)), sum(1 for b in both if not ft_ab(b) and not nt_ab(b))))
    p("items where no_tools ANSWERED and the lookup control abstained: " + (", ".join(b for b in both if ft_ab(b) and not nt_ab(b)) or "none"))
    p("items where the lookup control ANSWERED: " + (", ".join("%s (%s)" % (b, cell[(b, "free_text")]["answer_line"]) for b in both if not ft_ab(b)) or "none"))

    p("")
    p("TABLE 8  Every text a run emitted or answered (all of them are confident wrong answers: the item has no answer)")
    p("| run | layer | text |")
    p("|---|---|---|")
    n8 = 0
    for r in have:
        if r["status"] == "answered_unans":
            n8 += 1
            p("| %s.%s | %s | %s |" % (r["base"], r["mode"], r["layer"], ((r["answer_line"] if r["control"] else r["text"]) or "").replace("|", "/")))
    if not n8:
        p("| (none) | | |")
    return "\n".join(out) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bank", default=os.path.join(HERE, "tasks_unans.jsonl"))
    ap.add_argument("--runs", default=os.path.join(HERE, "runs_unans"))
    ap.add_argument("--results", default=os.path.join(HERE, "results_unans"))
    ap.add_argument("--write", action="store_true", help="write the tables to <results>/REPORT_TABLES.txt (never overwritten)")
    a = ap.parse_args(argv)
    text = tables(collect(a.bank, a.runs, a.results))
    print(text)
    if a.write:
        path = os.path.join(a.results, "REPORT_TABLES.txt")
        with open(path, "x", encoding="utf-8") as f:
            f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
