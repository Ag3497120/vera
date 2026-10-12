"""LOOM-span: score a measurement again under the EXACT-MATCH headline (score.py, 2026-10-12) without touching its files.

    python experiments/line3/loom/rescore.py --results experiments/line3/loom/results_h55 [--out experiments/line3/loom/results_h55/rescore_h55.md]

For every results file of the folder it takes the ledger the file names (`ledger`, relative to the repository root), runs `score.score_run` on that run
folder (so the ledger is VERIFIED first, chain + replay: a ledger that holds the legacy `weave_sentence` is replayed by its legacy code path) and prints
or writes a Markdown table: the old status / hits_text of the results file next to the new hit_exact / hit_cited / hits_text / excess_chars.  The results JSON
files and the ledgers are only read; the only file written is the `--out` file (never overwritten).

`rescore_dir` is also what compare_span.py uses, so the three measurements are compared under one rule.
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import json
import os
import sys
from typing import Any, Dict, List, Optional, Sequence

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def _load_score():
    name = "loom_score"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, os.path.join(HERE, "score.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


score = _load_score()
BANK = os.path.join(HERE, "tasks_bank2.jsonl")
MODES = ("record_only", "constructed_allowed", "free_text")
SHORT = {"record_only": "ro", "constructed_allowed": "ca", "free_text": "ctl"}


def _abs(p: str) -> str:
    return p if os.path.isabs(p) else os.path.join(ROOT, p)


def rescore_dir(results_dir: str, bank: Optional[Dict[str, dict]] = None, gold: Optional[Dict[str, dict]] = None) -> List[dict]:
    """One dict per results file (sorted by file name): the old fields of the file, the new RunScore fields, and the run folder."""
    bank = bank if bank is not None else score.load_bank(BANK)
    gold = gold if gold is not None else score.load_gold()
    out: List[dict] = []
    for f in sorted(glob.glob(os.path.join(_abs(results_dir), "*.json"))):
        with open(f, encoding="utf-8") as fh:
            o = json.load(fh)
        run_dir = os.path.dirname(_abs(o["ledger"]))
        rs = score.score_run(run_dir, bank, gold)
        old = o.get("score") or {}
        out.append({
            "file": os.path.basename(f), "base": o["base"], "mode": o["mode"], "task_id": o["task_id"], "run_dir": run_dir, "kind": rs.kind,
            "old_status": old.get("status"), "old_hits_text": old.get("hits_text"),
            "status": rs.status, "verify": rs.verify_status, "replay_verified": rs.replay_verified, "text": rs.text, "answer_line": rs.answer_line,
            "abstain_type": rs.abstain_type, "hit_exact": rs.hit_exact, "hit_cited": rs.hit_cited, "hits_text": rs.hits_text, "excess_chars": rs.excess_chars,
            "facts": rs.facts, "result": o,
        })
    return out


def yn(v: Any) -> str:
    return "-" if v is None else ("Y" if v else "N")


def shown(r: dict) -> str:
    t = r["answer_line"] if r["mode"] == "free_text" else r["text"]
    return "(none)" if t is None else "「%s」" % t.replace("|", "/").replace("\n", " ")[:60]


def tables(rows: Sequence[dict]) -> List[str]:
    out: List[str] = []
    p = out.append
    p("| task | mode | old status | old hits_text | new status | hit_exact | hit_cited | hits_text | excess | output (emitted text; a control: its answer line) |")
    p("|---|---|---|---|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda r: (r["base"], MODES.index(r["mode"]))):
        p("| %s | %s | %s | %s | %s | %s | %s | %s | %s | %s |" % (
            r["base"], SHORT[r["mode"]], r["old_status"], yn(r["old_hits_text"]), r["status"], yn(r["hit_exact"]), yn(r["hit_cited"]), yn(r["hits_text"]),
            "-" if r["excess_chars"] is None else r["excess_chars"], shown(r)))
    p("")
    p("| mode | answerable runs | hits_text (old headline) | **hit_exact (new headline)** | hit_cited (extra, longer quoted text) | emitted but not exact | unans abstained correct | unans answered | unans no output |")
    p("|---|---|---|---|---|---|---|---|---|")
    for m in MODES:
        rs = [r for r in rows if r["mode"] == m]
        ans = [r for r in rs if r["kind"] == "answerable"]
        un = [r for r in rs if r["kind"] == "unans"]
        p("| %s | %d | %d | **%d** | %d | %d | %d/%d | %d | %d |" % (
            m, len(ans), sum(1 for r in ans if r["old_hits_text"]), sum(1 for r in ans if r["hit_exact"]), sum(1 for r in ans if r["hit_cited"]),
            sum(1 for r in ans if r["status"] == "miss"),
            sum(1 for r in un if r["status"] == "abstained_correct"), len(un), sum(1 for r in un if r["status"] == "answered_unans"),
            sum(1 for r in un if r["status"] == "no_output")))
    return out


def render(label: str, results_dir: str, rows: Sequence[dict]) -> str:
    n_ok = sum(1 for r in rows if r["verify"] == "OK" and r["replay_verified"])
    lines = ["# rescore_%s: the same runs under the exact-match headline" % label, "",
             "Ticket LOOM-span (owner, 2026-10-12): the headline `hit_exact` = the answer text equals a gold alternative after the T9 normalisation; a longer "
             "text counts as `hit_cited` only if it appears word for word in a sentence the ledger cites (an ok `read_sentence` / `lookup` result); `hits_text` "
             "(substring) and `excess_chars` are secondary columns. Made by `experiments/line3/loom/rescore.py --results %s` from the results files and the "
             "ledgers they name; nothing in `%s` was edited (the JSON files keep the score they were written with: `old status`, `old hits_text`)." % (
                 os.path.relpath(_abs(results_dir), ROOT), os.path.relpath(_abs(results_dir), ROOT)),
             "All %d ledgers were VERIFIED again before scoring (chain + replay): %d of %d are OK and replay IDENTICAL." % (len(rows), n_ok, len(rows)), ""]
    lines += tables(rows)
    lines.append("")
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--label", default=None, help="h55 | h55b | h55c (default: the folder name after `results_`)")
    ap.add_argument("--out", default=None, help="write the Markdown here (never overwritten); default: print")
    a = ap.parse_args(argv)
    label = a.label or os.path.basename(_abs(a.results).rstrip("/")).replace("results_", "")
    rows = rescore_dir(a.results)
    md = render(label, a.results, rows)
    if a.out:
        with open(_abs(a.out), "x", encoding="utf-8") as f:
            f.write(md)
        print("wrote", a.out)
    else:
        print(md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
