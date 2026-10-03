import json, sys
# usage: bank_cmp.py <before_dir_template> <after_dir_template>   (templates contain {fx}); compares results.jsonl by id for the three fixtures
bt, at = sys.argv[1], sys.argv[2]
print('id\tfixture\tbefore\tafter\tchanged')
tot = {'same': 0, 'changed': 0}
for fx in ('B1_v2', 'B1_v2_r2', 'B1_v2_r3'):
    b = {json.loads(l)['id']: json.loads(l)['class'] for l in open(bt.format(fx=fx) + '/results.jsonl', encoding='utf-8')}
    a = {json.loads(l)['id']: json.loads(l)['class'] for l in open(at.format(fx=fx) + '/results.jsonl', encoding='utf-8')}
    assert b.keys() == a.keys(), fx
    for i in b:
        ch = '' if b[i] == a[i] else 'CHANGED'
        tot['changed' if ch else 'same'] += 1
        print(i, fx, b[i], a[i], ch, sep='\t')
print('# totals', tot)
