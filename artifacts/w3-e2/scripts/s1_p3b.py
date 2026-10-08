"""W3-e2 S1-4 (not a product file): which sentences of the bicycle document give holes / which abstain with r9."""
import sys, collections
from pathlib import Path
TREE = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(TREE))
from verantyx import semantic_read as SR, semantic_reader as R, constructions
constructions.discover()
R9='/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2'
q = R.CoarseQuery(R9)
c = collections.Counter()
for t in [l.strip() for l in open(TREE/'tests/fusion/w10f05/domain_bicycle.txt', encoding='utf-8') if l.strip()]:
    o = SR.read_with_holes(t, placement=q)
    c[o['holes_status'].split(':')[0]] += 1
    if not o['readable']:
        print(t, o['holes_status'], (o['abstain'] or {}).get('reasons'), [(h['head'], h['particle'], h['expected_types'], h['role_candidates'], h['placement_state']) for h in o['holes']])
print(c)
