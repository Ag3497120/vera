import sys
from verantyx import semantic_reader as R
for t in sys.argv[1:]:
    v = R.document_view({'d': t})
    print('==', t)
    for c in v.clauses:
        print('  ', c.rule, c.predicate, repr(c.predicate_span.text), [(r.name, r.span.text) for r in c.roles], c.polarity, c.time, 'UNSUP' if c.unsupported else 'OK', list(c.unsupported))
    for u in v.unread: print('   unread', u.reason)
