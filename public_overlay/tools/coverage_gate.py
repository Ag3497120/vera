#!/usr/bin/env python3
"""Coverage gate: exit 1 if fewer than --min sentences of the fixed train-lead sample yield a supported clause.
Usage: tools/coverage_gate.py --min 590   (set VERA_LEADS to the leads jsonl). Prints the measured numbers."""
import argparse, sys
sys.path.insert(0, 'tools')
import read_coverage
ap = argparse.ArgumentParser(); ap.add_argument('--min', type=int, required=True); a = ap.parse_args()
r = read_coverage.measure(1500, 200)
print(f"supported_sentences={r['supported_sentences']} ({r['supported_pct']}%) min={a.min}")
sys.exit(0 if r['supported_sentences'] >= a.min else 1)
