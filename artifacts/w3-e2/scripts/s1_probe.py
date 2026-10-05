"""W3-e2 S1 measurement (not a product file): P2 token shapes, P1 reasons, stand-ins, P3 candidates."""
import sys, json, itertools, collections
from pathlib import Path
TREE = Path(__file__).resolve().parents[3]; sys.path.insert(0, str(TREE))
from verantyx import semantic_read as SR, semantic_reader as R, constructions
constructions.discover()
R8='/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2'
R9='/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2'
which = sys.argv[1]
def rd(t, p):
    o = SR.read(t, placement=p)
    return o['readable'], ((o.get('abstain') or {}).get('reasons') or [None])[0]
if which == 'p2':
    stems = ['ザク','ピロ','モフ','ヨモ','クル','ぷに','ゴロ','ぽよ','炎上','ハバ','フガ','テケ','ニャン','ガチ']
    ends = ['った','る','らない','らなかった','ります','りました','られた','られる']
    for s in stems:
        for e in ends:
            t = 'ハルは本を' + s + e + '。'
            toks = R._tokens(t)
            tail = [(w.surface, w.feature.pos1, w.feature.pos2, w.feature.cType, w.feature.cForm, w.feature.lemma) for w,a,b in toks[4:-1]]
            print(t, rd(t, None), tail)
elif which == 'p1':
    names = ['ミナ','ユウト','サキ','ポルミナ','ナナ','リク','佐々木','国連','京都','ハナコ','アオイ','ルカ','ノア','トリノ']
    preds = {'が':['読んだ','走った','来た'], 'を':['見た','叩いた'], 'に':['本を渡した','会った','手紙を送った'], 'へ':['荷物を運んだ','走った'], 'で':['本を読んだ']}
    cnt = collections.Counter()
    for pl_name, pl in (('none', None), ('r8', R.CoarseQuery(R8)), ('r9', R.CoarseQuery(R9))):
        for n in names:
            for p, ps in preds.items():
                for pr in ps:
                    t = ('ハルは' + n + p + pr + '。') if p in ('に','へ','を','で') else (n + 'が' + pr + '。')
                    if p == 'を' or p == 'で' : t = 'ハルは' + n + p + pr + '。' 
                    ok, why = rd(t, pl)
                    key = (pl_name, ok, (why or '').split(':')[0])
                    cnt[key] += 1
                    print(pl_name, t, ok, why)
    print('---- COUNTS'); [print(k, v) for k, v in sorted(cnt.items(), key=str)]
elif which == 'stand':
    for w in ["犬","田中","国連","京都",'佐藤','山田','鈴木','外務省','大阪','奈良','国会']:
        toks = R._tokens(w)
        print(w, [(t.surface, t.feature.pos1, t.feature.pos2, t.feature.pos3, t.feature.lemma) for t,a,b in toks],
              'person', R._is_person_phrase(w), 'place', R._is_place_phrase(w),
              'r8', R.CoarseQuery(R8).query(w)['state'], R.CoarseQuery(R8).query(w).get('top'), 'r9', R.CoarseQuery(R9).query(w)['state'], R.CoarseQuery(R9).query(w).get('top'))
