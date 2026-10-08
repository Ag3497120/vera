# usage: probe_cmp.py <probe_outputs.jsonl>   (code from PYTHONPATH)
import json, sys, collections
from verantyx import semantic_read as SR
cnt = collections.Counter()
for line in open(sys.argv[1], encoding='utf-8'):
    r = json.loads(line); a = r['actual']; b = SR.read(r['text'])
    if a == b: cnt['same'] += 1; continue
    if a['readable'] and not b['readable']: k = 'readable→false'
    elif a['readable'] and b['readable']: k = 'changed'
    elif not a['readable'] and b['readable']: k = 'false→readable'
    else: k = 'reason_changed'
    cnt[k] += 1
    print(k, r['id'], r['text'], (b.get('abstain') or {}).get('reasons'), json.dumps(b['clauses'], ensure_ascii=False)[:150])
print(dict(cnt))
