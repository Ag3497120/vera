import sys
from verantyx import semantic_read as SR
for t in open(sys.argv[1],encoding='utf-8').read().split('\n'):
    t=t.strip()
    if not t: continue
    o=SR.read(t)
    if o['readable']:
        print('READ ', t, '|', ' ; '.join(f"{c['predicate']} {c['roles']} {c['polarity']} {c['tense']} {c['voice']}" for c in o['clauses']))
    else:
        print('ABST ', t, '|', o['abstain']['kind'], o['abstain']['reasons'][:1])
