#!/usr/bin/env python3
"""W5-f r3 S2: write tests/reading_soundness/w5f_gates_r3.jsonl (F1 additions). Expectations are designed from the sentence, before any output is seen."""
import json, sys
from pathlib import Path
# (suffix_text_with_gap, control_text, fake placement or None, roles for the control)
P = lambda a, b, c, d, v: {a: 'PERSON', b: 'ARTIFACT', c: 'PLACE', d: 'PLACE', v: 'P_ACT'} if d else {a: 'PERSON', b: 'ARTIFACT', c: 'PLACE', v: 'P_ACT'}
rows = []
def pair(abst, ctrl, placement, roles):
    rows.append((abst, ctrl, placement, roles))
# (abstain text, control text, placement, roles) -- null placement: the direct reading path
pair('兄が荷車を倉庫から も押した。', '兄が荷車を倉庫から押した。', None, {'agent': '兄', 'patient': '荷車', 'source': '倉庫'})
pair('姉が箱を港から  は蹴った。', '姉が箱を港から蹴った。', None, {'agent': '姉', 'patient': '箱', 'source': '港'})
pair('弟が荷物を駅から　だけ引いた。', '弟が荷物を駅から引いた。', None, {'agent': '弟', 'patient': '荷物', 'source': '駅'})
pair('母が机を広場から、こそ押した。', '母が机を広場から押した。', None, {'agent': '母', 'patient': '机', 'source': '広場'})
pair('父が箱を畑から・すら叩いた。', '父が箱を畑から叩いた。', None, {'agent': '父', 'patient': '箱', 'source': '畑'})
pair('叔母が荷車を店から…しか戻した。', '叔母が荷車を店から戻した。', None, {'agent': '叔母', 'patient': '荷車', 'source': '店'})
pair('祖母が台車を市場から〜まで押した。', '祖母が台車を市場から押した。', None, {'agent': '祖母', 'patient': '台車', 'source': '市場'})
pair('妹が箱を港へ"も"蹴った。', '妹が箱を港へ蹴った。', {'妹': 'PERSON', '箱': 'ARTIFACT', '港': 'PLACE', '蹴る': 'P_ACT'}, {'agent': '妹', 'patient': '箱', 'goal': '港'})
pair("兄が荷物を工場へ'は'引っ張った。", '兄が荷物を工場へ引っ張った。', {'兄': 'PERSON', '荷物': 'ARTIFACT', '工場': 'PLACE', '引っ張る': 'P_ACT'}, {'agent': '兄', 'patient': '荷物', 'goal': '工場'})
pair('姉が台車を駅から[も]押した。', '姉が台車を駅から押した。', {'姉': 'PERSON', '台車': 'ARTIFACT', '駅': 'PLACE', '押す': 'P_ACT'}, {'agent': '姉', 'patient': '台車', 'source': '駅'})
pair('弟が机を公園へ★は★戻した。', '弟が机を公園へ戻した。', {'弟': 'PERSON', '机': 'ARTIFACT', '公園': 'PLACE', '戻す': 'P_ACT'}, {'agent': '弟', 'patient': '机', 'goal': '公園'})
pair('父が箱を畑へ 「も」 叩いた。', '父が箱を畑へ叩いた。', {'父': 'PERSON', '箱': 'ARTIFACT', '畑': 'PLACE', '叩く': 'P_ACT'}, {'agent': '父', 'patient': '箱', 'goal': '畑'})
pair('叔父が荷車を店から「ゆく」押した。', '叔父が荷車を店から押した。', {'叔父': 'PERSON', '荷車': 'ARTIFACT', '店': 'PLACE', '押す': 'P_ACT'}, {'agent': '叔父', 'patient': '荷車', 'source': '店'})
pair('兄が広場で、さえ箱を押した。', '兄が広場で箱を押した。', {'兄': 'PERSON', '広場': 'PLACE', '箱': 'ARTIFACT', '押す': 'P_ACT'}, {'agent': '兄', 'patient': '箱', 'place': '広場'})
out = []
n = 101
for a, c, pl, roles in rows:
    out.append({'id': 'W5F-F1-%03d' % n, 'group': 'F1', 'text': a, 'expect': 'abstain', 'placement': pl}); n += 1
for a, c, pl, roles in rows:
    out.append({'id': 'W5F-F1-%03d' % n, 'group': 'F1', 'text': c, 'expect': 'read_or_abstain', 'placement': pl, 'roles': roles}); n += 1
# not-over-blocking controls: a space then a verb; a comma right after を
out.append({'id': 'W5F-F1-%03d' % n, 'group': 'F1', 'text': '兄が荷物を駅から 引いた。', 'expect': 'read_or_abstain', 'placement': None, 'roles': {'agent': '兄', 'patient': '荷物', 'source': '駅'}}); n += 1
out.append({'id': 'W5F-F1-%03d' % n, 'group': 'F1', 'text': '姉が箱を、駅から蹴った。', 'expect': 'read_or_abstain', 'placement': None, 'roles': {'agent': '姉', 'patient': '箱', 'source': '駅'}}); n += 1
# appended after the first freeze (balance rule |abstain - read| <= 2 for F1 over both files): two more abstain rows, nothing above changed
out.append({'id': 'W5F-F1-%03d' % n, 'group': 'F1', 'text': '姉が机を店から 、は戻した。', 'expect': 'abstain', 'placement': None}); n += 1
out.append({'id': 'W5F-F1-%03d' % n, 'group': 'F1', 'text': '妹が荷車を広場から「も」叩いた。', 'expect': 'abstain', 'placement': {'妹': 'PERSON', '荷車': 'ARTIFACT', '広場': 'PLACE', '叩く': 'P_ACT'}}); n += 1
Path(sys.argv[1]).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in out), encoding='utf-8')
print(len(out))
