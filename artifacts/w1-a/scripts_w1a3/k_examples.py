# usage: PYTHONPATH=<tree> k_examples.py <sentences.txt> : prints the reader's (document_view) supported clauses and, when the tree has it, the entry's output
import sys, json
from verantyx.semantic_reader import document_view
try:
    from verantyx import semantic_read as SR
except ImportError:
    SR = None
for t in [l.strip() for l in open(sys.argv[1], encoding='utf-8') if l.strip() and not l.startswith('#')]:
    cl = [c for c in document_view({'d': t}).clauses if not c.unsupported]
    print(t)
    print('  reader:', [(c.predicate, [(r.name, r.span.text) for r in c.roles]) for c in cl] or 'unsupported')
    if SR:
        o = SR.read(t)
        print('  entry :', json.dumps(o['clauses'], ensure_ascii=False) if o['readable'] else 'readable=false ' + '; '.join(o['abstain']['reasons']))
