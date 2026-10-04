"""Run a bank of (explanation, task) questions through the ENTRY (a subprocess of ``python -m verantyx.cli route``), never through a
function, and score it.

    python tests/routing_from_text/run_bank.py --bank <dir> --items <items.jsonl> --out <dir> [--explanations-dir explanations]

``<bank>/<explanations-dir>/<explanation_id>.md`` is the explanation of an item.  An item is one JSON line:
``{"id", "lang", "explanation_id", "task": {...}, "expect": {"decision": "route"|"undecided", "agent", "basis_kind",
"wrong_agents", "evidence"}, ...}``.

Counted (docs/ROUTING_FROM_TEXT.md): for the questions whose answer is a route: how many were routed to the right agent, abstained,
routed to a different one; for the questions whose answer is undecided: how many were answered undecided and how many got an agent;
**misroutes = (undecided is right and an agent was returned) + (a route is right and a different agent was returned)**.
The scoring reads only ``decision`` and ``agent`` (the agent is compared after NFKC and case folding).  ``--out`` may not be inside
``--bank`` (the bank is read-only; exit code 2).  Only the standard library is used.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def norm(text):
    return unicodedata.normalize("NFKC", text).strip().casefold() if isinstance(text, str) else text


def run_entry(explanation_path, task):
    env = dict(os.environ)
    env["PYTHONPATH"] = ROOT
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run([sys.executable, "-m", "verantyx.cli", "route", "--explanation", explanation_path,
                           "--task", json.dumps(task, ensure_ascii=False)],
                          capture_output=True, text=True, env=env, cwd=ROOT)
    try:
        out = json.loads(proc.stdout.strip().splitlines()[-1]) if proc.stdout.strip() else None
    except ValueError:
        out = None
    return proc.returncode, out, proc.stderr[-400:]


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--bank", required=True)
    parser.add_argument("--items", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--explanations-dir", default="explanations")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args(argv)
    bank, out_dir = os.path.realpath(args.bank), os.path.realpath(args.out)
    if out_dir == bank or out_dir.startswith(bank + os.sep):
        sys.stderr.write("--out must not be inside --bank (the bank is read-only)\n")
        return 2
    items = [json.loads(line) for line in open(args.items, encoding="utf-8") if line.strip()]
    os.makedirs(out_dir, exist_ok=True)

    def one(item):
        path = os.path.join(bank, args.explanations_dir, item["explanation_id"] + ".md")
        return run_entry(path, item["task"])

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        results = list(pool.map(one, items))      # map keeps the order of the items

    rows, errors = [], 0
    stats = Counter()
    reasons, abstentions, bases = Counter(), Counter(), Counter()
    per_expl = {}
    for item, (code, out, err) in zip(items, results):
        expect = item["expect"]
        row = {"id": item["id"], "explanation_id": item["explanation_id"], "expect": expect, "exit_code": code, "output": out}
        if code != 0 or not isinstance(out, dict) or out.get("decision") not in ("route", "undecided"):
            errors += 1
            row["scored_as"] = "ERROR"
            row["stderr"] = err
            rows.append(row)
            continue
        got, agent = out["decision"], out.get("agent")
        if expect["decision"] == "route":
            stats["route_expected"] += 1
            if got == "route" and norm(agent) == norm(expect["agent"]):
                stats["route_correct"] += 1
                row["scored_as"] = "ROUTE_CORRECT"
            elif got == "route":
                stats["route_wrong_agent"] += 1
                row["scored_as"] = "MISROUTE_WRONG_AGENT"
            else:
                stats["route_abstained"] += 1
                row["scored_as"] = "ROUTE_ABSTAINED"
        else:
            stats["undecided_expected"] += 1
            if got == "undecided":
                stats["undecided_correct"] += 1
                row["scored_as"] = "UNDECIDED_CORRECT"
            else:
                stats["undecided_got_agent"] += 1
                row["scored_as"] = "MISROUTE_AGENT_FOR_UNDECIDED"
        reasons[str(out.get("undecided_reason"))] += 1
        abstentions[str((out.get("abstention") or {}).get("type"))] += 1
        bases[str(out.get("basis_kind"))] += 1
        rd = out.get("reading") or {}
        entry = per_expl.setdefault(item["explanation_id"], {"questions": 0, "units": rd.get("units"),
                                                              "by_status": rd.get("by_status")})
        entry["questions"] += 1
        rows.append(row)
    stats["misroutes"] = stats["route_wrong_agent"] + stats["undecided_got_agent"]
    total = len(items)
    summary = {
        "items": total, "errors": errors,
        "route_expected": stats["route_expected"], "route_correct": stats["route_correct"],
        "route_abstained": stats["route_abstained"], "route_wrong_agent": stats["route_wrong_agent"],
        "undecided_expected": stats["undecided_expected"], "undecided_correct": stats["undecided_correct"],
        "undecided_got_agent": stats["undecided_got_agent"],
        "misroutes": stats["misroutes"],
        "always_abstain_correct": stats["undecided_expected"],
        "correct_total": stats["route_correct"] + stats["undecided_correct"],
        "undecided_reason": dict(sorted(reasons.items())), "abstention_type": dict(sorted(abstentions.items())),
        "basis_kind": dict(sorted(bases.items())),
        "per_explanation": {key: per_expl[key] for key in sorted(per_expl)},
    }
    with open(os.path.join(out_dir, "runs.jsonl"), "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    lines = [f"items: {total}  errors: {errors}",
             f"route questions (a route is the right answer): {summary['route_expected']}"
             f"  routed correctly: {summary['route_correct']}  abstained: {summary['route_abstained']}"
             f"  routed to a different agent: {summary['route_wrong_agent']}",
             f"undecided questions (undecided is the right answer): {summary['undecided_expected']}"
             f"  answered undecided: {summary['undecided_correct']}  returned an agent: {summary['undecided_got_agent']}",
             f"misroutes: {summary['misroutes']}   (= undecided answered with an agent + a route answered with a different agent)",
             f"correct in total: {summary['correct_total']} of {total}   (always abstain would be correct on {summary['always_abstain_correct']})",
             f"undecided_reason: {json.dumps(summary['undecided_reason'], ensure_ascii=False)}",
             f"abstention.type: {json.dumps(summary['abstention_type'], ensure_ascii=False)}",
             f"basis_kind: {json.dumps(summary['basis_kind'], ensure_ascii=False)}", "units by status, per explanation:"]
    for key, entry in summary["per_explanation"].items():
        by = entry["by_status"] or {}
        read = sum(by.get(name, 0) for name in ("MAPPED", "COMPARISON_ONLY"))
        shown = ", ".join(f"{name} {count}" for name, count in by.items() if count)
        lines.append(f"  {key}: {read} of {entry['units']} units read and mapped ({shown}); {entry['questions']} questions")
    with open(os.path.join(out_dir, "summary.txt"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    sys.stdout.write("\n".join(lines) + "\n")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
