import sys, json, importlib.util
from pathlib import Path
T = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location('fk', T/'tests/reading_soundness/w3b1_fakes.py'); fk = importlib.util.module_from_spec(spec); spec.loader.exec_module(fk)
from verantyx import semantic_read as SR, semantic_reader as R
assert R.__file__.startswith(str(T))
restore = len(sys.argv) > 2 and sys.argv[2] == 'rows'
if restore:   # put back the three place/で rows removed in W3-b4 round 3 (in memory)
    for t in ('P_ACT', 'P_CREATE', 'P_EMOTION'):
        R.TYPED_FRAMES_W3B4[t] = tuple(R.TYPED_FRAMES_W3B4[t]) + (('place', ('で',), ('PLACE',), 'adjunct'),)
cases = [
 ('兄が右で打った。', {'兄':'PERSON','右':'PLACE','打つ':'P_ACT'}),
 ('兄が右で皿を洗った。', {'兄':'PERSON','右':'PLACE','皿':'ARTIFACT','洗う':'P_ACT'}),
 ('兄が上で打った。', {'兄':'PERSON','上':'PLACE','打つ':'P_ACT'}),
 ('兄が前で打った。', {'兄':'PERSON','前':'PLACE','打つ':'P_ACT'}),
 ('兄が中で打った。', {'兄':'PERSON','中':'PLACE','打つ':'P_ACT'}),
 ('兄が校庭で打った。', {'兄':'PERSON','校庭':'PLACE','打つ':'P_ACT'}),
 ('弟が右から倉庫へ打った。', {'弟':'PERSON','右':'PLACE','倉庫':'PLACE','打つ':'P_ACT'}),
 ('弟が上から倉庫へ打った。', {'弟':'PERSON','上':'PLACE','倉庫':'PLACE','打つ':'P_ACT'}),
 ('弟が前から倉庫へ打った。', {'弟':'PERSON','前':'PLACE','倉庫':'PLACE','打つ':'P_ACT'}),
 ('弟が畑から倉庫へ打った。', {'弟':'PERSON','畑':'PLACE','倉庫':'PLACE','打つ':'P_ACT'}),
 ('兄が荷車を上へ押した。', {'兄':'PERSON','荷車':'ARTIFACT','上':'PLACE','押す':'P_ACT'}),
 ('兄が荷車を畑へ押した。', {'兄':'PERSON','荷車':'ARTIFACT','畑':'PLACE','押す':'P_ACT'}),
 ('兄が荷車を駅前へ押した。', {'兄':'PERSON','荷車':'ARTIFACT','駅前':'PLACE','押す':'P_ACT'}),
 ('兄が中から走った。', {'兄':'PERSON','中':'PLACE','走る':'P_MOVE'}),
 ('兄が上から走った。', {'兄':'PERSON','上':'PLACE','走る':'P_MOVE'}),
 ('兄が倉庫へ「も」走った。', {'兄':'PERSON','倉庫':'PLACE','走る':'P_MOVE'}),
]
for text, m in cases:
    q = fk.MapQuery({k: fk.answer(v, term=k) for k, v in m.items()})
    out = SR.read(text, 'ja', placement=q)
    ex = SR.typed_explain_ja(text, fk.MapQuery({k: fk.answer(v, term=k) for k, v in m.items()}))
    print(text, out['readable'], (out.get('clauses') or [{}])[0].get('roles'), json.dumps(ex, ensure_ascii=False)[:200] if ex else '')
