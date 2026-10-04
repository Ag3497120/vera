"""Oracle for two holes (K280 step 7), written for the frozen data and independent of the implementation: sentences whose single-filler probe
does not read, but where a second filler reason shows up once the first is typed and a pair of types reads."""
import json, re, sys
from verantyx import semantic_read as S, semantic_reader as R
from verantyx.coarse_types import NOUN_TYPES
sys.path.insert(0, 'artifacts/w10-f04/scripts')
from table_types import table_types
P = '/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2'
pat = re.compile(r'^PLACEMENT_(UNPLACED|MULTIPLE|UNKNOWN):([^:]+):(.+)$')
base = R.CoarseQuery(P)
class Probe:
    def __init__(s, m): s.m = m
    def query(s, t):
        if t in s.m: return {'state': 'DECIDED', 'top': [s.m[t]], 'origin': 'direct', 'estimate_basis': None, 'constructed': False, 'decided_by': ['hole_probe']}
        return base.query(t)
    @property
    def id(s): return 'probe'
def filler(t, pl):
    o = S.read(t, placement=pl); tr = S.typed_explain_ja(t, pl)
    rs = list(o['abstain']['reasons']) + [v for v in tr.values() if isinstance(v, str) and v != 'READ'] if o['abstain'] else []
    for r in rs:
        m = pat.match(r)
        if m and m.group(2) in R._CASE_PARTICLES_9: return m.group(2), m.group(3)
    return None
def ok(q): return q['readable'] and len(q['clauses']) == 1 and not q['relations']
rows = [json.loads(l) for l in open(sys.argv[1])]
out = open(sys.argv[2], 'w')
for r in rows:
    if 'particle' not in r or r['particle'] == 'part' or r.get('probe_types'): continue
    t = r['text']; p1, h1 = r['particle'], r['head']
    seconds = set()
    for T in NOUN_TYPES:
        pl = Probe({h1: T}); q = S.read(t, placement=pl)
        if ok(q): break
        f = filler(t, pl)
        if f and f[1] != h1: seconds.add(f)
    else:
        if len(seconds) != 1: continue
        p2, h2 = next(iter(seconds))
        good = []
        for T1 in NOUN_TYPES:
            for T2 in NOUN_TYPES:
                q = S.read(t, placement=Probe({h1: T1, h2: T2}))
                if ok(q): good.append((T1, T2, q['clauses'][0]['predicate']))
        if good:
            pred = good[0][2]; pans = base.query(pred)
            row = {'text': t, 'holes': [{'particle': p1, 'head': h1, 'types': sorted({g[0] for g in good})}, {'particle': p2, 'head': h2, 'types': sorted({g[1] for g in good})}],
                   'pairs': len(good), 'predicate': pred}
            row['holes'][0]['table_types'] = sorted(table_types(pans, p1)[1]); row['holes'][1]['table_types'] = sorted(table_types(pans, p2)[1])
            out.write(json.dumps(row, ensure_ascii=False) + '\n')
