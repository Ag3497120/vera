#!/usr/bin/env python3
"""W3-b4: tests/reading_soundness/w3b2_delta.py (not changed) with the rows of ja_r10_w3b4.jsonl added to the sources whose gold gives the verdict of a newly read sentence
(`tools.bank_score.v2.b1.judge` against the row's `expect`). Same arguments, same exit code. A sentence that two sources hold keeps the first (the entry's own input order) as in w3b2_delta.
Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-b4/tools/delta_w3b4.py --before A --after B --out C --manual D [--labels-out E]"""
import importlib.util
import json
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parents[3]
RS = TREE / 'tests' / 'reading_soundness'
sys.path.insert(0, str(RS))
spec = importlib.util.spec_from_file_location('w3b2_delta_of_the_tree', RS / 'w3b2_delta.py')
D = importlib.util.module_from_spec(spec); spec.loader.exec_module(D)
_original = D.gold_sources


def gold_sources():
    src, b1, classify = _original()
    for r in D.rows_of(RS / 'ja_r10_w3b4.jsonl'): src.setdefault(r['input'], ('new_data', r))
    return src, b1, classify


D.gold_sources = gold_sources
D.main()
