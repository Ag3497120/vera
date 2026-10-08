import json, collections, sys
c = collections.Counter(); n = 0
for l in open(sys.argv[1], encoding='utf-8'):
    r = json.loads(l)
    if r['readable'] and r['unsupported']:
        n += 1
        c.update([tuple(u['reasons']) for u in r['unsupported']])
        assert any('comparison' in x for x in r['clauses']), r['text']
print(n, dict(c))
