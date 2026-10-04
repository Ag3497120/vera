#!/usr/bin/env python3
"""W3-b1 手順 4: 検査データ ja_r8.jsonl・en_r4.jsonl を書く生成スクリプト。

このスクリプトは verantyx を import しない(読解器にも入口にも配置にも通さずに、期待を先に書いて凍結するため)。
語は、配置の問い合わせ(`python -m verantyx.coarse_place --term <語> --placement <配置>`)の答えを見て選んだ(答えは artifacts/w3-b1/r8_placement_answers.jsonl)。
1 行の形(B1 v2 の 1 問の形に鍵を足したもの):
  id, lang, behavior, input, text(= input), expect{readable, clauses, relations, must_not}, path(U|S4|EN), pred_type, construction,
  entry_expect(read|abstain), expect_reason_prefix, note
`expect` は規約どおりの正しい読み(普通の文なら readable true と節。規約に役割が無い構成だけを含む文は readable false)。`entry_expect` は「登録した表と門と
配置の答えなら入口は読むはず/棄権するはず」で、両者を混ぜない。
使い方: python tests/reading_soundness/w3b1_mk_r8.py [--out-dir DIR]   (DIR の既定はこのファイルの隣)
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROWS = []
COUNTER = {'U': 0, 'S4': 0, 'EN': 0}


def C(pred, roles, pol='+', tense='past', mod=None, voice='active'):
    return {'predicate': pred, 'roles': roles, 'polarity': pol, 'tense': tense, 'modality': mod, 'voice': voice}


def add(path, text, clauses, pred_type, construction, entry, reason=None, note='', must_not=None, lang='ja'):
    """clauses が None なら expect.readable は false(規約に役割が無い構成だけで決まる文)。"""
    COUNTER[path] += 1
    readable = clauses is not None
    ROWS.append({
        'id': 'W3B1-%s-%03d' % (path, COUNTER[path]), 'lang': lang, 'behavior': 'read' if readable else 'abstain',
        'input': text, 'text': text,
        'expect': {'readable': readable, 'clauses': clauses or [], 'relations': [], 'must_not': must_not or []},
        'path': path, 'pred_type': pred_type, 'construction': construction, 'entry_expect': entry,
        'expect_reason_prefix': reason, 'note': note})


def mn_role(role, value, clause=0):
    return {'clause': clause, 'role': role, 'value': value}


# ---------------------------------------------------------------------------------------------------------------------------------
# 経路 U: 述語の型で項を読む(和文)
# ---------------------------------------------------------------------------------------------------------------------------------
# --- 読むべき文(P_MOVE): <agent>が[<source>から][<time>に]<goal>へ<動詞>た。
MOVE_READ = [
    # agent, goal, 動詞の書かれた形, 辞書形, source, time
    ('猫', '庭', '走った', '走る', None, None), ('馬', '森', '走った', '走る', None, None), ('鳥', '島', '飛んだ', '飛ぶ', None, None),
    ('兄', '村', '歩いた', '歩く', None, None), ('弟', '港', '走った', '走る', None, None), ('姉', '市場', '立ち寄った', '立ち寄る', None, None),
    ('母', '病院', '引き返した', '引き返す', None, None), ('先生', '町', '赴いた', '赴く', None, None), ('生徒', '広場', '集まった', '集まる', None, None),
    ('祖父', '寺', '歩いた', '歩く', None, None), ('父', '畑', '走った', '走る', None, None), ('妹', '橋', '歩いた', '歩く', None, None),
    ('兄', '玄関', '走った', '走る', None, None), ('学生', '倉庫', '立ち寄った', '立ち寄る', None, None), ('店員', '屋上', '走った', '走る', None, None),
    ('犬', '湖', '走った', '走る', None, None),
    ('兄', '空港', '歩いた', '歩く', '駅', None), ('弟', '山', '走った', '走る', '町', None), ('母', '台所', '歩いた', '歩く', '店', None),
    ('姉', '村', '引き返した', '引き返す', '山', None), ('祖父', '町', '歩いた', '歩く', '工場', None),
    ('弟', '港', '歩いた', '歩く', None, '夜'), ('先生', '島', '赴いた', '赴く', None, '冬'), ('姉', '公園', '走った', '走る', None, '昼'),
]
for ag, goal, written, lemma, src, tm in MOVE_READ:
    text = ag + 'が' + (src + 'から' if src else '') + (tm + 'に' if tm else '') + goal + 'へ' + written + '。'
    roles = {'agent': ag, 'goal': goal}
    if src: roles['source'] = src
    if tm: roles['time'] = tm
    cons = 'goal:へ:PLACE' + (' + source:から:PLACE' if src else '') + (' + time:に:TIME' if tm else '')
    add('U', text, [C(lemma, roles)], 'P_MOVE', cons, 'read', None,
        '述語は読解器の 4 つの一覧の外。へ の句を読解器は recipient と名付けて写せない(U1)。',
        [mn_role('recipient', goal), mn_role('place', goal), mn_role('patient', ag)])

# --- 読むべき文(P_COMMUNICATE)
COMM_READ = [
    # 文, 辞書形, roles, 構成, must_not
    ('兄が弟に名乗った。', '名乗る', {'agent': '兄', 'recipient': '弟'}, 'recipient:に:PERSON'),
    ('母が先生に断った。', '断る', {'agent': '母', 'recipient': '先生'}, 'recipient:に:PERSON'),
    ('生徒が先生に求めた。', '求める', {'agent': '生徒', 'recipient': '先生'}, 'recipient:に:PERSON'),
    ('先生が生徒に述べた。', '述べる', {'agent': '先生', 'recipient': '生徒'}, 'recipient:に:PERSON'),
    ('姉が妹に願った。', '願う', {'agent': '姉', 'recipient': '妹'}, 'recipient:に:PERSON'),
    ('祖父が学生に名乗った。', '名乗る', {'agent': '祖父', 'recipient': '学生'}, 'recipient:に:PERSON'),
    ('店員が学生に断った。', '断る', {'agent': '店員', 'recipient': '学生'}, 'recipient:に:PERSON'),
    ('父が弟に述べた。', '述べる', {'agent': '父', 'recipient': '弟'}, 'recipient:に:PERSON'),
    ('兄が弟に結果を述べた。', '述べる', {'agent': '兄', 'recipient': '弟', 'patient': '結果'}, 'recipient:に:PERSON + patient:を:ABSTRACT'),
    ('先生が生徒に名前を名乗った。', '名乗る', {'agent': '先生', 'recipient': '生徒', 'patient': '名前'}, 'recipient:に:PERSON + patient:を:INFO_LANGUAGE'),
    ('母が店員に返事を求めた。', '求める', {'agent': '母', 'recipient': '店員', 'patient': '返事'}, 'recipient:に:PERSON + patient:を:EVENT_ACT'),
    ('弟が先生に許可を求めた。', '求める', {'agent': '弟', 'recipient': '先生', 'patient': '許可'}, 'recipient:に:PERSON + patient:を:EVENT_ACT'),
    ('姉が妹に約束を求めた。', '求める', {'agent': '姉', 'recipient': '妹', 'patient': '約束'}, 'recipient:に:PERSON + patient:を:EVENT_ACT'),
    ('兄が公園で弟に名乗った。', '名乗る', {'agent': '兄', 'place': '公園', 'recipient': '弟'}, 'recipient:に:PERSON + place:で:PLACE'),
    ('姉が庭で妹に願った。', '願う', {'agent': '姉', 'place': '庭', 'recipient': '妹'}, 'recipient:に:PERSON + place:で:PLACE'),
    ('弟が駅で先生に断った。', '断る', {'agent': '弟', 'place': '駅', 'recipient': '先生'}, 'recipient:に:PERSON + place:で:PLACE'),
    ('兄が夜に弟に名乗った。', '名乗る', {'agent': '兄', 'time': '夜', 'recipient': '弟'}, 'recipient:に:PERSON + time:に:TIME'),
    ('母が冬に先生に述べた。', '述べる', {'agent': '母', 'time': '冬', 'recipient': '先生'}, 'recipient:に:PERSON + time:に:TIME'),
    ('弟が会社に願った。', '願う', {'agent': '弟', 'recipient': '会社'}, 'recipient:に:GROUP_ORG'),
    ('母が会社に断った。', '断る', {'agent': '母', 'recipient': '会社'}, 'recipient:に:GROUP_ORG'),
]
for text, lemma, roles, cons in COMM_READ:
    mn = [mn_role('goal', roles['recipient'])]
    if 'patient' in roles: mn.append(mn_role('recipient', roles['patient']))
    add('U', text, [C(lemma, roles)], 'P_COMMUNICATE', cons, 'read', None,
        '述語は読解器の 4 つの一覧の外。に の句を読解器は recipient と名付けて写せない(U1)。', mn)
add('U', '弟が先生に断らなかった。', [C('断る', {'agent': '弟', 'recipient': '先生'}, pol='-')], 'P_COMMUNICATE', 'recipient:に:PERSON (negative)', 'read', None,
    '否定の極性は今のコードのまま(態・極性・時制・モダリティの規則は変えない)。', [mn_role('goal', '先生'), {'clause': 0, 'field': 'polarity', 'value': '+'}])

# --- 棄権すべき文(P_MOVE・P_COMMUNICATE。項の型・助詞が表に合わない)
add('U', '手紙が駅へ飛んだ。', [C('飛ぶ', {'entity': '手紙', 'goal': '駅'})], 'P_MOVE', 'agent:が:MULTIPLE', 'abstain', 'PLACEMENT_MULTIPLE',
    '主語の語の配置が割れる(多義)。同点は棄権。', [mn_role('agent', '手紙'), mn_role('recipient', '駅')])
add('U', '車が駅へ走った。', [C('走る', {'entity': '車', 'goal': '駅'})], 'P_MOVE', 'agent:が:direct_via_generated', 'abstain', 'PLACEMENT_DIRECT_VIA_GENERATED',
    '主語の語は生成した定義で直接に格上げされた型(証拠の門 4)。', [mn_role('agent', '車'), mn_role('recipient', '駅')])
add('U', '兄が学校へ走った。', [C('走る', {'agent': '兄', 'goal': '学校'})], 'P_MOVE', 'goal:へ:GROUP_ORG', 'abstain', 'PLACEMENT_TYPE_MISMATCH',
    '学校の型は組織だけで場所でない。表の goal は PLACE だけ。', [mn_role('recipient', '学校')])
add('U', '母が図書館へ歩いた。', [C('歩く', {'agent': '母', 'goal': '図書館'})], 'P_MOVE', 'goal:へ:MULTIPLE', 'abstain', 'PLACEMENT_MULTIPLE',
    '多義の語。', [mn_role('recipient', '図書館')])
add('U', '犬が庭に走った。', [C('走る', {'agent': '犬', 'goal': '庭'})], 'P_MOVE', 'に:PLACE (not in the table)', 'abstain', 'PLACEMENT_TYPE_MISMATCH',
    'P_MOVE の に は時の行だけ(に+場所は居住・存在と到達が同居するので読まない)。', [mn_role('recipient', '庭'), mn_role('place', '庭')])
add('U', '鳥が島に飛んだ。', [C('飛ぶ', {'agent': '鳥', 'goal': '島'})], 'P_MOVE', 'に:PLACE (not in the table)', 'abstain', 'PLACEMENT_TYPE_MISMATCH',
    '同上。', [mn_role('recipient', '島'), mn_role('place', '島')])
add('U', '弟が一緒に公園へ走った。', None, 'P_MOVE', 'time:に:TIME(slot evidence only)', 'abstain', 'PLACEMENT_SLOT_EVIDENCE_ONLY',
    '一緒に は様態の副詞的な句。時の型が役割の分布の腕だけで決まった語で、付加に使わない(門 5)。規約に様態の役割は無いので expect は readable false。', [])
add('U', '先生が実際に山へ登った。', None, 'P_MOVE', 'time:に:TIME(slot evidence only)', 'abstain', 'PLACEMENT_SLOT_EVIDENCE_ONLY',
    '実際に は文副詞。役割の分布の腕だけが時の型の決め手(門 5)。規約に役割が無いので expect は readable false。', [])
add('U', '兄が教室で弟に断った。', [C('断る', {'agent': '兄', 'place': '教室', 'recipient': '弟'})], 'P_COMMUNICATE', 'place:で:PLACE(slot evidence only)', 'abstain',
    'PLACEMENT_SLOT_EVIDENCE_ONLY', '場所の型が役割の分布の腕だけで決まった語を付加に使わない(門 5)。', [mn_role('goal', '弟')])
add('U', '母が海で先生に述べた。', [C('述べる', {'agent': '母', 'place': '海', 'recipient': '先生'})], 'P_COMMUNICATE', 'place:で:PLACE(slot evidence only)', 'abstain',
    'PLACEMENT_SLOT_EVIDENCE_ONLY', '同上。', [mn_role('goal', '先生')])
add('U', '兄が犬に名乗った。', [C('名乗る', {'agent': '兄', 'recipient': '犬'})], 'P_COMMUNICATE', 'recipient:に:ANIMAL', 'abstain', 'PLACEMENT_TYPE_MISMATCH',
    'recipient の期待は人・組織。動物は表に無い。', [mn_role('goal', '犬')])
add('U', '姉が客に断った。', [C('断る', {'agent': '姉', 'recipient': '客'})], 'P_COMMUNICATE', 'recipient:に:MULTIPLE', 'abstain', 'PLACEMENT_MULTIPLE',
    '多義の語。', [mn_role('goal', '客')])
add('U', '兄が弟に手紙を求めた。', [C('求める', {'agent': '兄', 'recipient': '弟', 'patient': '手紙'})], 'P_COMMUNICATE', 'patient:を:MULTIPLE', 'abstain', 'PLACEMENT_MULTIPLE',
    '多義の語。', [mn_role('recipient', '手紙')])
add('U', '姉が妹に意見を述べた。', [C('述べる', {'agent': '姉', 'recipient': '妹', 'patient': '意見'})], 'P_COMMUNICATE', 'patient:を:UNPLACED', 'abstain', 'PLACEMENT_UNPLACED',
    '材料にあるが決める証拠が足りない語。「無い」と「決まらない」を混ぜない。', [mn_role('recipient', '意見')])
add('U', '兄が弟に夢を述べた。', [C('述べる', {'agent': '兄', 'recipient': '弟', 'patient': '夢'})], 'P_COMMUNICATE', 'patient:を:estimated_generated', 'abstain', 'PLACEMENT_ESTIMATED_GENERATED',
    '推定(生成)は構成であって証言でない。', [mn_role('recipient', '夢')])
add('U', '弟が兄に断られた。', [C('断る', {'agent': '兄', 'patient': '弟'}, voice='passive')], 'P_COMMUNICATE', 'passive', 'abstain', None,
    '受身。表は能動の枠だけ。引き金の外(受身は 読解器の節に recipient も ambiguous も無い)でもよい。', [{'clause': 0, 'field': 'voice', 'value': 'active'}])
add('U', '兄は弟に名乗った。', [C('名乗る', {'agent': '兄', 'recipient': '弟'})], 'P_COMMUNICATE', 'は topic', 'abstain', None,
    'は の主題の節は読解器が割れると言う(ambiguous frame role)。型で上書きしない。', [mn_role('goal', '弟')])
add('U', 'そして兄が弟に名乗った。', None, 'P_COMMUNICATE', 'sentence-initial connective', 'abstain', 'PLACEMENT_REREAD_ABSTAINS',
    '文頭の接続詞は文をまたぐ関係(入口は写さない)。型で決めた役割で今の写しに通しても、今の規則が棄権する。', [])
add('U', '兄が弟に名乗りたい。', [C('名乗る', {'agent': '兄', 'recipient': '弟'}, tense='nonpast', mod='desire')], 'P_COMMUNICATE', 'modality', 'abstain', 'PLACEMENT_REREAD_ABSTAINS',
    '願望のモダリティは今の入口が出さない(UNDETERMINED_MODALITY)。', [{'clause': 0, 'field': 'modality', 'value': None}])
add('U', '母が先生に断るだろう。', [C('断る', {'agent': '母', 'recipient': '先生'}, tense='nonpast', mod='conjecture')], 'P_COMMUNICATE', 'modality', 'abstain', 'PLACEMENT_REREAD_ABSTAINS',
    '推量のモダリティは今の入口が出さない。', [{'clause': 0, 'field': 'modality', 'value': None}])

# --- 棄権すべき文(読まない型。11 型 x 4 文)。述語は読解器の 4 つの一覧の外で、に+人 か へ+場所 を持つ
NOT_READ = {
    'P_GIVE': [('兄が弟に買った。', '買う', 'recipient', '弟'), ('母が先生に出した。', '出す', 'recipient', '先生'),
               ('姉が妹に添えた。', '添える', 'recipient', '妹'), ('父が生徒に施した。', '施す', 'recipient', '生徒')],
    'P_CHANGE': [('兄が弟に近づいた。', '近づく', 'goal', '弟'), ('犬が兄に迫った。', '迫る', 'goal', '兄'),
                 ('猫が弟に近づいた。', '近づく', 'goal', '弟'), ('母が先生に迫った。', '迫る', 'goal', '先生')],
    'P_CREATE': [('兄が弟に手渡した。', '手渡す', 'recipient', '弟'), ('母が先生に差し出した。', '差し出す', 'recipient', '先生'),
                 ('姉が妹に差し出した。', '差し出す', 'recipient', '妹'), ('父が生徒に手渡した。', '手渡す', 'recipient', '生徒')],
    'P_PERCEIVE': [('兄が弟に見えた。', '見える', None, None), ('先生が生徒に見えた。', '見える', None, None),
                   ('姉が妹に見えた。', '見える', None, None), ('母が店員に見えた。', '見える', None, None)],
    'P_EXIST': [('兄が町に暮らした。', '暮らす', 'place', '町'), ('弟が村に泊まった。', '泊まる', 'place', '村'),
                ('犬が庭に隠れた。', '隠れる', 'place', '庭'), ('祖父が寺に泊まった。', '泊まる', 'place', '寺')],
    'P_POSSESS': [('兄が弟に引き継いだ。', '引き継ぐ', 'recipient', '弟'), ('母が先生に引き継いだ。', '引き継ぐ', 'recipient', '先生'),
                  ('姉が妹に隠した。', '隠す', None, None), ('父が生徒に隠した。', '隠す', None, None)],
    'P_ACT': [('兄が駅へ送り出した。', '送り出す', 'goal', '駅'), ('弟が港へ踏み出した。', '踏み出す', 'goal', '港'),
              ('母が庭へ踏み込んだ。', '踏み込む', 'goal', '庭'), ('姉が部屋へ踏み入れた。', '踏み入れる', 'goal', '部屋')],
    'P_STATE': [('兄が先生に従った。', '従う', None, None), ('弟が兄に従った。', '従う', None, None), ('生徒が先生に従った。', '従う', None, None),
                ('姉が母に従った。', '従う', None, None), ('妹が姉に似た。', '似る', None, None)],
    'P_COGNITION': [('兄が弟に慣れた。', '慣れる', None, None), ('母が先生に困った。', '困る', None, None),
                    ('犬が兄に慣れた。', '慣れる', None, None), ('弟が先生に慣れた。', '慣れる', None, None)],
    'P_EMOTION': [('母が弟に怒った。', '怒る', None, None), ('兄が先生に驚いた。', '驚く', None, None),
                  ('姉が妹に怒った。', '怒る', None, None), ('弟が兄に笑った。', '笑う', None, None)],
    'P_CONSUME': [('兄が弟に残した。', '残す', None, None), ('母が先生に残した。', '残す', None, None),
                  ('姉が妹に残した。', '残す', None, None), ('父が生徒に残した。', '残す', None, None)],
}
NOT_READ_WHY = {
    'P_GIVE': 'に の役割が成員で割れる(受け手・恩恵・到達点)。', 'P_CHANGE': 'に が result か goal か time か。', 'P_CREATE': 'に+人 が recipient か beneficiary か。',
    'P_PERCEIVE': 'に が source か recipient か(見える の に の役割は規約で決まらない)。', 'P_EXIST': 'が が entity か agent か。に は place(居住・存在)。',
    'P_POSSESS': '助詞と役割の対応が型で決まらない。', 'P_ACT': '助詞と役割の対応が型で決まらない。', 'P_STATE': 'に の役割が規約に無い(従う・似る の対象)。',
    'P_COGNITION': 'に が決まらない(対象・原因)。', 'P_EMOTION': 'に・で が対象か原因か。', 'P_CONSUME': 'に の役割が決まらない(受け手か恩恵か)。'}
for ptype, items in NOT_READ.items():
    for text, lemma, role, value in items:
        agent = text.split('が')[0]
        if role is None:
            clauses = None
            cons = 'に:' + ptype + ' (role not in the convention)'
        else:
            particle = 'へ' if role == 'goal' and 'へ' in text else 'に'
            clauses = [C(lemma, {'agent': agent, role: value})]
            cons = particle + ':' + ptype + ' (frame not read)'
        add('U', text, clauses, ptype, cons, 'abstain', 'PLACEMENT_FRAME_NOT_READ',
            '読まない型。' + NOT_READ_WHY[ptype], [mn_role('recipient', value)] if (role == 'goal' and value) else [])

# ---------------------------------------------------------------------------------------------------------------------------------
# 経路 S4: 表せない部分を時・場所として読む(和文)
# ---------------------------------------------------------------------------------------------------------------------------------
# --- 読むべき文: <agent>が<時の語>、<物>を<動詞>た。(時の語は門 5 を通る直接の TIME。文頭でないので読解器は時の副詞として読まない)
S4_READ = [
    ('母', '夜', '手紙', '書いた', '書く'), ('弟', '夜', '皿', '洗った', '洗う'), ('姉', '夜', '扉', '閉めた', '閉める'),
    ('兄', '冬', '窓', '閉めた', '閉める'), ('父', '冬', '靴', '磨いた', '磨く'), ('祖父', '冬', '本', '読んだ', '読む'),
    ('先生', '昼', '本', '読んだ', '読む'), ('妹', '昼', '皿', '洗った', '洗う'), ('生徒', '昼', '絵', '描いた', '描く'),
    ('店員', '休日', '床', '磨いた', '磨く'), ('母', '休日', '食器', '洗った', '洗う'), ('兄', '休日', '手紙', '書いた', '書く'),
    ('父', '平日', '窓', '開けた', '開ける'), ('姉', '平日', '靴', '磨いた', '磨く'), ('弟', '平日', '本', '読んだ', '読む'),
    ('母', '年末', '床', '磨いた', '磨く'), ('兄', '年末', '窓', '洗った', '洗う'), ('先生', '年末', '手紙', '書いた', '書く'),
    ('生徒', '放課後', '床', '磨いた', '磨く'), ('学生', '放課後', '本', '読んだ', '読む'), ('妹', '放課後', '窓', '開けた', '開ける'),
    ('父', '月末', '手紙', '書いた', '書く'), ('姉', '月末', '食器', '洗った', '洗う'), ('弟', '月末', '靴', '磨いた', '磨く'),
    ('母', '誕生日', '手紙', '書いた', '書く'), ('兄', '誕生日', '絵', '描いた', '描く'), ('祖父', '誕生日', '本', '読んだ', '読む'),
    ('姉', '大晦日', '床', '磨いた', '磨く'), ('父', '大晦日', '窓', '洗った', '洗う'), ('先生', '大晦日', '本', '読んだ', '読む'),
    ('弟', '春休み', '本', '読んだ', '読む'), ('妹', '春休み', '絵', '描いた', '描く'), ('生徒', '春休み', '手紙', '書いた', '書く'),
    ('兄', '年明け', '窓', '開けた', '開ける'), ('母', '年明け', '床', '磨いた', '磨く'), ('姉', '年明け', '手紙', '書いた', '書く'),
]
for ag, tm, obj, written, lemma in S4_READ:
    add('S4', '%sが%s、%sを%s。' % (ag, tm, obj, written), [C(lemma, {'agent': ag, 'time': tm, 'patient': obj})], None, 'time:∅(、):TIME', 'read', None,
        '時の語が文頭でなく、読解器の時の副詞(文頭のみ)に当たらない。覆われない部分(unrepresented source content)を TIME+∅ として読む。',
        [mn_role('place', tm), mn_role('patient', tm)])

# --- 棄権すべき文
S4_ABSTAIN_FRAME = '%sが%s、%sを%s。'


def s4a(ag, tm, obj, written, lemma, cons, reason, note, *, readable=True, extra_mn=None):
    text = S4_ABSTAIN_FRAME % (ag, tm, obj, written)
    clauses = [C(lemma, {'agent': ag, 'time': tm, 'patient': obj})] if readable else None
    add('S4', text, clauses, None, cons, 'abstain', reason, note, [mn_role('place', tm)] + (extra_mn or []))


for ag, tm, obj, written, lemma in [('兄', '夏', '窓', '開けた', '開ける'), ('母', '秋', '皿', '洗った', '洗う'), ('弟', '夕方', '靴', '磨いた', '磨く'),
                                    ('姉', '週末', '本', '読んだ', '読む'), ('父', '早朝', '床', '磨いた', '磨く'), ('先生', '正午', '手紙', '書いた', '書く'),
                                    ('妹', '日曜', '扉', '閉めた', '閉める'), ('祖父', '夜中', '窓', '閉めた', '閉める')]:
    s4a(ag, tm, obj, written, lemma, 'time:∅(、):TIME(slot evidence only)', 'PLACEMENT_SLOT_EVIDENCE_ONLY', '時の型が役割の分布の腕だけで決まった語(門 5)。')
for ag, tm, obj, written, lemma in [('兄', '先週', '窓', '開けた', '開ける'), ('母', '来週', '手紙', '書いた', '書く'), ('弟', '去年', '本', '読んだ', '読む'),
                                    ('姉', '来年', '絵', '描いた', '描く')]:
    s4a(ag, tm, obj, written, lemma, 'time:∅(、):TIME(estimated_generated)', 'PLACEMENT_ESTIMATED_GENERATED', '推定(生成)は構成であって証言でない。')
for ag, tm, obj, written, lemma in [('兄', '夜明け', '窓', '開けた', '開ける'), ('母', '真夜中', '皿', '洗った', '洗う'), ('弟', '連休', '本', '読んだ', '読む'),
                                    ('姉', '週明け', '手紙', '書いた', '書く')]:
    s4a(ag, tm, obj, written, lemma, 'time:∅(、):TIME(direct_via_generated)', 'PLACEMENT_DIRECT_VIA_GENERATED', '生成した定義で直接に格上げされた型(門 4)。')
for ag, tm, obj, written, lemma in [('兄', '春', '窓', '開けた', '開ける'), ('母', '梅雨', '靴', '磨いた', '磨く'), ('弟', '明日', '本', '読んだ', '読む'),
                                    ('姉', '最近', '手紙', '書いた', '書く')]:
    s4a(ag, tm, obj, written, lemma, 'time:∅(、):MULTIPLE', 'PLACEMENT_MULTIPLE', '多義の語。同点は棄権。')
for ag, tm, obj, written, lemma in [('兄', '朝', '窓', '開けた', '開ける'), ('母', '未明', '皿', '洗った', '洗う'), ('弟', '夕べ', '本', '読んだ', '読む'),
                                    ('姉', '冬休み', '絵', '描いた', '描く')]:
    s4a(ag, tm, obj, written, lemma, 'time:∅(、):UNPLACED', 'PLACEMENT_UNPLACED', '材料にあるが決める証拠が足りない語。')
# 様態(副詞・形状詞)。規約に様態の役割は無いので、expect は readable false
for ag, adv, obj, written in [('兄', 'そっと', '窓', '開けた'), ('母', 'ゆっくり', '手紙', '書いた'), ('弟', 'きちんと', '靴', '磨いた'),
                              ('姉', 'はっきり', '名前', '書いた')]:
    add('S4', '%sが%s%sを%s。' % (ag, adv, obj, written), None, None, 'manner:副詞', 'abstain', 'PLACEMENT_PART_NOT_NP',
        '様態の副詞。規約 §2 に様態の役割は無い(副詞の部分は名詞句でない)。', [mn_role('place', adv), mn_role('time', adv)])
for ag, adv, obj, written in [('兄', '静かに', '窓', '閉めた'), ('母', '丁寧に', '皿', '洗った')]:
    add('S4', '%sが%s%sを%s。' % (ag, adv, obj, written), None, None, 'manner:形状詞', 'abstain', 'PLACEMENT_PART_NOT_NP',
        '様態の形状詞+に。規約に様態の役割は無い。', [mn_role('place', adv.rstrip('に')), mn_role('time', adv.rstrip('に'))])
# 数量(数詞)。規約に数量の役割は無い(quantifiers は入口が出さない)
for ag, q, obj, written in [('兄', '三回', '窓', '開けた'), ('母', '二回', '手紙', '書いた'), ('弟', '五回', '皿', '洗った'), ('姉', '十回', '靴', '磨いた')]:
    add('S4', '%sが%s、%sを%s。' % (ag, q, obj, written), None, None, 'quantity:数詞', 'abstain', 'PLACEMENT_PART_MARKER:quant',
        '数詞を含む部分。数量は quantifiers で、入口は出さない。', [mn_role('time', q), mn_role('place', q)])
# の で名詞にかかる部分
for ag, tm, obj, written, lemma in [('母', '冬の夜', '窓', '閉めた', '閉める'), ('兄', '冬の朝', '手紙', '書いた', '書く'), ('弟', '冬の昼', '本', '読んだ', '読む')]:
    add('S4', S4_ABSTAIN_FRAME % (ag, tm, obj, written), [C(lemma, {'agent': ag, 'time': tm, 'patient': obj})], None, 'time:の+名詞', 'abstain',
        'PLACEMENT_PART_NO_ROLE', '部分の直後が の。名詞にかかる語の一部だけを時にすると修飾を落とす(冬の夜 の 冬 だけを読まない)。', [mn_role('time', tm.split('の')[0]), mn_role('time', tm.split('の')[1])])
# 標識(量化)
for ag, tm, obj, written, mark, rsn in [('兄', '夜', '窓', '開けた', 'だけ', None), ('母', '夜', '手紙', '書いた', 'のみ', None),
                                        ('弟', '冬', '本', '読んだ', 'ばかり', 'PLACEMENT_PART_MARKER:quant'), ('姉', '昼', '靴', '磨いた', 'しか', 'PLACEMENT_PART_MARKER:quant')]:
    neg = (mark == 'しか')
    writ = (written[:-1] + 'なかった') if neg else written
    add('S4', '%sが%s%s%sを%s。' % (ag, tm, mark, obj, writ), None, None, 'marker:quant(' + mark + ')', 'abstain', rsn,
        '限定・量化の標識(だけ・のみ・ばかり・しか)は部分の直後にある。限定は規約の役割に無い。', [mn_role('time', tm)])
# 接続詞
for conn in ('そして', 'しかし', 'また'):
    ag, tm, obj, written = {'そして': ('兄', '夜', '窓', '開けた'), 'しかし': ('母', '冬', '手紙', '書いた'), 'また': ('弟', '昼', '本', '読んだ')}[conn]
    add('S4', '%s%sが%s、%sを%s。' % (conn, ag, tm, obj, written), None, None, 'conn:' + conn, 'abstain', 'PLACEMENT_PART_MARKER:conn',
        '文頭の接続詞は文をまたぐ関係(入口は写さない)。文のどこかに接続詞があれば部分を読まない。', [mn_role('place', tm)])
# 2 文
add('S4', '兄が夜、窓を開けた。弟が夜、窓を閉めた。', None, None, 'two sentences', 'abstain', None, '2 文。入力が 1 文でないので引き金に当たらない。', [])
add('S4', '母が冬、手紙を書いた。姉が冬、手紙を読んだ。', None, None, 'two sentences', 'abstain', None, '2 文。', [])
# 部分の直前に覆われない修飾(指示の連体詞)
for ag, dem, tm, obj, written, lemma in [('兄', 'この', '夜', '窓', '開けた', '開ける'), ('弟', 'その', '冬', '本', '読んだ', '読む'), ('母', 'あの', '夜', '手紙', '書いた', '書く')]:
    add('S4', '%sが%s%s、%sを%s。' % (ag, dem, tm, obj, written), [C(lemma, {'agent': ag, 'time': tm, 'patient': obj})], None, 'time:連体詞+名詞', 'abstain', 'PLACEMENT_PART_NOT_ISOLATED',
        '部分の直前に覆われない連体詞がある。修飾を落とさない(指示の連体詞を外す規則は役割の句の中だけ)。', [mn_role('place', tm)])
# で+場所(読解器が場所と知らない語は ambiguous で。引き金の外)
add('S4', '兄が川で窓を洗った。', [C('洗う', {'agent': '兄', 'place': '川', 'patient': '窓'})], None, 'place:で:PLACE (reader says ambiguous)', 'abstain', None,
    '読解器は で の句を場所|手段で割れると言う(unsupported ambiguous case role: で)。引き金の外。型で上書きしない。', [mn_role('instrument', '川')])
add('S4', '母が森で靴を洗った。', [C('洗う', {'agent': '母', 'place': '森', 'patient': '靴'})], None, 'place:で:PLACE (reader says ambiguous)', 'abstain', None,
    '同上。', [mn_role('instrument', '森')])

# ---------------------------------------------------------------------------------------------------------------------------------
# 英語(すべて棄権。配置に英語の述語が 0 件、日常語の名詞に direct が無い)
# ---------------------------------------------------------------------------------------------------------------------------------
for text, lemma, roles in [
        ('The dog sprinted to the park.', 'sprint', {'agent': 'the dog', 'goal': 'the park'}),
        ('The girl whispered to the boy.', 'whisper', {'agent': 'the girl', 'recipient': 'the boy'}),
        ('The teacher lectured the students.', 'lecture', {'agent': 'the teacher', 'patient': 'the students'}),
        ('The boy strolled to the station.', 'stroll', {'agent': 'the boy', 'goal': 'the station'}),
        ('The woman hurried to the shop.', 'hurry', {'agent': 'the woman', 'goal': 'the shop'}),
        ('The man wandered to the river.', 'wander', {'agent': 'the man', 'goal': 'the river'}),
        ('A bird fluttered to the garden.', 'flutter', {'agent': 'a bird', 'goal': 'the garden'}),
        ('The farmer shouted to the worker.', 'shout', {'agent': 'the farmer', 'recipient': 'the worker'})]:
    add('EN', text, [C(lemma, roles)], None, 'unknown predicate (English)', 'abstain', 'PLACEMENT_',
        '閉じた動詞の一覧の外(UNKNOWN_PREDICATE)。配置が指定されていても英語は読まない。', [], lang='en')
for text, lemma, roles in [
        ('The boy opened the window at night.', 'open', {'agent': 'the boy', 'patient': 'the window', 'time': 'at night'}),
        ('The girl closed the door in the morning.', 'close', {'agent': 'the girl', 'patient': 'the door', 'time': 'in the morning'}),
        ('The woman washed the dishes in the kitchen.', 'wash', {'agent': 'the woman', 'patient': 'the dishes', 'place': 'in the kitchen'}),
        ('The man cleaned the garage after lunch.', 'clean', {'agent': 'the man', 'patient': 'the garage', 'time': 'after lunch'}),
        ('The farmer painted the fence yesterday.', 'paint', {'agent': 'the farmer', 'patient': 'the fence', 'time': 'yesterday'}),
        ('The teacher wrote the report at home.', 'write', {'agent': 'the teacher', 'patient': 'the report', 'place': 'at home'}),
        ('The girl cleaned the room quietly.', 'clean', {'agent': 'the girl', 'patient': 'the room'}),
        ('The boy washed the car in the garden.', 'wash', {'agent': 'the boy', 'patient': 'the car', 'place': 'in the garden'})]:
    add('EN', text, [C(lemma, roles)], None, 'adjunct (English)', 'abstain', None,
        '英語の付加語(UNREPRESENTED_CONTENT)は変えない。英語の枠に時・場所の役割が無い。', [], lang='en')


def write(out_dir):
    ja = [r for r in ROWS if r['lang'] == 'ja']
    en = [r for r in ROWS if r['lang'] == 'en']
    (out_dir / 'ja_r8.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in ja), encoding='utf-8')
    (out_dir / 'en_r4.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in en), encoding='utf-8')
    return len(ja), len(en)


def strings(obj):
    """すべての文字列値(辞書の鍵は含めない。tests/test_event_cross_data.py と同じ数え方)。"""
    if isinstance(obj, str): yield obj
    elif isinstance(obj, dict):
        for v in obj.values(): yield from strings(v)
    elif isinstance(obj, list):
        for v in obj: yield from strings(v)


def load_values(paths):
    seen = set()
    for p in paths:
        for line in p.read_text(encoding='utf-8').splitlines():
            if line.strip():
                try: seen.update(s.strip() for s in strings(json.loads(line)))
                except ValueError: pass          # tests/test_event_cross_data.py も読めない行は飛ばす
    return seen


def other_values():
    """(a) 既存の凍結データ・B1 見本のすべての文字列値、(b) 十字の検査文の text。"""
    root = HERE.parents[1]
    mine = {'ja_r8.jsonl', 'en_r4.jsonl'}
    paths = [p for p in HERE.glob('*.jsonl') if p.name not in mine] + list((root / 'tests' / 'bank_score' / 'fixtures').rglob('*.jsonl'))
    cross = set()
    cpaths = list((root / 'tests' / 'event_cross' / 'data').glob('sentences_*.jsonl'))
    for p in cpaths:
        for line in p.read_text(encoding='utf-8').splitlines():
            if line.strip(): cross.add(json.loads(line)['text'].strip())
    return load_values(paths), cross, len(paths), len(cpaths)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-dir', default=str(HERE))
    ap.add_argument('--overlap-out', default=None)
    a = ap.parse_args()
    out_dir = Path(a.out_dir)
    inputs = [r['input'] for r in ROWS]
    assert len(set(inputs)) == len(inputs), 'duplicate input'
    for r in ROWS:
        for c in r['expect']['clauses']:
            for role, v in c['roles'].items():
                if r['lang'] == 'ja': assert v in r['input'], (r['id'], role, v)
    seen, cross, npaths, ncross = other_values()
    mine = set()
    for r in ROWS: mine.update(x.strip() for x in strings(r))
    inputs_shared = sorted(set(inputs) & seen)          # (a) 入力の文が既存の凍結データ・B1 見本の値と重なる
    cross_shared = sorted(mine & cross)                 # (b) 十字の検査文が、このデータのどれかの文字列値と重なる
    overlap = inputs_shared + cross_shared
    if a.overlap_out:
        Path(a.overlap_out).write_text('files_compared=%d cross_files=%d\ninputs_shared_with_existing=%d\ncross_sentences_shared_with_this_data=%d\noverlap=%d\n%s'
                                       % (npaths, ncross, len(inputs_shared), len(cross_shared), len(overlap), ''.join(x + '\n' for x in overlap)), encoding='utf-8')
    if overlap:
        print('OVERLAP', len(overlap), overlap[:10]); raise SystemExit(1)
    nja, nen = write(out_dir)
    print('ja=%d en=%d overlap=0 files_compared=%d cross_files=%d' % (nja, nen, npaths, ncross))


if __name__ == '__main__':
    main()
