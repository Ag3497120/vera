import json, sys, collections
from verantyx import event_cross as EC
import verantyx.event_cross
assert verantyx.event_cross.__file__.startswith(sys.argv[1] + '/')
rows = [json.loads(l) for l in open(sys.argv[2], encoding='utf-8')]
new = [r for r in rows if r['kind'] == 'newly_read']
status = collections.Counter(); rej = collections.Counter(); keyst = collections.Counter(); flags = 0; lines = []
for r in new:
    out = r['after']
    cr = EC.build_crosses(out)
    status[cr.status] += 1
    if cr.status == 'INPUT_REJECTED':
        for x in cr.abstain['reasons']: rej[x] += 1
    for c in out['clauses']:
        if 'flags' in c: flags += 1
        keyst['%s/%s' % (cr.status, ','.join(sorted(k for k in ('quantifiers',) if k in c)))] += 1
        lines.append('%s\t%s\t%s' % (cr.status, r['text'], json.dumps({k: c[k] for k in ('quantifiers',) if k in c}, ensure_ascii=False)))
print('newly_read sentences (no placement): %d' % len(new))
print('build_crosses status: %s' % dict(status))
print('INPUT_REJECTED reasons: %s (UNKNOWN_CLAUSE_KEY:flags absent: %s)' % (dict(rej), not any('UNKNOWN_CLAUSE_KEY:flags' in k for k in rej)))
print('status by the key the clause carries: %s' % dict(keyst))
print('clauses that carry flags: %d' % flags)
print('\n'.join(lines))
