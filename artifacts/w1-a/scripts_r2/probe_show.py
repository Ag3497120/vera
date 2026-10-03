import sys
from verantyx import semantic_reader as R
for t in open(sys.argv[1],encoding='utf-8').read().split('\n'):
    t=t.strip()
    if not t: continue
    v = R.document_view({'d': t})
    sup=[c for c in v.clauses if not c.unsupported]
    print(('S ' if sup else 'U ') + t, ' | '.join(c.rule+':'+c.predicate+str([(r.name, r.span.text) for r in c.roles]) for c in sup))
