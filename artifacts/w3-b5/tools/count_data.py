#!/usr/bin/env python3
"""W3-b5 step 5: the counts of the data against the registered floors (K205). Usage: python artifacts/w3-b5/tools/count_data.py --data FILE --out TXT"""
import argparse
import collections
import json

ap = argparse.ArgumentParser(); ap.add_argument('--data', required=True); ap.add_argument('--out', required=True)
a = ap.parse_args()
rows = [json.loads(l) for l in open(a.data, encoding='utf-8') if l.strip()]
out = ['rows=%d' % len(rows), '', '# role_group x behavior (rows)']
c = collections.Counter((r['role_group'], r['behavior']) for r in rows)
for k in sorted(c): out.append('%s\t%s\t%d' % (k[0], k[1], c[k]))
out += ['', '# role_group x behavior x path x frame_source x pred_type']
c = collections.Counter((r['role_group'], r['behavior'], r['path'], r['frame_source'], r['pred_type']) for r in rows)
for k in sorted(c): out.append('\t'.join(map(str, k)) + '\t%d' % c[k])
out += ['', '# registered floors: read >= 20 for de_place ni_recipient ni_goal ni_time; abstain >= 20 for de_place de_instrument de_cause ni_recipient ni_goal ni_time ni_purpose ni_other; mechanism >= 15']
n = lambda g, b: sum(1 for r in rows if r['role_group'] == g and r['behavior'] == b)
ok = True
for g in ('de_place', 'ni_recipient', 'ni_goal', 'ni_time'):
    v = n(g, 'read'); out.append('floor read %s %d %s' % (g, v, 'OK' if v >= 20 else 'SHORT')); ok &= v >= 20
for g in ('de_place', 'de_instrument', 'de_cause', 'ni_recipient', 'ni_goal', 'ni_time', 'ni_purpose', 'ni_other'):
    v = n(g, 'abstain'); out.append('floor abstain %s %d %s' % (g, v, 'OK' if v >= 20 else 'SHORT')); ok &= v >= 20
v = sum(1 for r in rows if r['role_group'] == 'mechanism'); out.append('floor mechanism %d %s' % (v, 'OK' if v >= 15 else 'SHORT')); ok &= v >= 15
out.append('read rows that reach a typed trigger (U/U3) by group (frozen expectation): ' + json.dumps(collections.Counter(r['role_group'] for r in rows if r['behavior'] == 'read' and r['path'] in ('U', 'U3')), ensure_ascii=False))
out.append('read rows the reader alone reads (path none): %d' % sum(1 for r in rows if r['behavior'] == 'read' and r['path'] == 'none'))
out.append('all floors met: %s' % ok)
open(a.out, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
print('\n'.join(out[-6:]))
