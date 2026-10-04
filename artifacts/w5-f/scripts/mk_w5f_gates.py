#!/usr/bin/env python3
"""W5-f S2: write tests/reading_soundness/w5f_gates.jsonl from the DESIGN below (the expectations are written here, before any product code changes; the output of the
reader is never looked at to decide an expectation). Usage: python3 mk_w5f_gates.py OUT.jsonl [--only ID,ID,...]   (--only keeps the rows of a reach list)

Rows: {"id","group","text","expect","roles"?,"placement"}.  expect: "abstain" (a reading is a MISREAD) | "read_or_abstain" (a reading must be the one in `roles`).
Groups: F1 a quoted 1-2 character piece right after a case particle (abstain) and the same sentence without it (read_or_abstain);
        F2 a place / goal / source / で filler whose head is 名詞/普通名詞/副詞可能 (abstain) and the same sentence with a 名詞/普通名詞/一般 noun (read_or_abstain);
        F3 a coordination or disjunction in the value of a copula and 'NP とも NP とも' (abstain) and a copula / とも with one value (read_or_abstain).
Words: the nouns of the F2 abstain rows are the ones that UniDic tags 副詞可能 (artifacts/w5-f/pos_tags_f2_design.txt); 右・左 and other 一般 words of direction are NOT in an
abstain row (K-F2) and not in a read row either (their reading is not claimed)."""
import json
import sys

P, A_, PL = 'PERSON', 'ARTIFACT', 'PLACE'
rows = []


def add(group, n, text, expect, placement, roles=None):
    r = {'id': 'W5F-%s-%03d' % (group, n), 'group': group, 'text': text, 'expect': expect, 'placement': placement}
    if roles is not None: r['roles'] = roles
    rows.append(r)


def pl(**kw):
    return dict(kw)


