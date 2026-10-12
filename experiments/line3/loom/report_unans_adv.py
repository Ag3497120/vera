"""LOOM-control-adv (L-LOOM-165..): the extra tables of the bank4 adversarial-unanswerable sweep, on top of report_unans.py's eight.

    python experiments/line3/loom/report_unans_adv.py [--write]

Reads tasks_unans_adv.jsonl / runs_unans_adv / results_unans_adv (and, for the combined table, tasks_unans.jsonl / runs_unans / results_unans), the kind and the trap answer
of each item from experiments/line3/bank4/bank4.tsv (the trap = notes field c).  Verifies every ledger through report_unans.collect (chain + replay).  Nothing calls a model.
`equals trap` is a mechanical text test (the NFKC, punctuation-stripped emitted text and the trap contain one another); every flagged / unflagged emit is read by hand in REPORT.md.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import unicodedata
from collections import Counter, OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import report_unans as RU  # noqa: E402

BANK4 = os.path.join(os.path.dirname(HERE), "bank4", "bank4.tsv")
MODES = RU.MODES
LOOM = RU.LOOM_MODES


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    return re.sub(r"[\s\W_]+", "", s)


def load_bank4():
    out = OrderedDict()
    with open(BANK4, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            m = re.search(r"c\)\s*(.*)$", r["notes"])
            out[r["#id"]] = {"kind": r["kind"], "question": r["question"], "trap": (m.group(1).strip() if m else ""), "audit": r["audit"]}
    return out


def emitted(r):
    return ((r["answer_line"] if r["control"] else r["text"]) or "").strip()


def equals_trap(txt, trap):
    """The emitted / answered text IS the trap (normalised equality)."""
    a, b = norm(txt), norm(trap)
    return bool(a and b and a == b)


def mentions_trap(txt, trap):
    """The text contains the trap string inside a longer answer (the main value is something else, or the trap is a qualifier)."""
    a, b = norm(txt), norm(trap)
    return bool(a and b and a != b and b in a)


def tag(txt, trap):
    return "=trap" if equals_trap(txt, trap) else ("mentions trap" if mentions_trap(txt, trap) else "other")


def outside_knowledge():
    """item -> the auditor's 'outside knowledge' label (AUDIT4.md table): yes / partial / no / -."""
    out = {}
    with open(os.path.join(os.path.dirname(HERE), "bank4", "AUDIT4.md"), encoding="utf-8") as f:
        for ln in f:
            c = [x.strip() for x in ln.split("|")]
            if len(c) > 6 and re.fullmatch(r"ADV-\d+", c[1]):
                out[c[1]] = c[5]
    return out


