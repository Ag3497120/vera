#!/usr/bin/env python3
"""W5-f r3: how many READABLE entry outputs would the gate stop, with separated_only True / False (tree's own function). Usage: cost_unseparated.py DUMP.jsonl..."""
import json, sys
import verantyx.semantic_reader as R
for f in sys.argv[1:]:
    rows = [json.loads(l) for l in open(f, encoding='utf-8') if l.strip()]
    rd = [r for r in rows if r['out'].get('readable')]
    for flag in (True, False):
        hits = [r['text'] for r in rd if R._quoted_focus_after_case_reason(R._tokens(r['text']), 0, len(r['text']), r['text'], separated_only=flag)]
        print(f.split('/')[-1], 'inputs', len(rows), 'readable', len(rd), 'separated_only=%s' % flag, 'would_stop', len(hits), hits)