# ---------------------------------------------------------------------------------------------- F1
# (design note: the predicates are the P_ACT / P_MOVE verbs for which the typed step is the one that can read a へ phrase; a source phrase (から) is read by the reader alone,
# so every sentence with a から phrase also has a へ phrase. Which sentences really reach the typed step is checked on the base tree: artifacts/w5-f/w5f_gates_reach.txt)
F1_ABSTAIN = [
    ('姉が台車を駅へ「は」押した。', pl(姉=P, 台車=A_, 駅=PL, 押す='P_ACT')),
    ('妹が箱を港へ『も』蹴った。', pl(妹=P, 箱=A_, 港=PL, 蹴る='P_ACT')),
    ('父が箱を畑へ（は）引いた。', pl(父=P, 箱=A_, 畑=PL, 引く='P_ACT')),
    ('母が自転車を広場へ、「も」押した。', pl(母=P, 自転車=A_, 広場=PL, 押す='P_ACT')),
    ('叔母が机を病院へ 「は」 叩いた。', pl(叔母=P, 机=A_, 病院=PL, 叩く='P_ACT')),
    ('祖母が箱を市場から“も”駅へ押した。', pl(祖母=P, 箱=A_, 市場=PL, 駅=PL, 押す='P_ACT')),
    ('弟が荷物を校庭から「さえ」港へ引っ張った。', pl(弟=P, 荷物=A_, 校庭=PL, 港=PL, 引っ張る='P_ACT')),
    ('兄が台車を「も」広場へ押した。', pl(兄=P, 台車=A_, 広場=PL, 押す='P_ACT')),
    ('姉が「は」荷物を港へ拾った。', pl(姉=P, 荷物=A_, 港=PL, 拾う='P_ACT')),
    ('妹が自転車を駅へ「ね」押した。', pl(妹=P, 自転車=A_, 駅=PL, 押す='P_ACT')),
    ('父が机を畑から「よ」工場へ戻した。', pl(父=P, 机=A_, 畑=PL, 工場=PL, 戻す='P_ACT')),
    ('母が箱を病院へ「倉庫」引いた。', pl(母=P, 箱=A_, 病院=PL, 引く='P_ACT')),
    ('叔父が荷物を工場へ『ああ』投げ込んだ。', pl(叔父=P, 荷物=A_, 工場=PL, 投げ込む='P_ACT')),
    ('姉が台車を公園から（も）店へ押した。', pl(姉=P, 台車=A_, 公園=PL, 店=PL, 押す='P_ACT')),
    ('兄が学校へ「も」走った。', pl(兄=P, 学校=PL, 走る='P_MOVE')),
    ('妹が市場へ「は」歩いた。', pl(妹=P, 市場=PL, 歩く='P_MOVE')),
]
# read_or_abstain: the sentences of the same shapes without the quoted piece (other nouns), roles by the design of the sentence
F1_READ = [
    ('姉が台車を駅へ押した。', pl(姉=P, 台車=A_, 駅=PL, 押す='P_ACT'), {'agent': '姉', 'patient': '台車', 'goal': '駅'}),
    ('妹が箱を港へ蹴った。', pl(妹=P, 箱=A_, 港=PL, 蹴る='P_ACT'), {'agent': '妹', 'patient': '箱', 'goal': '港'}),
    ('父が箱を畑へ引いた。', pl(父=P, 箱=A_, 畑=PL, 引く='P_ACT'), {'agent': '父', 'patient': '箱', 'goal': '畑'}),
    ('母が自転車を広場へ押した。', pl(母=P, 自転車=A_, 広場=PL, 押す='P_ACT'), {'agent': '母', 'patient': '自転車', 'goal': '広場'}),
    ('叔母が机を病院へ叩いた。', pl(叔母=P, 机=A_, 病院=PL, 叩く='P_ACT'), {'agent': '叔母', 'patient': '机', 'goal': '病院'}),
    ('祖母が箱を市場から駅へ押した。', pl(祖母=P, 箱=A_, 市場=PL, 駅=PL, 押す='P_ACT'), {'agent': '祖母', 'patient': '箱', 'source': '市場', 'goal': '駅'}),
    ('弟が荷物を校庭から港へ引っ張った。', pl(弟=P, 荷物=A_, 校庭=PL, 港=PL, 引っ張る='P_ACT'), {'agent': '弟', 'patient': '荷物', 'source': '校庭', 'goal': '港'}),
    ('兄が台車を広場へ押した。', pl(兄=P, 台車=A_, 広場=PL, 押す='P_ACT'), {'agent': '兄', 'patient': '台車', 'goal': '広場'}),
    ('姉が荷物を港へ拾った。', pl(姉=P, 荷物=A_, 港=PL, 拾う='P_ACT'), {'agent': '姉', 'patient': '荷物', 'goal': '港'}),
    ('父が机を畑から工場へ戻した。', pl(父=P, 机=A_, 畑=PL, 工場=PL, 戻す='P_ACT'), {'agent': '父', 'patient': '机', 'source': '畑', 'goal': '工場'}),
    ('叔父が荷物を工場へ投げ込んだ。', pl(叔父=P, 荷物=A_, 工場=PL, 投げ込む='P_ACT'), {'agent': '叔父', 'patient': '荷物', 'goal': '工場'}),
    ('姉が台車を公園から店へ押した。', pl(姉=P, 台車=A_, 公園=PL, 店=PL, 押す='P_ACT'), {'agent': '姉', 'patient': '台車', 'source': '公園', 'goal': '店'}),
    ('兄が学校へ走った。', pl(兄=P, 学校=PL, 走る='P_MOVE'), {'agent': '兄', 'goal': '学校'}),
    ('妹が市場へ歩いた。', pl(妹=P, 市場=PL, 歩く='P_MOVE'), {'agent': '妹', 'goal': '市場'}),
    ('弟が公園へ走った。', pl(弟=P, 公園=PL, 走る='P_MOVE'), {'agent': '弟', 'goal': '公園'}),
    ('母が病院へ歩いた。', pl(母=P, 病院=PL, 歩く='P_MOVE'), {'agent': '母', 'goal': '病院'}),
]

