"""W3-e2 measurement tool: public B1 samples through read() with r9. Not a product file."""
import json, sys
from pathlib import Path
TREE = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(TREE))
from verantyx import semantic_read as SR, semantic_reader as R, constructions
constructions.discover()
q = R.CoarseQuery('/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2')
n = 0
with open(sys.argv[1], 'w', encoding='utf-8') as fo:
    for d in ('B1_v2', 'B1_v2_r2', 'B1_v2_r3'):
        for l in open(TREE / 'tests/bank_score/fixtures' / d / 'items.jsonl', encoding='utf-8'):
            r = json.loads(l); t = r.get('input')
            if not isinstance(t, str): continue
            try: out = SR.read(t, placement=q)
            except Exception as e: out = {'error': type(e).__name__}
            fo.write(json.dumps({'id': r['id'], 'out': out}, ensure_ascii=False, sort_keys=True, default=str) + '\n'); n += 1
print('rows', n)
