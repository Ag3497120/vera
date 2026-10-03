"""W5-d2: compare per item the output of the r7 banks run on a round-1-equivalent copy (parts of parallel names not asked) with the output now.
Usage: g3_r7_diff.py <before_dir> <after_dir> [<before_dir> <after_dir> ...]; prints every item whose output differs (decision, agent, by_status, units with status/reasons)."""
import json, sys
args = sys.argv[1:]
total = changed = 0
for b, a in zip(args[0::2], args[1::2]):
    rb = {r['id']: r for r in map(json.loads, open(b + '/runs.jsonl', encoding='utf-8'))}
    ra = {r['id']: r for r in map(json.loads, open(a + '/runs.jsonl', encoding='utf-8'))}
    assert rb.keys() == ra.keys()
    print('==', a.split('/')[-1], 'items', len(ra))
    for k in sorted(ra):
        total += 1
        ob, oa = rb[k]['output'], ra[k]['output']
        if ob != oa:
            changed += 1
            ub = {u['index']: (u['status'], u['reasons'], u['text']) for u in (ob.get('abstention') or {}).get('units', [])}
            ua = {u['index']: (u['status'], u['reasons'], u['text']) for u in (oa.get('abstention') or {}).get('units', [])}
            print(' CHANGED', k, 'decision', ob['decision'], '->', oa['decision'], 'agent', ob['agent'], '->', oa['agent'])
            print('   by_status before', ob['reading']['by_status'], '\n   by_status after ', oa['reading']['by_status'])
            for i in sorted(set(ub) | set(ua)):
                if ub.get(i) != ua.get(i): print('   unit', i, ub.get(i), '->', ua.get(i))
print('items', total, 'changed', changed)