# ---------------------------------------------------------------------------------------------- F2
F2_ABSTAIN = [
    ('妹が箱を上へ蹴った。', pl(妹=P, 箱=A_, 上=PL, 蹴る='P_ACT')),
    ('兄が台車を前へ押した。', pl(兄=P, 台車=A_, 前=PL, 押す='P_ACT')),
    ('姉が箱を中へ引いた。', pl(姉=P, 箱=A_, 中=PL, 引く='P_ACT')),
    ('父が机を先へ叩いた。', pl(父=P, 机=A_, 先=PL, 叩く='P_ACT')),
    ('母が荷物を後へ押した。', pl(母=P, 荷物=A_, 後=PL, 押す='P_ACT')),
    ('叔母が箱を近くへ拾った。', pl(叔母=P, 箱=A_, 近く=PL, 拾う='P_ACT')),
    ('祖母が台車を遠くへ押した。', pl(祖母=P, 台車=A_, 遠く=PL, 押す='P_ACT')),
    ('弟が荷物を辺りへ投げ込んだ。', pl(弟=P, 荷物=A_, 辺り=PL, 投げ込む='P_ACT')),
    ('兄が箱を上から駅へ押した。', pl(兄=P, 箱=A_, 上=PL, 駅=PL, 押す='P_ACT')),
    ('姉が机を中から広場へ引いた。', pl(姉=P, 机=A_, 中=PL, 広場=PL, 引く='P_ACT')),
    ('妹が台車を前から港へ押した。', pl(妹=P, 台車=A_, 前=PL, 港=PL, 押す='P_ACT')),
    ('父が荷物を近くから校庭へ引っ張った。', pl(父=P, 荷物=A_, 近く=PL, 校庭=PL, 引っ張る='P_ACT')),
    ('兄が上へ走った。', pl(兄=P, 上=PL, 走る='P_MOVE')),
    ('姉が中から港へ歩いた。', pl(姉=P, 中=PL, 港=PL, 歩く='P_MOVE')),
    ('弟が前で走った。', pl(弟=P, 前=PL, 走る='P_MOVE')),
    ('妹が近くで歩いた。', pl(妹=P, 近く=PL, 歩く='P_MOVE')),
    ('母が遠くから駅へ走った。', pl(母=P, 遠く=PL, 駅=PL, 走る='P_MOVE')),
    ('父が辺りで歩いた。', pl(父=P, 辺り=PL, 歩く='P_MOVE')),
]
F2_READ = [
    ('妹が箱を畑へ蹴った。', pl(妹=P, 箱=A_, 畑=PL, 蹴る='P_ACT'), {'agent': '妹', 'patient': '箱', 'goal': '畑'}),
    ('兄が台車を学校へ押した。', pl(兄=P, 台車=A_, 学校=PL, 押す='P_ACT'), {'agent': '兄', 'patient': '台車', 'goal': '学校'}),
    ('姉が箱を倉庫へ引いた。', pl(姉=P, 箱=A_, 倉庫=PL, 引く='P_ACT'), {'agent': '姉', 'patient': '箱', 'goal': '倉庫'}),
    ('父が机を駅へ叩いた。', pl(父=P, 机=A_, 駅=PL, 叩く='P_ACT'), {'agent': '父', 'patient': '机', 'goal': '駅'}),
    ('母が荷物を港へ押した。', pl(母=P, 荷物=A_, 港=PL, 押す='P_ACT'), {'agent': '母', 'patient': '荷物', 'goal': '港'}),
    ('叔母が箱を病院へ拾った。', pl(叔母=P, 箱=A_, 病院=PL, 拾う='P_ACT'), {'agent': '叔母', 'patient': '箱', 'goal': '病院'}),
    ('祖母が台車を市場へ押した。', pl(祖母=P, 台車=A_, 市場=PL, 押す='P_ACT'), {'agent': '祖母', 'patient': '台車', 'goal': '市場'}),
    ('弟が荷物を公園へ投げ込んだ。', pl(弟=P, 荷物=A_, 公園=PL, 投げ込む='P_ACT'), {'agent': '弟', 'patient': '荷物', 'goal': '公園'}),
    ('兄が箱を畑から駅へ押した。', pl(兄=P, 箱=A_, 畑=PL, 駅=PL, 押す='P_ACT'), {'agent': '兄', 'patient': '箱', 'source': '畑', 'goal': '駅'}),
    ('姉が机を工場から広場へ引いた。', pl(姉=P, 机=A_, 工場=PL, 広場=PL, 引く='P_ACT'), {'agent': '姉', 'patient': '机', 'source': '工場', 'goal': '広場'}),
    ('妹が台車を市場から港へ押した。', pl(妹=P, 台車=A_, 市場=PL, 港=PL, 押す='P_ACT'), {'agent': '妹', 'patient': '台車', 'source': '市場', 'goal': '港'}),
    ('父が荷物を店から校庭へ引っ張った。', pl(父=P, 荷物=A_, 店=PL, 校庭=PL, 引っ張る='P_ACT'), {'agent': '父', 'patient': '荷物', 'source': '店', 'goal': '校庭'}),
    ('兄が学校へ走った。', pl(兄=P, 学校=PL, 走る='P_MOVE'), {'agent': '兄', 'goal': '学校'}),
    ('姉が公園から港へ歩いた。', pl(姉=P, 公園=PL, 港=PL, 歩く='P_MOVE'), {'agent': '姉', 'source': '公園', 'goal': '港'}),
    ('弟が校庭で走った。', pl(弟=P, 校庭=PL, 走る='P_MOVE'), {'agent': '弟', 'place': '校庭'}),
    ('妹が広場で歩いた。', pl(妹=P, 広場=PL, 歩く='P_MOVE'), {'agent': '妹', 'place': '広場'}),
    ('母が畑から駅へ走った。', pl(母=P, 畑=PL, 駅=PL, 走る='P_MOVE'), {'agent': '母', 'source': '畑', 'goal': '駅'}),
    ('父が港で歩いた。', pl(父=P, 港=PL, 歩く='P_MOVE'), {'agent': '父', 'place': '港'}),
]

