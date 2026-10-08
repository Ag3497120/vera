#!/usr/bin/env python
"""Verify the measured generator target lists against the frozen ticket expectations."""
import json
from pathlib import Path


root = Path(__file__).resolve().parents[1]
tree = root.parents[1]
expect = json.loads((tree / "tests/coarse_place/data/w3a6_expect.json").read_text(encoding="utf-8"))


def words(path):
    return {json.loads(line)["word"] for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


ntype_words = words(root / "needs_ntype.jsonl")
role_words = words(root / "needs_role.jsonl")
missing_ntype = sorted(set(expect["relative_position"]) - ntype_words)
expected_predicates = {row["pred"] for row in expect["roles"]}
missing_roles = sorted(expected_predicates - role_words)
ntype_meta = json.loads((root / "needs_ntype.meta.json").read_text(encoding="utf-8"))
role_meta = json.loads((root / "needs_role.meta.json").read_text(encoding="utf-8"))
print("ntype_total", ntype_meta["total"], "missing_expected", missing_ntype)
print("role_total", role_meta["total"], "missing_expected", missing_roles)
print("role_rows", len(expect["roles"]), "distinct_predicates", len(expected_predicates))
assert not missing_ntype and not missing_roles
