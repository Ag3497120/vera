#!/usr/bin/env python3
"""W3-b4 step 11: compare two dumps of frozen_fixture_dump.py (base tree, this tree). The OUTPUT difference must be `newly_read` only (the base abstains, now it reads); the diagnosis-only
difference (the output is the same, `typed_explain_ja` says something else: W3-b4 gives the reason of the second table where the base said FRAME_NOT_READ) is counted apart.
Usage: python frozen_fixture_compare.py --base A --after B --out TXT"""
import argparse
import collections
import json
from pathlib import Path

ap = argparse.ArgumentParser(); ap.add_argument('--base', required=True); ap.add_argument('--after', required=True); ap.add_argument('--out', required=True)
a = ap.parse_args()
base = [json.loads(l) for l in Path(a.base).read_text(encoding='utf-8').splitlines() if l.strip()]
after = [json.loads(l) for l in Path(a.after).read_text(encoding='utf-8').splitlines() if l.strip()]
assert [(x['file'], x['id'], x['fake'], x['text']) for x in base] == [(x['file'], x['id'], x['fake'], x['text']) for x in after]
kinds = collections.Counter(); lines = []
for b, n in zip(base, after):
    if b['out'] == n['out']:
        if b['explain'] != n['explain']:
            kinds['diagnosis_only'] += 1
            lines.append('diagnosis_only\t%s\t%s\t%s\t%s -> %s' % (n['fake'], n['file'], n['text'], (b['explain'] or {}).get('w3b2'), (n['explain'] or {}).get('w3b2')))
        else: kinds['same'] += 1
        continue
    bo, no = b['out'], n['out']
    if 'error' in bo or 'error' in no: k = 'error_changed'
    elif not bo['readable'] and no['readable']: k = 'newly_read'
    elif bo['readable'] and not no['readable']: k = 'read_to_abstain'
    elif bo['readable'] and no['readable']: k = 'changed'
    else: k = 'refusal_changed'
    kinds[k] += 1
    lines.append('%s\t%s\t%s\t%s\t%s' % (k, n['fake'], n['file'], n['text'], json.dumps(no.get('clauses', [{}])[0].get('roles'), ensure_ascii=False) if no.get('readable') else ''))
head = ['rows=%d (file x row x fake)' % len(base), 'output differences: ' + json.dumps({k: v for k, v in sorted(kinds.items()) if k not in ('same', 'diagnosis_only')}),
        'same output and same diagnosis: %d' % kinds['same'], 'same output, diagnosis differs only: %d' % kinds['diagnosis_only']]
Path(a.out).write_text('\n'.join(head + lines) + '\n', encoding='utf-8')
print('\n'.join(head))
