"""Scratch: dev-data what-if for QUERY-TIME config keys (not an official run).
usage: dev_whatif.py PLACEMENT [--frozen] [k=v ...]   (values parsed as JSON)"""
import os, sys, json
from collections import Counter
sys.path.insert(0, '/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S/artifacts/w3-a')
import measure_w3a as m
from verantyx import coarse_place as cp
# --frozen switches to the frozen test data -- REPORT ONLY: the configuration is never chosen on it
FROZEN = "--frozen" in sys.argv
ARGS = [a for a in sys.argv[1:] if a != "--frozen"]
pl_path = ARGS[0]
pl, why = cp._open(pl_path)
for kv in ARGS[1:]:
    k, v = kv.split('=', 1)
    pl.cfg[k] = json.loads(v)
q = m.query
seeds = {w for v in m.ct.SEEDS_NOUN.values() for w in v}
V = [g for g in m.load(m.D + ('/typed_vocab.jsonl' if FROZEN else '/dev_vocab.jsonl')) if g['term'] not in seeds]
n = len(V); c = w = 0; est = Counter(); tr = tw = 0
for g in V:
    r = q(g['term'], placement=pl_path); k = m.cls(r, g['gold']); d = r['origin'] == 'direct'
    c += (k == 'correct' and d); w += (k == 'wrong_single' and d)
    if not d: est[(r['origin'], k)] += 1
    if g['suffix_trap']: tr += 1; tw += (k == 'wrong_single' and d)
print('L2 n', n, 'correct %.4f wrong %.4f trapwrong %.4f' % (c/n, w/n, tw/max(1,tr)), dict(est))
U = m.load(m.D + ('/unknown_words.jsonl' if FROZEN else '/dev_unknown.jsonl'))
tc = tw2 = tn = ret = un = 0
for u in U:
    r = q(u['term'], context_role=u['context_role'], context_predicate=u['context_predicate'], placement=pl_path)
    top = r['top']; gs = set(u['gold'])
    if u['gold_unknown']:
        un += 1; ret += bool(top)
    else:
        tn += 1
        if top and set(top) & gs and len(top) <= max(1, len(gs)): tc += 1
        elif top: tw2 += 1
print('L3 typed', tn, 'correct %.3f wrong %.3f | unk %d returned %.3f' % (tc/tn, tw2/tn, un, ret/max(1,un)))
import fugashi
tg = fugashi.Tagger()
H = m.load(m.A + ('/holdout_2000.jsonl' if FROZEN else '/dev_l1_1000.jsonl'))
tot = hit = 0; memo = {}
for h in H:
    for term, role, pred, p1 in m.content_tokens(tg, h['sentence']):
        key = (term, role, pred)
        if key not in memo:
            memo[key] = bool(q(term, context_role=role, context_predicate=pred, placement=pl_path)['top'])
        tot += 1; hit += memo[key]
print('L1 tokens', tot, 'cover %.4f' % (hit/tot))
