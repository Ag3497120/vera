"""W3-e2 S1-4 (not a product file): UNPLACED common nouns of r9 in a few frames, read_with_holes (r9)."""
import sys
from pathlib import Path
TREE = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(TREE))
from verantyx import semantic_read as SR, semantic_reader as R, constructions
constructions.discover()
R9='/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2'
q = R.CoarseQuery(R9)
words = [l.split('\t')[0] for l in open(TREE/'artifacts/w10-f05/candidates_r9.txt', encoding='utf-8') if '\tnoun\tUNPLACED' in l or '\tnoun\tUNKNOWN' in l]
frames = ['兄が{w}で歩いた。', '母が荷物を{w}へ押した。', '母が{w}を押した。', '{w}が倒れた。', '母が{w}に手紙を送った。', '兄が{w}から来た。', '妹が{w}で本を読んだ。']
n = 0
for w in words:
    st = q.query(w)['state']
    for f in frames:
        t = f.format(w=w)
        try: o = SR.read_with_holes(t, placement=q)
        except Exception as e: print(w, st, t, 'ERR', type(e).__name__); continue
        print('%s\t%s\t%s\t%s\t%s\t%s' % (w, st, t, o['readable'], o['holes_status'], [(h['head'], h['particle'], h['expected_types'], h['role_candidates'], h['placement_state']) for h in o['holes']]))
