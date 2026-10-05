#!/usr/bin/env python3
"""W3-c7: row counts per file/rule, and every row's `expect` through tools.bank_score.v2.b1.validate_item (errors must be 0)."""
import collections, glob, json, sys
from pathlib import Path
TREE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(TREE))
from tools.bank_score.v2 import b1
KEYS = ('id', 'lang', 'behavior', 'input', 'text', 'expect', 'cut', 'construction', 'entry_expect', 'w3c7_expect', 'structure_expect', 'abstain_why', 'rule', 'source', 'note')
tot = errs = 0
ids, inputs = set(), set()
for f in sorted(glob.glob(str(TREE / 'tests/reading_soundness/w3c7_*.jsonl'))):
    name = Path(f).name
    if 'placement' in name: continue
    rows = [json.loads(l) for l in open(f, encoding='utf-8') if l.strip()]
    read = sum(1 for r in rows if r['entry_expect'] == 'read')
    e = []
    for r in rows:
        b1.validate_item(r, e)
        if tuple(r) != KEYS: e.append('KEYS:%s' % r['id'])
        if r['id'] in ids: e.append('DUP_ID:' + r['id'])
        if r['input'] in inputs: e.append('DUP_INPUT:' + r['input'])
        ids.add(r['id']); inputs.add(r['input'])
        if r['behavior'] == 'read' and r['entry_expect'] != 'read': e.append('BEHAVIOR_ENTRY:' + r['id'])
    print('%s rows=%d read=%d abstain=%d errors=%d' % (name, len(rows), read, len(rows) - read, len(e)))
    for x in e: print('  ', x)
    print('  by_w3c7_expect=%s' % json.dumps(dict(sorted(collections.Counter(r['w3c7_expect'] for r in rows).items())), ensure_ascii=False))
    tot += len(rows); errs += len(e)
print('total rows=%d errors=%d' % (tot, errs))