def tables(adv, b2, b4):
    out = []
    p = out.append
    have = [r for r in adv if not r["missing"]]
    cell = {(r["base"], r["mode"]): r for r in adv}
    items = list(b4.keys())
    kinds = list(OrderedDict((v["kind"], 1) for v in b4.values()).keys())

    p("TABLE A1  Confident wrong (any emitted / answered text) per condition, and how many equal the trap answer (mechanical test; see per-item table)")
    p("| condition | n | confident wrong | = trap (text IS the trap) | mentions trap inside a longer answer | other text | abstained | (of confident wrong: empty reply) |")
    p("|---|---|---|---|---|---|---|---|")
    for m in MODES:
        rr = [r for r in have if r["mode"] == m]
        ans = [r for r in rr if r["status"] == "answered_unans"]
        t = [r for r in ans if equals_trap(emitted(r), b4[r["base"]]["trap"])]
        mt = [r for r in ans if mentions_trap(emitted(r), b4[r["base"]]["trap"])]
        p("| %s | %d | %d | %d | %d | %d | %d | %d |" % (m, len(rr), len(ans), len(t), len(mt), len(ans) - len(t) - len(mt), sum(1 for r in rr if r["status"] == "abstained_correct"),
                                                   sum(1 for r in ans if not emitted(r))))

    p("")
    p("TABLE A2  Stop layer per condition and per kind (L_meta / L_struct / L_none_marked / L_none / L_other)")
    p("| condition | kind | n | L_meta | L_struct | L_none_marked | L_none | L_other | runs with a build attempt | structural refusals (runs) |")
    p("|---|---|---|---|---|---|---|---|---|---|")
    for m in MODES:
        for k in kinds + ["ALL"]:
            rr = [r for r in have if r["mode"] == m and (k == "ALL" or b4[r["base"]]["kind"] == k)]
            c = Counter(r["layer"] for r in rr)
            att = sum(1 for r in rr if r["L"].get("build_attempts", 0) > 0)
            st = sum(1 for r in rr if r["L"].get("struct_refusals_total", 0) > 0)
            p("| %s | %s | %d | %d | %d | %d | %d | %d | %d | %d |" % (m, k, len(rr), c["L_meta"], c["L_struct"], c["L_none_marked"], c["L_none"], c["L_other"], att, st))

    p("")
    p("TABLE A3  Per item: kind, trap answer (bank4.tsv notes c), and for each condition: M/S abstain, or the emitted / answered text with [=trap] or [other]")
    p("| item | kind | trap | record_only | constructed_allowed | free_text | no_tools |")
    p("|---|---|---|---|---|---|---|")
    code = {"L_meta": "M", "L_struct": "S", "L_none_marked": "N", "L_none": "E", "L_other": "O"}
    for b in items:
        cs = []
        for m in MODES:
            r = cell.get((b, m))
            if r is None or r["missing"]:
                cs.append("-")
                continue
            if r["status"] == "answered_unans":
                t = emitted(r).replace("|", "/")
                cs.append("%s: %s [%s]" % (code.get(r["layer"], "?"), t if t else "(empty reply)", tag(t, b4[b]["trap"])))
            else:
                cs.append(code.get(r["layer"], "?") + ("" if r["status"] == "abstained_correct" else " (%s)" % r["status"]))
        p("| %s | %s | %s | %s |" % (b, b4[b]["kind"], b4[b]["trap"], " | ".join(cs)))

    p("")
    p("TABLE A4  Per kind: confident wrong by condition (n items per kind)")
    p("| kind | n items | " + " | ".join(MODES) + " |")
    p("|---|---|" + "---|" * len(MODES))
    for k in kinds:
        its = [b for b in items if b4[b]["kind"] == k]
        row = []
        for m in MODES:
            ans = [b for b in its if (b, m) in cell and not cell[(b, m)]["missing"] and cell[(b, m)]["status"] == "answered_unans"]
            row.append("%d" % len(ans))
        p("| %s | %d | %s |" % (k, len(its), " | ".join(row)))

    p("")
    p("TABLE A5  L_struct runs (>=1 structural refusal): refusal types, and every run with a build attempt")
    p("| run | kind | layer | weave | emit | refusals | structural refusals by type | of which before an emit | outcome |")
    p("|---|---|---|---|---|---|---|---|---|")
    n = 0
    types = Counter()
    for m in LOOM:
        for r in have:
            if r["mode"] != m:
                continue
            L = r["L"]
            if L.get("build_attempts", 0) > 0 or L.get("struct_refusals_total", 0) > 0:
                n += 1
                types.update(L.get("struct_refusals", {}))
                p("| %s.%s | %s | %s%s | %d | %d | %d | %s | %s | %s |" % (r["base"], m, b4[r["base"]]["kind"], r["layer"], (" (" + L["stop_layer_detail"] + ")") if L.get("stop_layer_detail") else "",
                                                                  L["weave_attempts"], L["emit_attempts"], L["refusals"], json.dumps(L["struct_refusals"], ensure_ascii=False, sort_keys=True),
                                                                  L.get("struct_refusals_before_emit", 0), r["status"] + ((": " + r["text"]) if r["text"] else "")))
    if not n:
        p("| (none) | | | | | | | | |")
    p("structural refusal types over all loom runs: %s" % json.dumps(dict(sorted(types.items())), ensure_ascii=False))

    p("")
    p("TABLE A6  L_none_marked runs (constructed_allowed emitted a marked constructed unit) with the text")
    p("| run | kind | trap | text | = trap |")
    p("|---|---|---|---|---|")
    n = 0
    for r in have:
        if r["layer"] == "L_none_marked":
            n += 1
            t = r["text"].replace("|", "/")
            p("| %s.%s | %s | %s | %s | %s |" % (r["base"], r["mode"], b4[r["base"]]["kind"], b4[r["base"]]["trap"], t, tag(t, b4[r["base"]]["trap"])))
    if not n:
        p("| (none) | | | | |")

    p("")
    p("TABLE A7  Combined with the bank2 unanswerables (bank2 n=25, bank4 n=35)")
    p("| condition | bank2 n | bank2 confident wrong | bank2 L_meta / L_struct / L_none_marked / L_none | bank4 n | bank4 confident wrong | bank4 L_meta / L_struct / L_none_marked / L_none | all n | all confident wrong |")
    p("|---|---|---|---|---|---|---|---|---|")
    for m in MODES:
        a = [r for r in b2 if not r["missing"] and r["mode"] == m]
        d = [r for r in have if r["mode"] == m]
        f = lambda rr: "/".join(str(sum(1 for r in rr if r["layer"] == l)) for l in ("L_meta", "L_struct", "L_none_marked", "L_none"))
        wa = sum(1 for r in a if r["status"] == "answered_unans")
        wd = sum(1 for r in d if r["status"] == "answered_unans")
        p("| %s | %d | %d | %s | %d | %d | %s | %d | %d |" % (m, len(a), wa, f(a), len(d), wd, f(d), len(a) + len(d), wa + wd))

    p("")
    p("TABLE A8  Route (2) effort and tokens per condition on bank4 vs bank2 (median lookups per run; input tokens total)")
    p("| condition | bank2 lookups median | bank4 lookups median | bank2 input tokens | bank4 input tokens | bank4 output tokens | bank4 API calls |")
    p("|---|---|---|---|---|---|---|")
    import statistics
    for m in MODES:
        a = [r for r in b2 if not r["missing"] and r["mode"] == m]
        d = [r for r in have if r["mode"] == m]
        lm = lambda rr: statistics.median([r["L"].get("lookups", 0) for r in rr]) if rr else 0
        ti = lambda rr: sum(r["usage"].get("input_tokens", 0) for r in rr)
        p("| %s | %s | %s | %s | %s | %s | %d |" % (m, lm(a), lm(d), format(ti(a), ","), format(ti(d), ","), format(sum(r["usage"].get("output_tokens", 0) for r in d), ","),
                                                    sum(r["usage"].get("calls", 0) for r in d)))
    p("")
    p("TABLE A9  The confident wrong of the controls by the auditor's 'outside knowledge' label (AUDIT4.md: could a strong LLM answer this item from memory)")
    ok = outside_knowledge()
    p("| label | items | free_text answered | no_tools answered | loom (record_only + constructed_allowed) emitted |")
    p("|---|---|---|---|---|")
    for lab in ("yes", "partial", "no"):
        its = [b for b in items if ok.get(b, "-").split(" ")[0] == lab]
        f = lambda m: sum(1 for b in its if (b, m) in cell and not cell[(b, m)]["missing"] and cell[(b, m)]["status"] == "answered_unans")
        p("| %s | %d | %d | %d | %d |" % (lab, len(its), f("free_text"), f("no_tools"), f("record_only") + f("constructed_allowed")))
    return "\n".join(out) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="write results_unans_adv/REPORT_ADV_TABLES.txt (never overwritten)")
    a = ap.parse_args(argv)
    adv = RU.collect(os.path.join(HERE, "tasks_unans_adv.jsonl"), os.path.join(HERE, "runs_unans_adv"), os.path.join(HERE, "results_unans_adv"))
    b2 = RU.collect(os.path.join(HERE, "tasks_unans.jsonl"), os.path.join(HERE, "runs_unans"), os.path.join(HERE, "results_unans"))
    text = tables(adv, b2, load_bank4())
    print(text)
    if a.write:
        with open(os.path.join(HERE, "results_unans_adv", "REPORT_ADV_TABLES.txt"), "x", encoding="utf-8") as f:
            f.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
