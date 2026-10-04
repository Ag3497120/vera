"""Mine the public copies (tests/reading_soundness/*.jsonl) for abstained sentences, classified with the premise-probe logic (one filler swapped for one DECIDED direct type).
Output: JSONL, one row per unique sentence. Used to pick rows of tests/fusion/w10f04/holes.jsonl by eye; the labels written there are the author's."""
import glob, json, re, sys, collections
from verantyx import semantic_read as S, semantic_reader as R
from verantyx.coarse_types import NOUN_TYPES
sys.path.insert(0, 'artifacts/w10-f04/scripts')
from table_types import table_types
P = '/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2'
pat = re.compile(r'^PLACEMENT_(UNPLACED|MULTIPLE|UNKNOWN):([^:]+):(.+)$')
base = R.CoarseQuery(P)
class Probe:
    def __init__(s, term, T): s.term, s.T = term, T
    def query(s, t):
        if t == s.term: return {'state': 'DECIDED', 'top': [s.T], 'origin': 'direct', 'estimate_basis': None, 'constructed': False, 'decided_by': ['hole_probe']}
        return base.query(t)
    @property
    def id(s): return 'probe'
seen = set(); out = open(sys.argv[1], 'w')
for f in sorted(glob.glob('tests/reading_soundness/*.jsonl')):
    if '/en' in f: continue
    for line in open(f):
        try: t = json.loads(line).get('text')
        except Exception: continue
        if not isinstance(t, str) or t in seen: continue
        seen.add(t)
        try: o = S.read(t, placement=P)
        except S.ReadError: continue
        if o['readable']: continue
        tr = S.typed_explain_ja(t, P)
        rs = list(o['abstain']['reasons']) + [v for v in tr.values() if isinstance(v, str) and v != 'READ']
        hit = None
        for r in rs:
            m = pat.match(r)
            if m: hit = m; break
        row = {'text': t, 'reasons': rs}
        if hit:
            part, word = hit.group(2), hit.group(3)
            row.update(particle=part, head=word, why=hit.group(0))
            if part in R._CASE_PARTICLES_9:
                oks = {}
                for T in NOUN_TYPES:
                    q = S.read(t, placement=Probe(word, T))
                    if q['readable'] and len(q['clauses']) == 1 and not q['relations']:
                        oks[T] = q['clauses'][0]
                row['probe_types'] = sorted(oks)
                if oks:
                    c = next(iter(oks.values()))
                    pans = base.query(c['predicate'])
                    pt, tt = table_types(pans, part)
                    row.update(predicate=c['predicate'], ptype=pt, table_types=sorted(tt))
        out.write(json.dumps(row, ensure_ascii=False) + '\n')
print(len(seen))
