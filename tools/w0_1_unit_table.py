#!/usr/bin/env python3
"""Per-unit import table for W0-1 (G5): ledger record vs. branch vs. this tree.

Usage: w0_1_unit_table.py <ledger.jsonl> <branch> [<ledger.jsonl> <branch> ...]

Read-only: reads the ledgers, runs read-only git commands (rev-list / diff-tree / show) against the
tree it lives in, and compares the files each merged commit touched with the working tree.

Rules, applied in this order (the rule name is printed with every unit):
  R1  no `merged` event in the ledger            -> not imported (hold / unfinished)
  R2  `merged` event without a commit            -> not imported (no change exists to import)
  R4  `merged` with a commit, but measured to make previously-passing tests fail
      (EXCLUDED_BY_MEASUREMENT below, with the measurement file) -> not imported
  R3  `merged` with a commit that is on the branch -> imported
  R5  `merged` with a commit that is NOT on the branch -> UNKNOWN (not imported, needs a human)

Whether a unit's files are really in the tree is checked, not assumed: IN_TREE counts the touched
files whose working-tree bytes equal the branch-tip version.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# unit -> measurement file (relative to the tree) showing new failures when it is added on top of the rest.
EXCLUDED_BY_MEASUREMENT = {
    "w_question_forms2": "artifacts/w0-1/qf2_trial_compare.txt",
}
BASE_REF = "dev"


def git(*args: str) -> str:
    done = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=False)
    return done.stdout if done.returncode == 0 else ""


def read_ledger(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def files_in_tree(commit: str, branch: str) -> tuple[int, int, list[str]]:
    touched = [f for f in git("diff-tree", "--no-commit-id", "--name-only", "-r", commit).split("\n") if f]
    same = 0
    differ: list[str] = []
    for name in touched:
        tip = subprocess.run(["git", "-C", str(ROOT), "show", f"{branch}:{name}"], capture_output=True, check=False)
        path = ROOT / name
        if tip.returncode == 0 and path.is_file() and path.read_bytes() == tip.stdout:
            same += 1
        else:
            differ.append(name)
    return same, len(touched), differ


def table(ledger_path: str, branch: str) -> list[str]:
    rows = read_ledger(ledger_path)
    on_branch = set(git("rev-list", f"{BASE_REF}..{branch}").split())
    units: list[str] = []
    for row in rows:
        unit = row.get("unit")
        if unit and unit not in units:
            units.append(unit)
    out = [f"## {Path(ledger_path).parent.name}  ledger={ledger_path}  branch={branch}  units={len(units)}"]
    for unit in units:
        events = [r for r in rows if r.get("unit") == unit]
        names = [r["event"] for r in events]
        merged = [r for r in events if r["event"] == "merged"]
        last_state = names[-1]
        commit = next((r["commit"] for r in reversed(merged) if r.get("commit")), None)
        reason_merged = next((r.get("reason", "") for r in reversed(merged) if not r.get("commit")), "")
        if not merged:
            rule, verdict = "R1", "NOT_IMPORTED"
            why = "no merged event in the ledger (" + ("hold" if "hold" in names else "no terminal event") + ")"
        elif commit is None:
            rule, verdict = "R2", "NOT_IMPORTED"
            why = "merged without a commit; no change exists to import: " + reason_merged
        elif commit not in on_branch:
            rule, verdict = "R5", "UNKNOWN"
            why = "merged commit is not on " + branch + " beyond " + BASE_REF
        elif unit in EXCLUDED_BY_MEASUREMENT:
            rule, verdict = "R4", "NOT_IMPORTED"
            why = "merged with a commit, but adding it makes previously-passing tests fail; see " + EXCLUDED_BY_MEASUREMENT[unit]
        else:
            rule, verdict = "R3", "IMPORTED"
            why = "merged with a commit that is on the branch"
        out.append(f"unit={unit}")
        out.append(f"  events={'>'.join(names)}")
        out.append(f"  last_event={last_state}")
        out.append(f"  merged_commit={commit[:7] if commit else '-'}  on_branch={'yes' if commit in on_branch else ('no' if commit else '-')}")
        if commit:
            same, total, differ = files_in_tree(commit, branch)
            out.append(f"  tree_files_equal_to_branch_tip={same}/{total}" + (f"  differing={','.join(differ)}" if differ else ""))
        out.append(f"  rule={rule}  verdict={verdict}  why={why}")
    return out


def main(argv: list[str]) -> int:
    args = argv[1:]
    if not args or len(args) % 2:
        print(__doc__, file=sys.stderr)
        return 2
    for index in range(0, len(args), 2):
        for line in table(args[index], args[index + 1]):
            print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
