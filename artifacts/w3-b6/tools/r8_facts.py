#!/usr/bin/env python3
"""W3-b6 step 1: the answers of the placement r8 (read only) for the words of the data: state, origin, top, decided_by, frame_status.
Usage: PYTHONPATH=<tree> python artifacts/w3-b6/tools/r8_facts.py PLACEMENT WORD... > r8_facts.txt"""
import sys
from verantyx import coarse_place as CP

def main():
    path, words = sys.argv[1], sys.argv[2:]
    for w in words:
        a = CP.query(w, placement=path)
        print('%s\tstate=%s\torigin=%s\ttop=%s\tdecided_by=%s\tframe_status=%s\tnamespace=%s' % (
            w, a.get('state'), a.get('origin'), '+'.join(a.get('top') or []), ','.join(a.get('decided_by') or []), a.get('frame_status'), a.get('namespace')))

main()
