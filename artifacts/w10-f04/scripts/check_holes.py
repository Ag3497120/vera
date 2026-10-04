"""P2: read_with_holes on the frozen rows of tests/fusion/w10f04/holes.jsonl. First line: rows=… hole_expected=… hole_got=… wrong_hole=0 missed=… types_outside_table=0 empty_types=0 …"""
import argparse, json, os, sys, collections
from verantyx import semantic_read as S
ap = argparse.ArgumentParser(); ap.add_argument('--data', required=True); ap.add_argument('--out', required=True); a = ap.parse_args()
R8 = os.environ['VERA_PLACEMENT']
rows = [json.loads(l) for l in open(a.data)]
res, wrong, missed, outside, empty, status_bad, differ, details = [], [], [], [], [], [], [], []
n_exp = n_got = 0
for r in rows:
    pl = R8 if r['placement'] == 'r8' else None
    o = S.read_with_holes(r['text'], r.get('lang'), placement=pl)
    got = bool(o['holes'])
    n_exp += r['is_hole']; n_got += got
    if got and not r['is_hole']: wrong.append(r['id'])
    if r['is_hole'] and not got: missed.append((r['id'], o['holes_status']))
    st = o['holes_status']
    if not st.startswith(r['expect_status']): status_bad.append((r['id'], r['expect_status'], st))
    if got and r['is_hole']:
        exp = r['holes'] if r['n_holes'] > 1 else [{'particle': r['particle'], 'head': r['head'], 'table_types': r['table_types'], 'oracle_probe_types': r['oracle_probe_types']}]
        if len(o['holes']) != len(exp): status_bad.append((r['id'], 'n_holes %d' % len(exp), 'got %d' % len(o['holes'])))
        for h, e in zip(o['holes'], exp):
            if not h['expected_types']: empty.append(r['id'])
            if not set(h['expected_types']) <= set(e['table_types']): outside.append(r['id'])
            if (h['particle'], h['head']) != (e['particle'], e['head']): status_bad.append((r['id'], (e['particle'], e['head']), (h['particle'], h['head'])))
            if set(h['expected_types']) != set(e['oracle_probe_types']) & set(e['table_types']): differ.append((r['id'], h['expected_types'], e['oracle_probe_types'], e['table_types']))
    res.append({'id': r['id'], 'status': st, 'holes': o['holes']})
json.dump(res, open(a.out, 'w'), ensure_ascii=False, indent=1)
print('rows=%d hole_expected=%d hole_got=%d wrong_hole=%d missed=%d types_outside_table=%d empty_types=%d status_mismatch=%d expected_types_differ_from_oracle=%d'
      % (len(rows), n_exp, n_got, len(wrong), len(missed), len(outside), len(empty), len(status_bad), len(differ)))
for k, v in (('wrong_hole', wrong), ('missed', missed), ('status_mismatch', status_bad), ('differ', differ)):
    for x in v: print(' ', k, x)
print('status_counts', dict(collections.Counter(r['status'].split(':')[0] for r in res)))
