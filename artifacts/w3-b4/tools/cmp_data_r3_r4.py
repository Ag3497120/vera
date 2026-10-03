#!/usr/bin/env python3
"""W3-b4 round 4: compare artifacts/w3-b4/r3/data_check.json (333 rows) with r4/data_check.json (339 rows): the first 333 rows must be identical, and the six appended rows must be
refused (entry 'abstain', judged not misread) with the diagnosis of their `w3b4_expect` (the reason of the gate of K186). Usage: python cmp_data_r3_r4.py R3.json R4.json"""
import json
import sys
a = json.load(open(sys.argv[1])); b = json.load(open(sys.argv[2]))
diff = [x['id'] for x, y in zip(a, b) if x != y]
print('rows r3=%d r4=%d' % (len(a), len(b)))
print('first %d rows differing: %d %s' % (len(a), len(diff), diff))
assert [x['id'] for x in a] == [y['id'] for y in b[:len(a)]]
bad = 0
for y in b[len(a):]:
    ok = y['entry'] == 'abstain' and y['verdict'] not in ('misread', 'incomplete', 'UNJUDGED') and (y['w3b2'] or '').startswith(y['w3b4_expect']) and y['w3b4_expect'].startswith('PLACEMENT_FOCUS_PARTICLE_AFTER_CASE:')
    bad += (not ok)
    print(y['id'], y['entry'], y['verdict'], y['w3b2'], 'OK' if ok else 'BAD')
print('appended=%d bad=%d' % (len(b) - len(a), bad))
sys.exit(1 if (diff or bad) else 0)