# ---------------------------------------------------------------------------------------------- F3 (no placement)
F3_ABSTAIN = [
    '優勝者は健太と大輔だ。',
    '担当は次郎と美咲です。',
    '会長は由紀や誠でした。',
    '受賞者は剛志か隆だ。',
    '隊長は由紀と誠の二人である。',
    '首謀者は店長や課長だった。',
    '窓口は総務課と経理課です。',
    '責任者は部長と課長の二人でした。',
    '講師は佐知と花音だった。',
    '司会は優太か美月である。',
    '次郎とも美咲とも相談した。',
    '健太とも大輔とも会った。',
    '由紀とも誠とも話した。',
    '店長とも課長とも握手した。',
    '剛志とも隆とも連絡した。',
    '祖父とも祖母とも暮らした。',
]
F3_READ = [
    ('優勝者は健太だ。', {'entity': '優勝者', 'value': '健太'}),
    ('隊長は剛志です。', {'entity': '隊長', 'value': '剛志'}),
    ('窓口は総務課でした。', {'entity': '窓口', 'value': '総務課'}),
    ('責任者は店長である。', {'entity': '責任者', 'value': '店長'}),
    ('受付は由紀だった。', {'entity': '受付', 'value': '由紀'}),
    ('担当者は鈴木だった。', {'entity': '担当者', 'value': '鈴木'}),
    ('秘書は剛志だった。', {'entity': '秘書', 'value': '剛志'}),
    ('次郎とも話した。', {'companion': '次郎'}),
    ('美咲とも会った。', {'companion': '美咲'}),
    ('健太が由紀と話した。', {'agent': '健太', 'companion': '由紀'}),
    ('大輔が誠と会った。', {'agent': '大輔', 'companion': '誠'}),
    ('店長が課長と相談した。', {'agent': '店長', 'companion': '課長'}),
    ('講師は花音だった。', {'entity': '講師', 'value': '花音'}),
    ('司会は優太です。', {'entity': '司会', 'value': '優太'}),
]


def main():
    out = sys.argv[1]
    only = None
    if '--only' in sys.argv: only = set(sys.argv[sys.argv.index('--only') + 1].split(','))
    for g, ab, rd in (('F1', F1_ABSTAIN, F1_READ), ('F2', F2_ABSTAIN, F2_READ)):
        n = 0
        for text, pm in ab: n += 1; add(g, n, text, 'abstain', pm)
        for text, pm, roles in rd: n += 1; add(g, n, text, 'read_or_abstain', pm, roles)
    n = 0
    for text in F3_ABSTAIN: n += 1; add('F3', n, text, 'abstain', None)
    for text, roles in F3_READ: n += 1; add('F3', n, text, 'read_or_abstain', None, roles)
    keep = [r for r in rows if only is None or r['id'] in only]
    with open(out, 'w', encoding='utf-8') as f:
        for r in keep: f.write(json.dumps(r, ensure_ascii=False) + '\n')
    print('rows', len(keep))


main()
