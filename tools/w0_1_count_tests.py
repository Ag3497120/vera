#!/usr/bin/env python3
"""Count test functions by AST and compare two trees (G4 of W0-1).

Usage: w0_1_count_tests.py --before-ref <git-ref> --after <tree-dir>
   or: w0_1_count_tests.py --before-dir <dir> --after <tree-dir>

A test is a module-level `test_*` function, or a `test_*` method of a class named `Test*` or one
whose base is named `TestCase` / `*.TestCase`, in `tests/**/test_*.py`. Parametrised cases are NOT
expanded (this counts definitions, not collected items). IDs are `file::[Class::]name`; a name
defined twice in one scope is counted twice (the first is shadowed at runtime; that is reported).

Output: totals, names only in before, names only in after, and the rename table below applied to them.
Exit 1 if a before-name is missing from after without a documented rename, or after < before.
"""
from __future__ import annotations

import ast
import subprocess
import sys
from collections import Counter
from pathlib import Path

# Documented renames (wave5 units r_memory 6febe16 / r_verifier d25a73a rename these two tests).
DOCUMENTED_RENAMES = {
    "tests/test_verifier_agents.py::test_parse_accepts_recheckable_evidence_reference":
        "tests/test_verifier_agents.py::test_parse_accepts_legacy_evidence_reference_as_testimony",
    "tests/test_memory_revalidate.py::test_missing_or_unknown_witness_is_unverifiable_and_answerable":
        "tests/test_memory_revalidate.py::test_missing_or_unknown_witness_is_unverifiable_with_safe_answerability",
}


def _is_test_class(node: ast.ClassDef) -> bool:
    if node.name.startswith("Test"):
        return True
    for base in node.bases:
        name = base.attr if isinstance(base, ast.Attribute) else getattr(base, "id", "")
        if name == "TestCase":
            return True
    return False


def ids_in(source: str, relpath: str) -> list[str]:
    tree = ast.parse(source)
    found: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            found.append(f"{relpath}::{node.name}")
        elif isinstance(node, ast.ClassDef) and _is_test_class(node):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name.startswith("test_"):
                    found.append(f"{relpath}::{node.name}::{item.name}")
    return found


def from_ref(ref: str) -> Counter:
    listing = subprocess.run(["git", "ls-tree", "-r", "--name-only", ref, "tests"], capture_output=True, text=True, check=True).stdout.split()
    counts: Counter = Counter()
    for name in listing:
        if Path(name).name.startswith("test_") and name.endswith(".py"):
            source = subprocess.run(["git", "show", f"{ref}:{name}"], capture_output=True, text=True, check=True).stdout
            counts.update(ids_in(source, name))
    return counts


def from_dir(directory: Path) -> Counter:
    counts: Counter = Counter()
    for path in sorted((directory / "tests").rglob("test_*.py")):
        relpath = path.relative_to(directory).as_posix()
        counts.update(ids_in(path.read_text(encoding="utf-8"), relpath))
    return counts


def main(argv: list[str]) -> int:
    args = argv[1:]
    try:
        after = Path(args[args.index("--after") + 1]).resolve()
        if "--before-ref" in args:
            before_label = "ref " + args[args.index("--before-ref") + 1]
            before = from_ref(args[args.index("--before-ref") + 1])
        else:
            before_dir = Path(args[args.index("--before-dir") + 1]).resolve()
            before_label = f"dir {before_dir}"
            before = from_dir(before_dir)
    except (ValueError, IndexError):
        print(__doc__, file=sys.stderr)
        return 2
    now = from_dir(after)
    print(f"before ({before_label}): files-with-tests={len({i.split('::')[0] for i in before})} test definitions={sum(before.values())} unique ids={len(before)}")
    print(f"after  ({after}): files-with-tests={len({i.split('::')[0] for i in now})} test definitions={sum(now.values())} unique ids={len(now)}")
    for label, counter in (("before", before), ("after", now)):
        dups = sorted(i for i, n in counter.items() if n > 1)
        print(f"{label} ids defined more than once (shadowed at runtime): {len(dups)}")
        for item in dups:
            print(f"  DUP {label} {item} x{counter[item]}")
    only_before = sorted(set(before) - set(now))
    only_after = sorted(set(now) - set(before))
    reduced = sorted(i for i in before if i in now and now[i] < before[i])
    print(f"\nonly in before ({len(only_before)}):")
    for item in only_before:
        print(f"  - {item}" + (f"  => RENAMED to {DOCUMENTED_RENAMES[item]}" if item in DOCUMENTED_RENAMES else "  => UNEXPLAINED"))
    print(f"\nonly in after ({len(only_after)}):")
    renamed_targets = set(DOCUMENTED_RENAMES.values())
    for item in only_after:
        print(f"  + {item}" + ("  (rename target)" if item in renamed_targets else "  (new)"))
    print(f"\nids defined fewer times in after than before ({len(reduced)}):")
    for item in reduced:
        print(f"  ! {item} {before[item]} -> {now[item]}")
    unexplained = [i for i in only_before if i not in DOCUMENTED_RENAMES or DOCUMENTED_RENAMES[i] not in now]
    total_before, total_after = sum(before.values()), sum(now.values())
    print(f"\nG4 before={total_before} after={total_after} delta={total_after - total_before} unexplained_missing={len(unexplained)} reduced={len(reduced)}")
    return 1 if (unexplained or reduced or total_after < total_before) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
