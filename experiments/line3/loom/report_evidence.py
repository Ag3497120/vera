"""LOOM-evidence-3 (L-LOOM-188): the tables of the re-measurement with the evidence gate.

    python experiments/line3/loom/report_evidence.py [--write]

The three NEW sets are the LOOM modes only (record_only, constructed_allowed) of bank2's 10 tasks (runs_h55e), bank2's 25 unanswerable items (runs_unans_e) and bank4's 35
adversarial items (runs_unans_adv_e); the controls are NOT re-run, the stored ones are the comparison (runs_h55d, runs_unans, runs_unans_adv).  Every ledger is VERIFIED
and replayed (report_unans.collect -> score.score_run) before it is counted.  The offline columns (the reach over the whole bank2, the codes of the unreachable items) are
computed from the corpus and bank2.tsv with verantyx/loom/evidence.py (no model).  With --write the text goes to results_h55e/REPORT_TABLES.txt (never overwritten).  The
narrative of REPORT.md is written by hand.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import statistics
import sys
from collections import Counter, OrderedDict
from typing import Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import report_unans as RU          # noqa: E402
import report_unans_adv as RAU     # noqa: E402

S = RU.S
LOOM = RU.LOOM_MODES
UNREACHABLE = ("I2-001", "I2-008", "I2-041", "R2-I013")
REACHABLE = ("I2-013", "I2-025", "I2-034")
ANSWERABLE = ("I2-001", "I2-008", "I2-013", "I2-025", "I2-034", "I2-041", "R2-I013")
BANK2_UNANS = ("UF-001", "UF-015", "R2-U003")
CONTENT = S.EVIDENCE_CONTENT_CODES
d = lambda *p: os.path.join(HERE, *p)


def collect_all():
    new = {"bank2": RU.collect(d("tasks_bank2.jsonl"), d("runs_h55e"), d("results_h55e")),
           "unans": RU.collect(d("tasks_unans.jsonl"), d("runs_unans_e"), d("results_unans_e")),
           "adv": RU.collect(d("tasks_unans_adv.jsonl"), d("runs_unans_adv_e"), d("results_unans_adv_e"))}
    old = {"bank2": RU.collect(d("tasks_bank2.jsonl"), d("runs_h55d"), d("results_h55d")),
           "unans": RU.collect(d("tasks_unans.jsonl"), d("runs_unans"), d("results_unans")),
           "adv": RU.collect(d("tasks_unans_adv.jsonl"), d("runs_unans_adv"), d("results_unans_adv"))}
    return new, old


def loom_only(R: List[dict]) -> List[dict]:
    return [r for r in R if r["mode"] in LOOM and not r["missing"]]


def codes_of(r: dict) -> Dict[str, int]:
    return r["L"].get("struct_codes", {})


def has_evidence(r: dict) -> bool:
    return any(k.startswith("no_evidence") for k in codes_of(r))


def content_level(r: dict) -> bool:
    return any(k.split(":", 1)[-1] in CONTENT for k in codes_of(r) if k.startswith("no_evidence:"))


def read_codes_of(r: dict) -> Dict[str, int]:
    return r["L"].get("read_codes", {})


def spoke_content(r: dict) -> bool:
    """The structure said, in a CONTENT code, that the quoted sentence does not answer the question: in a refused `emit` or in the result of a dry-run `read` (an ok call that
    lists the refusals an emit would give).  The strict stop layer (score.layer_report) counts only refused ops; this counts what the model was TOLD."""
    return any(k.split(":", 1)[-1] in CONTENT for k in list(codes_of(r)) + list(read_codes_of(r)) if k.startswith("no_evidence:"))


def attempted_emit(r: dict) -> bool:
    return r["L"].get("emit_attempts", 0) > 0


def reach_offline():
    """(reach list under each subject scope, per-item best failing codes) over the 69 answerable bank2 items, from the corpus (no model)."""
    from verantyx.loom import evidence as ev
    from verantyx.loom.corpus import Corpus
    corpus = Corpus.load(open(os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl"), "rb").read())
    rows = [r for r in csv.DictReader(open(os.path.join(ROOT, "experiments/line3/bank2/bank2.tsv"), encoding="utf-8"), delimiter="\t")
            if r["kind"] == "intra2" and r["corpus"] == "fulllead"]
    reach = {ev.SCOPE_TITLE: [], ev.SCOPE_CLAUSE: []}
    why: Dict[str, dict] = {}
    for r in rows:
        qu = ev.question_units(r["question"])
        occ = []
        for alt in r["gold"].split("|"):
            for sid in range(corpus.n_sentences):
                v = ev.view_of(corpus, sid)
                pos = v.text.find(alt)
                while pos >= 0:
                    end = pos + len(alt)
                    i0 = next((k for k, s in enumerate(v.spans) if s[0] == pos), None)
                    i1 = next((k for k, s in enumerate(v.spans) if s[1] == end), None)
                    if i0 is not None and i1 is not None and i0 <= i1:
                        occ.append((sid, i0, i1))
                    pos = v.text.find(alt, pos + 1)
        for scope in reach:
            js = [ev.judge_quote(corpus, qu, scope, sid, "WORD", i0, i1) for sid, i0, i1 in occ]
            if any(not j["codes"] for j in js):
                reach[scope].append(r["#id"])
            elif scope == ev.SCOPE_TITLE:
                best = min(js, key=lambda j: (len(j["codes"]), j["codes"]), default=None)
                why[r["#id"]] = {"form": qu.form, "occurrences": len(js), "codes": ["gold_not_word_aligned"] if best is None else best["codes"]}
    return reach, why, len(rows)


def final_threads(sets: dict) -> List[dict]:
    """For every loom run of the new sets: the weave_span rows whose crosses were not dropped (the FINAL THREAD, in ledger order) -- what an emit would have quoted."""
    from verantyx.loom import ledger as lg
    out = []
    for k, R in sets.items():
        for r in R:
            if r["missing"] or r["mode"] not in LOOM:
                continue
            rdir = d({"bank2": "runs_h55e", "unans": "runs_unans_e", "adv": "runs_unans_adv_e"}[k], "%s.%s.api" % (r["base"], r["mode"]))
            rows = [json.loads(ln) for ln in lg.read_lines(rdir)[0]]
            made, dropped = [], set()
            for x in rows:
                if x["actor"] != "model" or x["result"].get("ok") is not True:
                    continue
                if x["op"] == "weave_span":
                    made.append((x["result"]["sid"], x["result"]["tier"], x["result"]["from"], x["result"]["to"], [c["cid"] for c in x["result"]["crosses"]]))
                elif x["op"] == "drop":
                    dropped.add(x["result"]["cid"])
            ws = [m[:4] for m in made if not set(m[4]) & dropped]
            out.append(dict(r, set=k, weaves=ws, question_text=rows[0]["result"]["task"]["text"]))
    return out


def tables() -> str:
    new, old = collect_all()
    b4 = RAU.load_bank4()
    out: List[str] = []
    p = out.append

    for k in new:
        have = loom_only(new[k])
        p("RUNS %s: %d loom runs; ledgers verified and replayed IDENTICAL: %d%s" % (k, len(have), sum(1 for r in have if r["verified"]),
                                                                                   "" if all(r["verified"] for r in have) else "   NOT VERIFIED: " +
                                                                                   ", ".join("%s.%s" % (r["base"], r["mode"]) for r in have if not r["verified"])))
    p("")

    # ---- E1: bank2 tasks ------------------------------------------------------------------------------------------------------------------------------
    p("TABLE E1  bank2 tasks (10 x record_only / constructed_allowed): what each run ended with, now (e) and in h55d (d, no gate).  exact = hit_exact (the headline).")
    p("| task | mode | status e | exact e | text e | stop layer e | emit refusals e (struct codes) | ops e | input tokens e | status d | exact d | text d |")
    p("|---|---|---|---|---|---|---|---|---|---|---|---|")
    ne = {(r["base"], r["mode"]): r for r in new["bank2"] if not r["missing"]}
    od = {(r["base"], r["mode"]): r for r in old["bank2"] if not r["missing"]}
    order = list(ANSWERABLE) + list(BANK2_UNANS)
    for b in order:
        for m in LOOM:
            e, o = ne.get((b, m)), od.get((b, m))
            if e is None:
                p("| %s | %s | (missing) | | | | | | | | | |" % (b, m))
                continue
            p("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
                b, m, e["status"], "Y" if e["hit_exact"] else "-", (e["text"] or "").replace("|", "/") or "(none)", e["layer"],
                json.dumps(codes_of(e), ensure_ascii=False, sort_keys=True), e["ops_total"], format((e["usage"] or {}).get("input_tokens", 0), ","),
                o["status"], "Y" if o["hit_exact"] else "-", (o["text"] or "").replace("|", "/") or "(none)"))
    p("")
    p("TABLE E2  bank2 answerable (7): exact hits, and where the other answerable runs ended")
    p("| mode | exact e /7 | exact d /7 | emitted not exact e | abstained e | no output e | emitted at all e |")
    p("|---|---|---|---|---|---|---|")
    for m in LOOM:
        ee = [ne[(b, m)] for b in ANSWERABLE if (b, m) in ne]
        dd = [od[(b, m)] for b in ANSWERABLE if (b, m) in od]
        p("| %s | %d/%d | %d/%d | %d | %d | %d | %d |" % (m, sum(1 for r in ee if r["hit_exact"]), len(ee), sum(1 for r in dd if r["hit_exact"]), len(dd),
                                                          sum(1 for r in ee if r["status"] == "miss"), sum(1 for r in ee if r["status"] == "abstained_wrong"),
                                                          sum(1 for r in ee if r["status"] == "no_output"), sum(1 for r in ee if r["text"] is not None)))
    un = [ne[(b, m)] for b in UNREACHABLE for m in LOOM if (b, m) in ne]
    p("")
    p("P-EV-3 rows: the four unreachable items (%s), %d runs: exact hits %d; runs with >= 1 no_evidence refusal %d; emitted a text %d (%s); abstained %d" % (
        ", ".join(UNREACHABLE), len(un), sum(1 for r in un if r["hit_exact"]), sum(1 for r in un if has_evidence(r)), sum(1 for r in un if r["text"] is not None),
        "; ".join("%s.%s 「%s」" % (r["base"], r["mode"], r["text"]) for r in un if r["text"] is not None) or "none", sum(1 for r in un if r["status"] == "abstained_wrong")))
    rc = [ne[(b, m)] for b in REACHABLE for m in LOOM if (b, m) in ne]
    p("the three reachable items (%s), %d runs: exact hits %d; emitted %d; abstained %d; no_evidence refusals met %d" % (
        ", ".join(REACHABLE), len(rc), sum(1 for r in rc if r["hit_exact"]), sum(1 for r in rc if r["text"] is not None), sum(1 for r in rc if r["status"] == "abstained_wrong"),
        sum(1 for r in rc if has_evidence(r))))
    p("")

    # ---- E3: the stop layers, L_struct by code ---------------------------------------------------------------------------------------------------------
    p("TABLE E3  The stop layer of each loom mode on each set, and the structural refusals BY CODE (a run is counted once per code; `no_evidence:<code>` is a code of the evidence gate)")
    p("| set | mode | n | L_meta | L_struct | L_none_marked | L_none | L_other | runs with a structural refusal | emitted a text (on unans: confident wrong) |")
    p("|---|---|---|---|---|---|---|---|---|---|")
    for k, lab in (("bank2", "bank2 tasks (10)"), ("unans", "bank2 unans (25)"), ("adv", "bank4 (35)")):
        for m in LOOM:
            rr = [r for r in loom_only(new[k]) if r["mode"] == m]
            c = Counter(r["layer"] for r in rr)
            p("| %s | %s | %d | %d | %d | %d | %d | %d | %d | %d |" % (lab, m, len(rr), c["L_meta"], c["L_struct"], c["L_none_marked"], c["L_none"], c["L_other"],
                                                                      sum(1 for r in rr if r["L"].get("struct_refusals_total", 0) > 0), sum(1 for r in rr if r["text"] is not None)))
    p("")
    p("| set | mode | structural codes (runs) |")
    p("|---|---|---|")
    for k, lab in (("bank2", "bank2 tasks"), ("unans", "bank2 unans"), ("adv", "bank4")):
        for m in LOOM:
            cc = Counter()
            for r in loom_only(new[k]):
                if r["mode"] == m:
                    cc.update(codes_of(r).keys())
            p("| %s | %s | %s |" % (lab, m, json.dumps(dict(sorted(cc.items())), ensure_ascii=False) or "{}"))
    p("")
    p("| set | mode | codes shown by a dry-run `read` (an ok call that lists what emit would refuse; runs) |")
    p("|---|---|---|")
    for k, lab in (("bank2", "bank2 tasks"), ("unans", "bank2 unans"), ("adv", "bank4")):
        for m in LOOM:
            cc = Counter()
            for r in loom_only(new[k]):
                if r["mode"] == m:
                    cc.update(read_codes_of(r).keys())
            p("| %s | %s | %s |" % (lab, m, json.dumps(dict(sorted(cc.items())), ensure_ascii=False) or "{}"))
    p("")
    p("TABLE E3b  Every loom run of the three sets that made a build attempt (weave / seat / add / emit): the layer, the refusals by code, the outcome")
    p("| run | layer | weave | read | emit | refused-op codes | codes shown by a dry-run `read` | outcome |")
    p("|---|---|---|---|---|---|---|---|")
    for k in ("bank2", "unans", "adv"):
        for r in loom_only(new[k]):
            L = r["L"]
            if L.get("build_attempts", 0) > 0 or L.get("read_codes"):
                p("| %s.%s.%s | %s%s | %d | %d | %d | %s | %s | %s |" % (k, r["base"], r["mode"], r["layer"], (" (" + L["stop_layer_detail"] + ")") if L.get("stop_layer_detail") else "",
                                                                   L["weave_attempts"], L["reads"], L["emit_attempts"], json.dumps(codes_of(r), ensure_ascii=False, sort_keys=True),
                                                                   json.dumps(read_codes_of(r), ensure_ascii=False, sort_keys=True), r["status"] + ((": " + r["text"]) if r["text"] else "")))
    p("")

    # ---- E4: bank2 unans ----------------------------------------------------------------------------------------------------------------------------------
    p("TABLE E4  bank2 unanswerable (25): emitted texts, route (2), and every run that tried to emit")
    p("| mode | n | emitted | L_meta (route 2) | L_struct | runs that attempted an emit | of those ended L_struct with no_evidence |")
    p("|---|---|---|---|---|---|---|")
    for m in LOOM:
        rr = [r for r in loom_only(new["unans"]) if r["mode"] == m]
        em = [r for r in rr if attempted_emit(r)]
        p("| %s | %d | %d | %d | %d | %d | %d |" % (m, len(rr), sum(1 for r in rr if r["text"] is not None), sum(1 for r in rr if r["layer"] == "L_meta"),
                                                    sum(1 for r in rr if r["layer"] == "L_struct"), len(em), sum(1 for r in em if r["layer"] == "L_struct" and has_evidence(r))))
    p("")

    # ---- E5: bank4 ---------------------------------------------------------------------------------------------------------------------------------------
    p("TABLE E5  bank4 (35): confident wrong, the trap value, content-level structural refusals (no_evidence with a content code), by kind.  `strict` = a refused op (emit) ended the run (L_struct); "
      "`told` = the content-level code was shown in a refused emit OR in a dry-run `read`, and the run ended without a text")
    p("| mode | n | confident wrong | = trap | mentions trap | content-level refusals, strict (L_struct) | content-level code told (emit or read), no text | L_meta | L_other |")
    p("|---|---|---|---|---|---|---|---|---|")
    kinds = list(OrderedDict((v["kind"], 1) for v in b4.values()).keys())
    for m in LOOM:
        rr = [r for r in loom_only(new["adv"]) if r["mode"] == m]
        wrong = [r for r in rr if r["status"] == "answered_unans"]
        tr = [r for r in wrong if RAU.equals_trap(RAU.emitted(r), b4[r["base"]]["trap"])]
        mt = [r for r in wrong if RAU.mentions_trap(RAU.emitted(r), b4[r["base"]]["trap"])]
        p("| %s | %d | %d | %d | %d | %d | %d | %d | %d |" % (m, len(rr), len(wrong), len(tr), len(mt), sum(1 for r in rr if r["layer"] == "L_struct" and content_level(r)),
                                                              sum(1 for r in rr if spoke_content(r) and r["text"] is None), sum(1 for r in rr if r["layer"] == "L_meta"),
                                                              sum(1 for r in rr if r["layer"] == "L_other")))
    p("")
    p("| kind | n items | " + " | ".join("%s wrong / content code told" % m for m in LOOM) + " |")
    p("|---|---|" + "---|" * len(LOOM))
    for k_ in kinds:
        its = [b for b in b4 if b4[b]["kind"] == k_]
        cells = []
        for m in LOOM:
            rr = [r for r in loom_only(new["adv"]) if r["mode"] == m and r["base"] in its]
            cells.append("%d / %d" % (sum(1 for r in rr if r["status"] == "answered_unans"), sum(1 for r in rr if spoke_content(r) and r["text"] is None)))
        p("| %s | %d | %s |" % (k_, len(its), " | ".join(cells)))
    p("")
    p("TABLE E5b  ADV-001 and ADV-010 (the two items whose trap was emitted before, results_unans_adv): then and now")
    p("| item | mode | before (d: no gate) | now (e) | now: structural codes |")
    p("|---|---|---|---|---|")
    oa = {(r["base"], r["mode"]): r for r in old["adv"] if not r["missing"]}
    na = {(r["base"], r["mode"]): r for r in new["adv"] if not r["missing"]}
    for b in ("ADV-001", "ADV-010"):
        for m in LOOM:
            o, e = oa.get((b, m)), na.get((b, m))
            f = lambda r: "(missing)" if r is None else ("%s: %s" % (r["layer"], r["text"]) if r["text"] else "%s %s" % (r["layer"], r["status"]))
            p("| %s | %s | %s | %s | %s |" % (b, m, f(o), f(e), (json.dumps(dict(codes_of(e), **{"read:" + k: v for k, v in read_codes_of(e).items()}), ensure_ascii=False, sort_keys=True)) if e else ""))
    p("")

    # ---- E6: the combined two-route table -------------------------------------------------------------------------------------------------------------------
    p("TABLE E6  THE TWO ROUTES over the 60 unanswerable items (bank2 25 + bank4 35) x 2 loom modes = 120 runs.  Route (1) = the structure refused and the run ended without a text "
      "(L_struct);  route (2) = the model re-checked and abstained with 0 build attempts (L_meta);  wrong = a text went out.")
    p("| measurement | mode | runs | wrong (text emitted) | route (1) strict: L_struct | of which content-level no_evidence | of which no_evidence by construction only | of which other types | "
      "route (1) via dry-run read: content-level code shown, then abstained (L_other/L_meta) | route (2) L_meta | L_other | structure fired and the run emitted anyway |")
    p("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for lab, sets in (("before (no gate: results_unans + results_unans_adv)", (old["unans"], old["adv"])), ("now (e: evidence.v1)", (new["unans"], new["adv"]))):
        for m in LOOM:
            rr = [r for s_ in sets for r in loom_only(s_) if r["mode"] == m]
            st = [r for r in rr if r["layer"] == "L_struct"]
            cl = [r for r in st if content_level(r)]
            cons = [r for r in st if has_evidence(r) and not content_level(r)]
            oth = [r for r in st if not has_evidence(r)]
            via_read = [r for r in rr if r["layer"] != "L_struct" and r["text"] is None and spoke_content(r)]
            p("| %s | %s | %d | %d | %d | %d | %d | %d | %d | %d | %d | %d |" % (
                lab, m, len(rr), sum(1 for r in rr if r["text"] is not None), len(st), len(cl), len(cons), len(oth), len(via_read), sum(1 for r in rr if r["layer"] == "L_meta"),
                sum(1 for r in rr if r["layer"] == "L_other"), sum(1 for r in rr if r["text"] is not None and r["L"].get("struct_refusals_before_emit", 0) > 0)))
    tot_new = [r for s_ in (new["unans"], new["adv"]) for r in loom_only(s_)]
    told = [r for r in tot_new if r["text"] is None and spoke_content(r)]
    p("now, both modes together: %d runs; wrong %d; route (1) strict (a refused op ended the run) %d (%.1f%%); route (1) as TOLD (a content-level no_evidence code in a refused emit or a dry-run `read`, "
      "no text) %d (%.1f%%); route (2) L_meta %d (%.1f%%); neither (L_other without a told code, or other) %d" % (
        len(tot_new), sum(1 for r in tot_new if r["text"] is not None), sum(1 for r in tot_new if r["layer"] == "L_struct"),
        100.0 * sum(1 for r in tot_new if r["layer"] == "L_struct") / max(1, len(tot_new)), len(told), 100.0 * len(told) / max(1, len(tot_new)),
        sum(1 for r in tot_new if r["layer"] == "L_meta"), 100.0 * sum(1 for r in tot_new if r["layer"] == "L_meta") / max(1, len(tot_new)),
        sum(1 for r in tot_new if r["text"] is None and r["layer"] != "L_meta" and not spoke_content(r))))
    p("")
    p("controls (stored, NOT re-run) over the same 60 items: lookup control wrong %d, no-tools control wrong %d" % (
        sum(1 for s_ in (old["unans"], old["adv"]) for r in s_ if not r["missing"] and r["mode"] == "free_text" and r["status"] == "answered_unans"),
        sum(1 for s_ in (old["unans"], old["adv"]) for r in s_ if not r["missing"] and r["mode"] == "no_tools" and r["status"] == "answered_unans")))
    p("")

    # ---- E7: tokens ----------------------------------------------------------------------------------------------------------------------------------------
    p("TABLE E7  Tokens (API-reported usage, testimony) and time of the e runs, and of the d runs they are compared with")
    p("| set | mode | n | input tokens | output tokens | API calls | input per run (median) | input per run (max) | wall per run (median s) | ops per run (median) |")
    p("|---|---|---|---|---|---|---|---|---|---|")
    for lab, sets in (("e", new), ("before", old)):
        for k, nm in (("bank2", "bank2 tasks"), ("unans", "bank2 unans"), ("adv", "bank4")):
            for m in LOOM:
                rr = [r for r in loom_only(sets[k]) if r["mode"] == m]
                i = [r["usage"].get("input_tokens", 0) for r in rr]
                o = [r["usage"].get("output_tokens", 0) for r in rr]
                c = [r["usage"].get("calls", 0) for r in rr]
                w = [int(r["wall_ns"] / 1e9) for r in rr if r["wall_ns"] is not None]
                ops = [r["ops_total"] for r in rr if r["ops_total"] is not None]
                p("| %s %s | %s | %d | %s | %s | %d | %s | %s | %s | %s |" % (lab, nm, m, len(rr), format(sum(i), ","), format(sum(o), ","), sum(c), format(int(statistics.median(i)) if i else 0, ","),
                                                                              format(max(i) if i else 0, ","), RU.med(w), RU.med(ops)))
    a14e = [ne[(b, m)] for b in ANSWERABLE for m in LOOM if (b, m) in ne]
    a14d = [od[(b, m)] for b in ANSWERABLE for m in LOOM if (b, m) in od]
    me = statistics.median([r["usage"].get("input_tokens", 0) for r in a14e]) if a14e else 0
    md = statistics.median([r["usage"].get("input_tokens", 0) for r in a14d]) if a14d else 0
    p("answerable loom runs (%d e, %d d): median input tokens e %s, d %s, ratio %s" % (len(a14e), len(a14d), format(int(me), ","), format(int(md), ","),
                                                                                       "%.2f" % (me / md) if md else "n/a"))
    ends = Counter((k, r["mode"], r["ended"]) for k in new for r in loom_only(new[k]))
    p("driver endings (e): " + "; ".join("%s %s %s %d" % (k, m, e, n) for (k, m, e), n in sorted(ends.items(), key=lambda kv: str(kv[0]))))
    p("")

    # ---- E9: the gate on the final threads (offline, both subject scopes) -------------------------------------------------------------------------------
    from verantyx.loom import evidence as ev
    from verantyx.loom.corpus import Corpus
    corpus = Corpus.load(open(os.path.join(ROOT, "experiments/line3/bank2/data/fulllead_sents.jsonl"), "rb").read())
    ft = [f for f in final_threads(new) if f["weaves"]]
    p("TABLE E9  The gate on the FINAL THREAD of every new loom run that left a non-empty thread (what an emit would have quoted; offline, both subject scopes).  A thread passes only if every weave passes.")
    p("| set | run | final weaves (sentence: stretch) | gate (a) clause_or_title | gate (b) clause | emitted? |")
    p("|---|---|---|---|---|---|")
    npass = {"a": 0, "b": 0}
    cnt = Counter()
    for f in ft:
        qu = ev.question_units(f["question_text"])
        verd = {}
        for tag, scope in (("a", ev.SCOPE_TITLE), ("b", ev.SCOPE_CLAUSE)):
            js = [ev.judge_quote(corpus, qu, scope, sid, tier, i0, i1) for sid, tier, i0, i1 in f["weaves"]]
            verd[tag] = "PASS" if all(not j["codes"] for j in js) else "refused " + "; ".join("%s:%s" % (j["answer"], "+".join(j["codes"])) for j in js if j["codes"])
            npass[tag] += verd[tag] == "PASS"
        cnt[(f["set"], f["mode"], verd["a"] == "PASS")] += 1
        sts = "; ".join("%d:%s" % (sid, ev.view_of(corpus, sid).text[corpus.spans().spans(tier, sid)[i0][0]:corpus.spans().spans(tier, sid)[i1][1]]) for sid, tier, i0, i1 in f["weaves"])
        p("| %s | %s.%s | %s | %s | %s | %s |" % (f["set"], f["base"], f["mode"], sts.replace("|", "/"), verd["a"], verd["b"], ("YES: " + f["text"]) if f["text"] else "no"))
    p("runs with a non-empty final thread: %d; the thread passes the gate under (a): %d, under (b): %d; unanswerable-item threads that pass under (a): %d" % (
        len(ft), npass["a"], npass["b"], sum(1 for f in ft if f["set"] != "bank2" or f["base"] in BANK2_UNANS) and sum(
            1 for f in ft if (f["set"] != "bank2" or f["base"] in BANK2_UNANS) and all(
                not ev.judge_quote(corpus, ev.question_units(f["question_text"]), ev.SCOPE_TITLE, sid, tier, i0, i1)["codes"] for sid, tier, i0, i1 in f["weaves"]))))
    p("")

    # ---- E8: reach (offline) -------------------------------------------------------------------------------------------------------------------------------
    reach, why, n69 = reach_offline()
    p("TABLE E8  The reach over the whole bank2 (offline, from the corpus: %d answerable items; an item is reachable when some gold occurrence passes the gate)" % n69)
    p("clause_or_title (the owner's answer, OP-EV-1 a): %d of %d reachable: %s" % (len(reach["clause_or_title"]), n69, ", ".join(reach["clause_or_title"])))
    p("clause only (OP-EV-1 b): %d of %d reachable" % (len(reach["clause"]), n69))
    cc = Counter(c for v in why.values() for c in v["codes"])
    p("the %d unreachable items, by the codes of their best occurrence (an item can carry several): %s" % (len(why), json.dumps(dict(cc.most_common()), ensure_ascii=False)))
    p("the 7 loom answerable tasks: " + "; ".join("%s %s" % (b, "reachable" if b in reach["clause_or_title"] else "UNREACHABLE (%s, %s)" % (why[b]["form"], "+".join(why[b]["codes"])))
                                                for b in ANSWERABLE))
    return "\n".join(out) + "\n"


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="write results_h55e/REPORT_TABLES.txt (never overwritten)")
    a = ap.parse_args(argv)
    text = tables()
    print(text)
    if a.write:
        with open(d("results_h55e", "REPORT_TABLES.txt"), "x", encoding="utf-8") as f:
            f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
