import sys
from verantyx.semantic_reader import document_view
from verantyx import semantic_read as SR
for t in [l.strip() for l in open(sys.argv[1], encoding='utf-8') if l.strip()]:
    v = document_view({'d': t})
    sup = [(c.predicate, [(r.name, r.span.text) for r in c.roles]) for c in v.clauses if not c.unsupported]
    out = SR.read(t)
    ent = [(c['predicate'], c['voice'], c['roles']) for c in out['clauses']] if out['readable'] else ('ABSTAIN', out['abstain']['reasons'][:2])
    print(t, '\n   R:', sup or '-', '\n   E:', ent)
