#!/usr/bin/env python3
"""W3-b2 step 4: the test data w3b2_frame.jsonl, w3b2_multiple.jsonl, w3b2_determiner.jsonl, w3b2_no.jsonl (and w3b2_data_terms.json, the words the rows
could ask the placement about).

This script does not import verantyx: the expectations are written before any row goes through the entry, the reader or the new paths. The words were chosen
from the answers of the placement (`coarse_place.query`; the answers are in artifacts/w3-b2/data_placement_answers.jsonl, made from w3b2_data_terms.json by
w3b2_data_answers.py) and from the closed lists of the reader's source (read, not run).

One row: id, lang, behavior, input, text (= input), expect {readable, clauses, relations, must_not}, path (U | U3 | S4), pred_type, construction,
entry_expect (read | abstain: what the entry returns under the registered rules and the placement's answers), w3b2_expect, note.
`expect` is the correct reading by the convention (docs/READING_CONVENTIONS.md): a demonstrative is dropped from a value, a の modifier stays in it.
`w3b2_expect` is the diagnosis of `semantic_read.typed_explain_ja`: `READ` (the new path reads), a prefix of its `w3b2` reason (the new path ran and refused),
`FRAME:<prefix>` (the base of W3-b1 read and the frame stopped it), `NOT_TRIGGERED` (no typed trigger fits). The two are never mixed.
Usage: python tests/reading_soundness/w3b2_mk_data.py [--out-dir DIR]
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROWS = {'frame': [], 'multiple': [], 'determiner': [], 'no': []}
TERMS = set()


def C(pred, roles, pol='+', tense='past', mod=None, voice='active'):
    return {'predicate': pred, 'roles': roles, 'polarity': pol, 'tense': tense, 'modality': mod, 'voice': voice}


def mn(role, value, clause=0):
    return {'clause': clause, 'role': role, 'value': value}


def add(name, text, clause, path, pred_type, construction, entry, w3b2, note, must_not=None, terms=()):
    """clause: the correct reading (one clause), or None when the convention has no role for the sentence (readable false)."""
    rows = ROWS[name]
    readable = clause is not None
    rows.append({'id': 'W3B2-%s-%03d' % (name.upper(), len(rows) + 1), 'lang': 'ja', 'behavior': 'read' if readable else 'abstain', 'input': text, 'text': text,
                 'expect': {'readable': readable, 'clauses': [clause] if readable else [], 'relations': [], 'must_not': must_not or []},
                 'path': path, 'pred_type': pred_type, 'construction': construction, 'entry_expect': entry, 'w3b2_expect': w3b2, 'note': note})
    TERMS.update(t for t in terms if t)


# verbs: dictionary form -> (past form, placement type of the dictionary form in the placement run1 r6: all asked in artifacts/w3-b2/data_placement_answers.jsonl)
MOVE = {'走る': '走った', '歩く': '歩いた', '飛ぶ': '飛んだ', '降りる': '降りた', '回る': '回った', '動く': '動いた'}          # P_MOVE, direct, NOT_CONFIRMED
COMM = {'名乗る': '名乗った', '断る': '断った', '願う': '願った', '呼ぶ': '呼んだ', '誘う': '誘った'}                       # P_COMMUNICATE, direct, NOT_CONFIRMED
OTHER = {'遊ぶ': ('遊んだ', 'P_ACT'), '働く': ('働いた', 'P_ACT'), '拭く': ('拭いた', 'P_ACT'), '洗う': ('洗った', 'P_ACT'), '書く': ('書いた', 'P_CREATE'),
         '描く': ('描いた', 'P_CREATE'), '眠る': ('眠った', 'P_EXIST'), '休む': ('休んだ', 'P_EXIST'), '座る': ('座った', 'P_EXIST'),
         '泣く': ('泣いた', 'P_EMOTION'), '笑う': ('笑った', 'P_EMOTION'), '見る': ('見た', 'P_PERCEIVE'), '聞く': ('聞いた', 'P_PERCEIVE')}
PAST = dict(MOVE); PAST.update(COMM)
PAST.update({k: v[0] for k, v in OTHER.items()})
PAST.update({'歌う': '歌った', '泳ぐ': '泳いだ'})    # verbs of the D2 rows: the path does not ask their type
PTYPE = {k: 'P_MOVE' for k in MOVE}; PTYPE.update({k: 'P_COMMUNICATE' for k in COMM}); PTYPE.update({k: v[1] for k, v in OTHER.items()})

# nouns for the で-phrase of U3: PLACE, DECIDED, direct, an arm that is not a role distribution, no generated definition, and none of the reader's own place
# tests (the nouns of _PLACE_NOMINALS, the endings of _PLACE_SUFFIXES, a named place) matches: the reader leaves their で ambiguous (`case:で:place|means`)
READ_PLACES = ['校庭', '地下', '校舎', '路上', '歩道', '国道', '山頂', '森林', '廃墟', '神社', 'マンション', 'アパート', '宿舎', 'ホテル', '民宿', '川', '湖',
               '銭湯', '隠れ家', '基地']


def u3(name, agent, place, verb, note, *, patient=None, time=None, entry='read', w3b2='READ', construction=None, must_extra=(), pred_type=None):
    """<agent>が[<time>に]<place>で[<patient>を]<verb>た。 (path U3)"""
    text = agent + 'が' + (time + 'に' if time else '') + place + 'で' + (patient + 'を' if patient else '') + PAST[verb] + '。'
    roles = {'agent': agent}
    if patient: roles['patient'] = patient
    if time: roles['time'] = time
    roles['place'] = place
    cons = 'agent:が + ' + ('time:に + ' if time else '') + 'place:で:PLACE' + (' + patient:を' if patient else '')
    must = [mn('instrument', place)] + [mn(r, v) for r, v in must_extra]
    add(name, text, C(verb, roles), 'U3', pred_type or PTYPE.get(verb), construction or cons, entry, w3b2, note, must,
        terms=[agent, place, verb, patient, time])


# ===================================================================================================================================
# w3b2_frame.jsonl: the で of a clause the reader leaves ambiguous (U3), and the frame of the predicate
# ===================================================================================================================================
F = 'frame'
NOTE_U3 = '述語は読解器の 4 つの一覧の外。で の句を読解器は place|means の曖昧と言って棄権する(U3)。'
# read: a P_MOVE verb, nothing but the agent and the で-phrase
for agent, place, verb in [('兄', '校庭', '走る'), ('弟', '歩道', '走る'), ('姉', '森林', '歩く'), ('妹', '山頂', '歩く'), ('母', '神社', '歩く'), ('父', '国道', '歩く'),
                           ('犬', '校庭', '走る'), ('猫', '廃墟', '歩く'), ('馬', '森林', '走る'), ('鳥', '山頂', '飛ぶ'), ('鳥', '森林', '飛ぶ'), ('祖父', '校舎', '歩く'),
                           ('祖母', '神社', '動く'), ('店員', '歩道', '走る'), ('生徒', '校庭', '回る'), ('学生', '校舎', '走る')]:
    u3(F, agent, place, verb, NOTE_U3 + ' 述語は P_MOVE(direct・NOT_CONFIRMED)で表の place/で/PLACE(付加)に当たる。')
# read: a P_COMMUNICATE verb with no patient
for agent, place, verb in [('兄', '校舎', '名乗る'), ('姉', '神社', '願う'), ('弟', 'ホテル', '断る'), ('母', 'アパート', '断る'), ('先生', '宿舎', '名乗る'),
                           ('祖母', '隠れ家', '願う')]:
    u3(F, agent, place, verb, NOTE_U3 + ' 述語は P_COMMUNICATE(direct・NOT_CONFIRMED)。')
# read: with a patient (を). the patient's type is in the table's list of P_COMMUNICATE (patient / を)
for agent, place, patient, verb in [('兄', '校庭', '弟', '呼ぶ'), ('姉', '神社', '妹', '誘う'), ('母', '校舎', '兄', '呼ぶ'), ('先生', '国道', '生徒', '呼ぶ'),
                                    ('店員', 'ホテル', '犬', '誘う'), ('母', 'アパート', '依頼', '断る'), ('父', '神社', '合格', '願う'), ('兄', '民宿', '名前', '名乗る')]:
    u3(F, agent, place, verb, NOTE_U3 + ' 述語は P_COMMUNICATE。を の句の型が表の patient の集合に入る。', patient=patient,
       must_extra=[('recipient', patient)])
# read: with a time に (the reader reads it as `time`; the table's time/に/TIME is an adjunct: its word needs a non-slot arm)
for agent, time, place, verb in [('兄', '夜', '校庭', '走る'), ('姉', '昼', '神社', '歩く'), ('母', '冬', '宿舎', '断る'), ('父', '休日', '川', '歩く'),
                                 ('弟', '平日', '歩道', '走る'), ('先生', '夜', 'ホテル', '願う')]:
    u3(F, agent, place, verb, NOTE_U3 + ' 時の に の句(夜・昼・冬・休日・平日)は TIME の direct で、役割の分布だけでない腕を持つ。', time=time,
       must_extra=[('place', time)])
# abstain: the で-phrase is an instrument (ARTIFACT): not the table's place
for agent, noun, verb in [('兄', '杖', '歩く'), ('祖父', '杖', '歩く'), ('母', '杖', '動く'), ('弟', '棒', '走る')]:
    text = agent + 'が' + noun + 'で' + PAST[verb] + '。'
    add(F, text, C(verb, {'agent': agent, 'instrument': noun}), 'U3', 'P_MOVE', 'place:で:ARTIFACT', 'abstain', 'PLACEMENT_TYPE_MISMATCH',
        'で の句の型が ARTIFACT(道具)。表の place は PLACE だけなので読まない。正しい読みは instrument。', [mn('place', noun)], terms=[agent, noun, verb])
# abstain: the で-phrase has split types, and one of them is not PLACE (the arms are not only role distributions)
for agent, noun, verb in [('兄', '窓口', '名乗る'), ('母', 'ホール', '断る'), ('姉', 'ゲート', '願う'), ('弟', '交番', '走る')]:
    u3(F, agent, noun, verb, 'で の句の型が割れる(PLACE のほかに ABSTRACT・EVENT_ACT・INFO_LANGUAGE・PERSON のどれか)。全候補が PLACE に入らないので読まない。', entry='abstain',
       w3b2='PLACEMENT_MULTIPLE', construction='place:で:MULTIPLE(PLACE を含み外れがある)')
# abstain: a PLACE that only the role distribution arms decide (slot evidence only: gate 5), and a split one that only they decide
for agent, noun, verb in [('兄', '廊下', '走る'), ('弟', '路地', '走る'), ('祖母', '縁側', '歩く'), ('猫', '屋根', '歩く'), ('犬', '洞窟', '走る'), ('姉', '浜辺', '歩く'),
                          ('姉', '階段', '走る'), ('母', '受付', '名乗る')]:
    u3(F, agent, noun, verb, 'で の句の型が、役割の分布の腕だけで決まっている(付加の門 5)。', entry='abstain', w3b2='PLACEMENT_SLOT_EVIDENCE_ONLY',
       construction='place:で:PLACE(slot evidence only)')
# abstain: a direct that a generated definition decided, and an estimated one
for agent, noun, verb, why in [('兄', 'テラス', '歩く', 'PLACEMENT_DIRECT_VIA_GENERATED'), ('弟', '渓流', '走る', 'PLACEMENT_DIRECT_VIA_GENERATED'),
                               ('母', '長屋', '名乗る', 'PLACEMENT_DIRECT_VIA_GENERATED'), ('兄', '蔵', '名乗る', 'PLACEMENT_ESTIMATED_GENERATED'),
                               ('姉', '塹壕', '走る', 'PLACEMENT_ESTIMATED_GENERATED')]:
    u3(F, agent, noun, verb, 'で の句の語は、生成した定義で direct に格上げされた型、または生成による推定。構成であって証言でないので読まない。', entry='abstain', w3b2=why,
       construction='place:で:' + ('direct_via_generated' if 'DIRECT' in why else 'estimated_generated'))
# abstain: the word is in the material but nothing decides its type; a type that is no place at all
for agent, noun, verb in [('兄', '土間', '歩く'), ('母', '広間', '名乗る'), ('祖父', '座敷', '断る'), ('妹', '屋根裏', '歩く')]:
    u3(F, agent, noun, verb, 'で の句の語は材料にあるが、型を決める証拠が足りない(UNPLACED)。', entry='abstain', w3b2='PLACEMENT_UNPLACED', construction='place:で:UNPLACED')
u3(F, '兄', '里', '歩く', 'で の句の語の配置の型は QUANTITY(配置の側の誤り)。表の place は PLACE だけなので読まない。', entry='abstain', w3b2='PLACEMENT_TYPE_MISMATCH',
   construction='place:で:QUANTITY')
# abstain: the predicate is of a type the table does not read (P_ACT, P_CREATE, P_EXIST, P_EMOTION, P_PERCEIVE)
for agent, noun, verb in [('兄', '校庭', '遊ぶ'), ('弟', '神社', '遊ぶ'), ('母', 'ホテル', '働く'), ('父', 'アパート', '働く'), ('猫', '校舎', '眠る'), ('犬', '基地', '眠る'),
                          ('母', '隠れ家', '休む'), ('妹', '校庭', '泣く'), ('弟', '神社', '笑う'), ('祖父', '国道', '座る')]:
    u3(F, agent, noun, verb, '述語の型が K62 の表に無い型。で の句が PLACE でも読まない。', entry='abstain', w3b2='PLACEMENT_FRAME_NOT_READ:' + PTYPE[verb],
       construction='predicate:' + PTYPE[verb])
for agent, noun, patient, verb in [('姉', '校舎', '窓', '拭く'), ('兄', '校庭', '絵', '描く'), ('姉', '神社', '手紙', '書く'), ('兄', '基地', '絵', '見る')]:
    u3(F, agent, noun, verb, '述語の型が K62 の表に無い型。', patient=patient, entry='abstain', w3b2='PLACEMENT_FRAME_NOT_READ:' + PTYPE[verb],
       construction='predicate:' + PTYPE[verb], must_extra=[])
# abstain: the predicate's frame was CONFIRMED (W3-a3) and holds no で; and one whose agent type the frame does not hold
for agent, noun in [('兄', '校庭'), ('姉', '神社'), ('母', '校舎'), ('弟', '路上')]:
    text = agent + 'が' + noun + 'で叫んだ。'
    add(F, text, C('叫ぶ', {'agent': agent, 'place': noun}), 'U3', 'P_COMMUNICATE', 'frame(CONFIRMED): で が枠に無い', 'abstain',
        'PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED', '述語の枠が確認済み(叫ぶ: が と を だけ)。枠に で が無いので、表の place/で があっても読まない。', [mn('instrument', noun)],
        terms=[agent, noun, '叫ぶ'])
for agent, noun in [('会社', '校庭'), ('チーム', '国道')]:
    text = agent + 'が' + noun + 'で叫んだ。'
    add(F, text, C('叫ぶ', {'agent': agent, 'place': noun}), 'U3', 'P_COMMUNICATE', 'frame(CONFIRMED): agent が GROUP_ORG が枠の型に無い', 'abstain',
        'PLACEMENT_FRAME_TYPE_NOT_CONFIRMED', '述語の枠が確認済み(叫ぶ: が は ANIMAL・PERSON)。agent の型が GROUP_ORG で枠に無いので、表に合っても読まない。', [mn('instrument', noun)],
        terms=[agent, noun, '叫ぶ'])
# abstain: not a で case at all: `case:に:result|beneficiary` (the reader says another split; U3 does not look at it)
for agent, obj, pers, verb, past in [('兄', '作文', '弟', '直す', '直した'), ('姉', '宿題', '妹', '直す', '直した'), ('母', '手紙', '父', '直す', '直した'),
                                      ('先生', '答案', '生徒', '直す', '直した')]:
    text = agent + 'が' + pers + 'に' + obj + 'を' + past + '。'
    add(F, text, C(verb, {'agent': agent, 'beneficiary': pers, 'patient': obj}), 'U3', 'P_CHANGE', 'case:に:result|beneficiary(U3 の対象外)', 'abstain', 'PLACEMENT_W3B2_NOT_TRIGGERED',
        '読解器が に を result|beneficiary の曖昧と言っている。型で上書きしない(K94 の U3 の引き金の対象外)。', [mn('result', pers)], terms=[agent, obj, pers, verb])

# ===================================================================================================================================
# w3b2_multiple.jsonl: MULTIPLE where every candidate is what the role expects (read), and where one is not (abstain)
# ===================================================================================================================================
M = 'multiple'
NOTE_MOVE = '述語は P_MOVE(direct)で読解器の 4 つの一覧の外。へ の句を読解器は recipient と名付けて写せない(U1)。'


def goal(name, agent, place, verb, note, *, entry='read', w3b2='READ', construction=None, pred_type='P_MOVE', must=None):
    text = agent + 'が' + place + 'へ' + PAST[verb] + '。'
    add(name, text, C(verb, {'agent': agent, 'goal': place}), 'U', pred_type, construction or 'agent:が + goal:へ:PLACE', entry, w3b2, note,
        must if must is not None else [mn('recipient', place), mn('place', place)], terms=[agent, place, verb])


# read: the agent's type splits into two, both of them in the agent's set (PERSON GROUP_ORG ANIMAL). 家族: GROUP_ORG + PERSON, 警察: GROUP_ORG + PERSON
for agent, place, verb in [('家族', '庭', '走る'), ('家族', '森', '歩く'), ('家族', '島', '飛ぶ'), ('家族', '村', '歩く'), ('家族', '港', '走る'), ('家族', '橋', '歩く'),
                           ('家族', '寺', '歩く'), ('家族', '玄関', '走る'), ('家族', '山', '歩く'), ('家族', '湖', '歩く'),
                           ('警察', '屋上', '走る'), ('警察', '倉庫', '走る'), ('警察', '港', '歩く'), ('警察', '畑', '走る'), ('警察', '森', '歩く'), ('警察', '湖', '歩く'),
                           ('警察', '山', '歩く'), ('警察', '病院', '走る')]:
    goal(M, agent, place, verb, NOTE_MOVE + ' 主語の語の型が割れるが、候補がすべて agent の期待(PERSON・GROUP_ORG・ANIMAL)に入る(全候補一致)。', construction='agent:が:MULTIPLE(全候補が合う) + goal:へ:PLACE')
for agent, place, verb in [('家族', '校庭', '走る'), ('家族', '神社', '歩く'), ('警察', '国道', '走る'), ('警察', '歩道', '歩く')]:
    u3(M, agent, place, verb, NOTE_U3 + ' 主語の語の型が割れるが、候補がすべて agent の期待に入る(全候補一致)。', construction='agent:が:MULTIPLE(全候補が合う) + place:で:PLACE')
for agent, place, verb in [('家族', 'ホテル', '名乗る'), ('警察', 'アパート', '断る')]:
    u3(M, agent, place, verb, NOTE_U3 + ' 主語の語の型が割れるが、候補がすべて agent の期待に入る(全候補一致)。', construction='agent:が:MULTIPLE(全候補が合う) + place:で:PLACE')
# read: the patient's type splits and every candidate is in the table's patient set (注文: EVENT_ACT + NATURAL_PHENOMENON)
for agent, place, verb in [('兄', 'ホテル', '断る'), ('母', '民宿', '断る'), ('先生', '宿舎', '断る'), ('姉', 'アパート', '断る')]:
    u3(M, agent, place, verb, NOTE_U3 + ' を の句の型が割れるが、候補がすべて表の patient の集合に入る(全候補一致)。', patient='注文',
       construction='place:で:PLACE + patient:を:MULTIPLE(全候補が合う)', must_extra=[('recipient', '注文')])
for agent, place, verb in [('家族', '川', '歩く'), ('警察', '湖', '走る')]:
    u3(M, agent, place, verb, NOTE_U3 + ' 主語の語の型が割れるが、候補がすべて agent の期待に入る(全候補一致)。', construction='agent:が:MULTIPLE(全候補が合う) + place:で:PLACE')
for agent, place, verb in [('夫婦', 'ホテル', '名乗る'), ('住民', '神社', '願う')]:
    u3(M, agent, place, verb, NOTE_U3 + ' 主語の語の型が割れ、候補の 1 つが agent の期待の外。1 つでも外れれば読まない。', entry='abstain', w3b2='PLACEMENT_MULTIPLE',
       construction='agent:が:MULTIPLE(外れがある) + place:で:PLACE')
# abstain: the agent has split types and one is not an agent's type (ABSTRACT, NATURAL_PHENOMENON, PLACE, TIME, QUANTITY, IDENTIFIER)
for agent, place, verb in [('友人', '庭', '走る'), ('夫婦', '森', '歩く'), ('住民', '村', '歩く'), ('隊員', '港', '走る'), ('親子', '橋', '歩く'), ('一行', '寺', '歩く'),
                           ('艦隊', '湖', '歩く'), ('客', '庭', '走る'), ('鹿', '山', '走る')]:
    goal(M, agent, place, verb, NOTE_MOVE + ' 主語の語の型が割れ、候補の 1 つが agent の期待の外。1 つでも外れれば読まない。', entry='abstain', w3b2='PLACEMENT_MULTIPLE',
         construction='agent:が:MULTIPLE(外れがある)')
# abstain: the goal has split types (GROUP_ORG と PLACE ほか): the table's goal is PLACE only
for agent, place, verb in [('兄', '図書館', '走る'), ('姉', '家', '歩く'), ('母', '谷', '歩く'), ('弟', '役所', '走る'), ('妹', '本部', '歩く'), ('父', '銀行', '歩く'),
                           ('祖父', '研究所', '歩く'), ('先生', '職場', '走る')]:
    goal(M, agent, place, verb, NOTE_MOVE + ' へ の句の語の型が割れる(PLACE のほかに GROUP_ORG・STATE_PROPERTY・ABSTRACT のどれか)。表の goal は PLACE だけ。', entry='abstain',
         w3b2='PLACEMENT_MULTIPLE', construction='goal:へ:MULTIPLE(外れがある)')
# abstain: the agent is fine (all candidates) and the goal is not: nothing is read
for agent, place, verb in [('家族', '図書館', '走る'), ('警察', '家', '歩く'), ('家族', '銀行', '歩く')]:
    goal(M, agent, place, verb, NOTE_MOVE + ' 主語は全候補一致で読めるが、へ の句の型が割れて外れがある。1 つの役割でも通らなければ読まない。', entry='abstain',
         w3b2='PLACEMENT_MULTIPLE', construction='agent:が:MULTIPLE(全候補が合う) + goal:へ:MULTIPLE(外れがある)')
# abstain: the patient has split types and one is not in the table's patient set (TIME, PLACE)
for agent, place, patient, verb in [('先生', '校舎', '挨拶', '断る'), ('母', 'ホテル', '勝利', '願う'), ('姉', '神社', '日程', '断る'), ('兄', 'アパート', '地図', '断る')]:
    u3(M, agent, place, verb, NOTE_U3 + ' を の句の型が割れ、候補の 1 つが表の patient の集合の外(TIME か PLACE)。', patient=patient, entry='abstain', w3b2='PLACEMENT_MULTIPLE',
       construction='patient:を:MULTIPLE(外れがある)', must_extra=[('recipient', patient)])
# abstain: the で-phrase has split types
for agent, noun, verb in [('兄', '窓口', '歩く'), ('母', 'ホール', '走る'), ('姉', '交番', '歩く')]:
    u3(M, agent, noun, verb, 'で の句の型が割れる。付加の型は 1 つの PLACE でなければ読まない。', entry='abstain', w3b2='PLACEMENT_MULTIPLE', construction='place:で:MULTIPLE(外れがある)')
# abstain: all candidates fit the agent, but the predicate's type is not read (the predicate is never made a "全候補一致")
for agent, noun, verb in [('家族', '校庭', '遊ぶ'), ('警察', '神社', '働く'), ('家族', 'ホテル', '眠る')]:
    u3(M, agent, noun, verb, '主語は全候補一致だが、述語の型が K62 の表に無い。', entry='abstain', w3b2='PLACEMENT_FRAME_NOT_READ:' + PTYPE[verb], construction='predicate:' + PTYPE[verb])

# ===================================================================================================================================
# w3b2_determiner.jsonl: この・その・あの before a part the new path reads as an expressed part
# ===================================================================================================================================
D = 'determiner'
S4V = {'書く': ('書いた', '手紙'), '洗う': ('洗った', '皿'), '磨く': ('磨いた', '靴'), '読む': ('読んだ', '本'), '描く': ('描いた', '絵'), '拭く': ('拭いた', '窓')}


def d1(agent, det, time, patient, verb, past, **kw):
    text = agent + 'が' + det + time + '、' + patient + 'を' + past + '。'
    entry = kw.get('entry', 'read'); w3b2 = kw.get('w3b2', 'READ')
    add(D, text, C(verb, {'agent': agent, 'patient': patient, 'time': time}), 'S4', None, kw.get('cons', 'time:連体詞+名詞+、(D1)'), entry, w3b2,
        kw.get('note', '指示詞(この・その・あの)の直後の時の語。指示詞は値から外し、role_flags に写す(D1)。'), [mn('time', det + time), mn('place', time)],
        terms=[agent, time, patient, verb])


# D1: the part is a time noun (a direct TIME with an arm that is not only a role distribution) after この・その and before 、
for agent, det, time, patient, verb, past in [
        ('母', 'この', '休日', '本', '読む', '読んだ'), ('兄', 'その', '昼', '手紙', '書く', '書いた'),
        ('先生', 'この', '平日', '皿', '洗う', '洗った'), ('弟', 'その', '年末', '靴', '磨く', '磨いた'),
        ('父', 'この', '月末', '手紙', '書く', '書いた'), ('生徒', 'その', '誕生日', '本', '読む', '読んだ'),
        ('祖母', 'この', '春休み', '絵', '描く', '描いた'), ('店員', 'その', '年明け', '靴', '磨く', '磨いた'),
        ('兄', 'この', '昼', '皿', '洗う', '洗った'), ('姉', 'その', '冬', '本', '読む', '読んだ'),
        ('弟', 'この', '大晦日', '靴', '磨く', '磨いた'), ('妹', 'その', '放課後', '窓', '拭く', '拭いた'),
        ('学生', 'この', '休日', '窓', '拭く', '拭いた'), ('祖父', 'その', '夜', '皿', '洗う', '洗った'), ('姉', 'この', '冬', '絵', '描く', '描いた'),
        ('母', 'その', '平日', '本', '読む', '読んだ')]:
    d1(agent, det, time, patient, verb, past)
# abstain: あの is cut by the tagger as an interjection (感動詞), never a 連体詞: it is not one of the demonstratives (K97), so the part is not isolated
for agent, time, patient, verb, past in [('姉', '冬', '絵', '描く', '描いた'), ('妹', '放課後', '窓', '拭く', '拭いた'), ('祖父', '大晦日', '皿', '洗う', '洗った'),
                                         ('学生', '休日', '窓', '拭く', '拭いた'), ('母', '平日', '手紙', '書く', '書いた')]:
    d1(agent, 'あの', time, patient, verb, past, entry='abstain', w3b2='PLACEMENT_PART_NOT_ISOLATED', cons='time:感動詞(あの)+名詞+、',
       note='あの はタガーが感動詞(フィラー)と切る。連体詞でないので指示詞の 3 語の条件に当たらず、部分の直前の語は孤立の条件を満たさない(K63)。')


def d2_place(agent, det, place, verb, **kw):
    text = agent + 'が' + det + place + 'で' + PAST[verb] + '。'
    add(D, text, C(verb, {'agent': agent, 'place': place}), 'S4', None, kw.get('cons', 'place:で + 連体詞(D2)'), kw.get('entry', 'read'), kw.get('w3b2', 'READ'),
        kw.get('note', '読解器は place と読み、指示詞が区間の外に残って unrepresented source content と言う。指示詞は値から外し、role_flags に写す(D2)。'),
        [mn('place', det + place), mn('instrument', place)], terms=[agent, place, verb])


# D2: a place the reader knows (place|means is not ambiguous), PLACE direct with an arm that is not only a role distribution
for agent, det, place, verb in [('母', 'この', '部屋', '休む'), ('兄', 'その', '公園', '遊ぶ'), ('弟', 'この', '工場', '働く'), ('妹', 'その', '庭', '遊ぶ'),
                                ('祖父', 'この', '山', '歩く'), ('祖母', 'その', '島', '休む'), ('生徒', 'この', '広場', '遊ぶ'), ('学生', 'その', '体育館', '走る'),
                                ('父', 'その', '台所', '働く'), ('先生', 'この', '港', '歩く'), ('姉', 'その', '病院', '働く'), ('店員', 'この', '美術館', '働く'),
                                ('兄', 'この', '博物館', '歩く'), ('母', 'その', '動物園', '歩く'), ('弟', 'この', '劇場', '働く')]:
    d2_place(agent, det, place, verb)
# abstain: あの is cut as an interjection: the reader's role has an interjection before its phrase, and no demonstrative stands before any role
for agent, place, verb in [('姉', '病院', '働く'), ('父', '台所', '働く'), ('先生', '港', '歩く'), ('店員', '美術館', '働く')]:
    d2_place(agent, 'あの', place, verb, entry='abstain', w3b2='PLACEMENT_PART_NONE', cons='place:で + 感動詞(あの)',
             note='あの はタガーが感動詞と切る。連体詞でないので指示詞の 3 語の条件に当たらず、D2 に当たらない(K97)。')


def d2_time(agent, det, time, patient, verb, past, **kw):
    text = agent + 'が' + det + time + 'に' + patient + 'を' + past + '。'
    add(D, text, C(verb, {'agent': agent, 'patient': patient, 'time': time}), 'S4', None, kw.get('cons', 'time:に + 連体詞(D2)'), kw.get('entry', 'read'), kw.get('w3b2', 'READ'),
        '読解器は time と読み、指示詞が区間の外に残る。指示詞は値から外し、role_flags に写す(D2)。', [mn('time', det + time), mn('place', time)], terms=[agent, time, patient, verb])


# (only 夜 and 昼: they are what the reader's own time test takes for `time` before に; 朝 is the same and is UNPLACED)
for agent, det, time, patient, verb, past in [('兄', 'その', '夜', '手紙', '書く', '書いた'), ('姉', 'この', '昼', '皿', '洗う', '洗った'),
                                              ('弟', 'その', '夜', '靴', '磨く', '磨いた'), ('先生', 'この', '昼', '絵', '描く', '描いた'),
                                              ('父', 'その', '夜', '窓', '拭く', '拭いた'), ('母', 'この', '夜', '本', '読む', '読んだ')]:
    d2_time(agent, det, time, patient, verb, past)
d2_time('姉', 'あの', '昼', '皿', '洗う', '洗った', entry='abstain', w3b2='PLACEMENT_PART_NONE', cons='time:に + 感動詞(あの)')

# abstain: どの (a question) before the part / the place
for agent, time, patient, verb, past in [('兄', '夜', '手紙', '書く', '書いた'), ('母', '冬', '本', '読む', '読んだ'), ('姉', '昼', '皿', '洗う', '洗った')]:
    text = agent + 'がどの' + time + '、' + patient + 'を' + past + '。'
    add(D, text, C(verb, {'agent': agent, 'patient': patient, 'time': time}), 'S4', None, 'time:どの+名詞(疑問。指示詞でない)', 'abstain', 'PLACEMENT_PART_NOT_ISOLATED',
        'どの は疑問で、指示詞の 3 語に入らない。部分の直前の連体詞は孤立の条件を満たさない(K63)。', [mn('time', 'どの' + time)], terms=[agent, time, patient, verb])
for agent, place, verb in [('母', '部屋', '歌う'), ('兄', '公園', '遊ぶ'), ('姉', '庭', '遊ぶ')]:
    text = agent + 'がどの' + place + 'で' + PAST[verb] + '。'
    add(D, text, C(verb, {'agent': agent, 'place': place}), 'S4', None, 'place:どの+名詞(疑問。指示詞でない)', 'abstain', 'PLACEMENT_PART_NONE',
        'どの は疑問で、指示詞の 3 語に入らない。指示詞の前にある役割が無いので D2 に当たらない。', [mn('place', 'どの' + place)], terms=[agent, place, verb])
# abstain: あの that the tagger cuts as an interjection (not a 連体詞)
for agent, patient, verb, past in [('兄', '窓', '拭く', '拭いた'), ('母', '本', '読む', '読んだ')]:
    text = 'あの' + agent + 'が' + patient + 'を' + past + '。'
    add(D, text, C(verb, {'agent': agent, 'patient': patient}), 'S4', None, '感動詞と切られる あの', 'abstain', 'PLACEMENT_',
        'あの をタガーが感動詞(フィラー)と切る。連体詞でないので指示詞として扱わない。読解器がこの文をどの理由で棄権するかは予測しない(引き金に当たらないか、S4 で部分が無いか)ので、期待は型付きの理由(PLACEMENT_)であること。', [mn('agent', 'あの' + agent)], terms=[agent, patient, verb])
# abstain: the role before which the demonstrative stands has no place in the type table (means / source: the table of the convention has no type for them)
for agent, det, noun, verb in [('兄', 'その', '車', '走る'), ('母', 'この', '電車', '歩く'), ('姉', 'その', '自転車', '走る'), ('弟', 'その', '船', '動く')]:
    text = agent + 'が' + det + noun + 'で' + PAST[verb] + '。'
    add(D, text, C(verb, {'agent': agent, 'instrument': noun}), 'S4', None, 'means:で + 連体詞(型の表に無い役割)', 'abstain', 'PLACEMENT_DETERMINER_ROLE_UNTYPED',
        '読解器は means と読み、規約では instrument。instrument は十字の型の表に無いので、指示詞の印を付けて読まない。', [mn('place', noun)], terms=[agent, noun, verb])
for agent, det, noun, verb in [('兄', 'その', '駅', '走る'), ('母', 'この', '町', '歩く'), ('姉', 'この', '山', '走る'), ('弟', 'その', '工場', '歩く')]:
    text = agent + 'が' + det + noun + 'から' + PAST[verb] + '。'
    add(D, text, C(verb, {'agent': agent, 'source': noun}), 'S4', None, 'source:から + 連体詞(型の表に無い役割)', 'abstain', 'PLACEMENT_DETERMINER_ROLE_UNTYPED',
        'から の句は source。source は十字の型の表に無いので、指示詞の印を付けて読まない。', [mn('place', noun)], terms=[agent, noun, verb])
# abstain: the place after the demonstrative is not a PLACE (GROUP_ORG), or split, or only the role distribution decides it
for agent, det, noun, verb, why in [('母', 'その', '学校', '歌う', 'PLACEMENT_TYPE_MISMATCH'), ('兄', 'この', '会社', '働く', 'PLACEMENT_TYPE_MISMATCH'),
                                    ('姉', 'その', '図書館', '歌う', 'PLACEMENT_MULTIPLE'), ('弟', 'この', '研究所', '働く', 'PLACEMENT_MULTIPLE'),
                                    ('父', 'その', '家', '休む', 'PLACEMENT_MULTIPLE')]:
    d2_place(agent, det, noun, verb, entry='abstain', w3b2=why, cons='place:で + 連体詞(型が合わない)',
             note='指示詞の前の役割の値の型が、時・場所の期待(PLACE)に入らない、または全候補が入らない。')
for agent, det, noun, verb in [('母', 'その', '教室', '歌う'), ('兄', 'この', '店', '働く'), ('姉', 'この', '海', '泳ぐ'), ('弟', 'その', '倉庫', '働く')]:
    d2_place(agent, det, noun, verb, entry='abstain', w3b2='PLACEMENT_SLOT_EVIDENCE_ONLY', cons='place:で + 連体詞(役割の分布の腕だけ)',
             note='場所の型が、役割の分布の腕だけで決まっている(付加の門 5)。')
# abstain: a time after the demonstrative that the placement does not place (UNPLACED)
for agent, det, time, patient, verb, past in [('弟', 'その', '朝', '靴', '磨く', '磨いた'), ('母', 'この', '朝', '本', '読む', '読んだ')]:
    d2_time(agent, det, time, patient, verb, past, entry='abstain', w3b2='PLACEMENT_UNPLACED', cons='time:に + 連体詞(型の証拠が足りない)')

# ===================================================================================================================================
# w3b2_no.jsonl: X の Y: the value is the whole phrase; the type is asked of the head Y
# ===================================================================================================================================
N = 'no'


def goal_no(agent, owner, head, verb, **kw):
    value = owner + 'の' + head
    text = agent + 'が' + value + 'へ' + PAST[verb] + '。'
    add(N, text, C(verb, {'agent': agent, 'goal': value}), 'U', 'P_MOVE', kw.get('cons', 'goal:へ:の(主辞 PLACE)'), kw.get('entry', 'read'), kw.get('w3b2', 'READ'),
        kw.get('note', 'へ の句が X の Y。値は句全体で、型は主辞 Y に問う(K96)。' + NOTE_MOVE), [mn('recipient', value), mn('goal', head), mn('place', value)],
        terms=[agent, head, verb])


# read: the head is a PLACE (direct) and not a relational noun
for agent, owner, head, verb in [('兄', '祖父', '畑', '走る'), ('母', '先生', '庭', '歩く'), ('姉', '叔父', '村', '歩く'), ('弟', '隣人', '港', '走る'),
                                 ('妹', '友人', '橋', '歩く'), ('父', '祖母', '寺', '歩く'), ('祖父', '母', '台所', '歩く'), ('先生', '生徒', '玄関', '走る'),
                                 ('店員', '店長', '倉庫', '走る'), ('兄', '町', '広場', '走る'), ('姉', '学校', '工場', '歩く'), ('弟', '会社', '屋上', '走る')]:
    goal_no(agent, owner, head, verb)
# read: the head is a relational noun of the tagger's 一般 (隣・横・方): the type is the placement's answer for the head (PLACE)
for agent, owner, head, verb in [('兄', '友人', '隣', '走る'), ('姉', '祖父', '横', '歩く'), ('母', '先生', '方', '歩く')]:
    goal_no(agent, owner, head, verb, cons='goal:へ:の(主辞 PLACE。関係名詞だが pos3 は 一般)')
# read: the agent is X の Y
for agent, owner, head, verb, place in [('弟', '友人', '弟', '走る', '庭'), ('妹', '先生', '妹', '歩く', '森'), ('息子', '隣人', '息子', '走る', '港'), ('兄', '祖父', '兄', '歩く', '島')]:
    value = owner + 'の' + head
    text = value + 'が' + place + 'へ' + PAST[verb] + '。'
    add(N, text, C(verb, {'agent': value, 'goal': place}), 'U', 'P_MOVE', 'agent:が:の(主辞 PERSON) + goal:へ:PLACE', 'read', 'READ',
        'agent が X の Y。値は句全体で、型は主辞 Y に問う(K96)。' + NOTE_MOVE, [mn('agent', head), mn('recipient', place)], terms=[head, place, verb])
# read: U3 で X の Y (the reader's place test looks at the head Y, which it does not know)
for agent, owner, head, verb in [('兄', '学校', '校庭', '走る'), ('弟', '町', '神社', '歩く'), ('姉', '村', '川', '歩く'), ('母', '山', '森林', '歩く'),
                                 ('祖父', '駅', '歩道', '歩く'), ('祖母', '会社', 'マンション', '名乗る'), ('父', '市', 'アパート', '断る'), ('先生', '島', 'ホテル', '願う')]:
    value = owner + 'の' + head
    text = agent + 'が' + value + 'で' + PAST[verb] + '。'
    add(N, text, C(verb, {'agent': agent, 'place': value}), 'U3', PTYPE[verb], 'place:で:の(主辞 PLACE)', 'read', 'READ',
        'で の句が X の Y。読解器は主辞 Y を知らず で を曖昧と言う(U3)。値は句全体、型は主辞 Y に問う(K96)。', [mn('instrument', value), mn('place', head)], terms=[agent, head, verb])
# read: U3 patient X の Y (head PERSON / ANIMAL / the split ABSTRACT+PERSON of 友人: every candidate is in the table's patient set)
for agent, place, owner, head, verb in [('兄', '校庭', '弟', '犬', '呼ぶ'), ('姉', '神社', '友人', '弟', '誘う'), ('母', '校舎', '兄', '友人', '呼ぶ'), ('先生', '国道', '祖母', '猫', '呼ぶ')]:
    value = owner + 'の' + head
    text = agent + 'が' + place + 'で' + value + 'を' + PAST[verb] + '。'
    add(N, text, C(verb, {'agent': agent, 'place': place, 'patient': value}), 'U3', PTYPE[verb], 'place:で:PLACE + patient:を:の(主辞)', 'read', 'READ',
        'を の句が X の Y。値は句全体、型は主辞 Y に問う(K96)。' + NOTE_U3, [mn('recipient', value), mn('instrument', place)], terms=[agent, place, head, verb])
# read: S4, 、 after X の Y where Y is a time noun that is not 副詞可能 (the part is merged: X の Y)
for agent, owner, head, patient, verb, past in [('兄', '去年', '大晦日', '窓', '拭く', '拭いた'), ('姉', '学校', '春休み', '本', '読む', '読んだ'), ('母', '町', '祝日', '皿', '洗う', '洗った'),
                                                ('弟', '去年', '年明け', '手紙', '書く', '書いた')]:
    value = owner + 'の' + head
    text = agent + 'が' + value + '、' + patient + 'を' + past + '。'
    add(N, text, C(verb, {'agent': agent, 'patient': patient, 'time': value}), 'S4', None, 'time:の+名詞+、(主辞 TIME)', 'read', 'READ',
        '覆われない内容語の連なり 2 つが の を挟んで続く。1 つの部分にまとめ、主辞 Y(pos3 が 一般)の型で時として読む(K96)。', [mn('time', head), mn('place', value)],
        terms=[agent, head, patient, verb])

# abstain: the head is a relational noun of the tagger (副詞可能)
for agent, owner, head, verb in [('兄', '友人', '前', '走る'), ('姉', '祖父', '後', '歩く'), ('猫', '庭', '中', '走る'), ('犬', '森', '中', '走る'), ('鳥', '山', '上', '飛ぶ'),
                                 ('馬', '橋', '上', '走る')]:
    goal_no(agent, owner, head, verb, entry='abstain', w3b2='PLACEMENT_HEAD_RELATIONAL', cons='goal:へ:の(主辞 副詞可能)',
            note='主辞が関係・時を表す名詞(pos3 が 副詞可能)。句の型を主辞が決めない(K96)。' + NOTE_MOVE)
for agent, owner, head, verb in [('兄', '校庭', '前', '走る'), ('母', '神社', '前', '歩く')]:
    value = owner + 'の' + head
    text = agent + 'が' + value + 'で' + PAST[verb] + '。'
    add(N, text, C(verb, {'agent': agent, 'place': value}), 'U3', PTYPE[verb], 'place:で:の(主辞 副詞可能)', 'abstain', 'PLACEMENT_HEAD_RELATIONAL',
        '主辞が関係・時を表す名詞(pos3 が 副詞可能)。句の型を主辞が決めない(K96)。', [mn('instrument', value)], terms=[agent, owner, verb])
for agent, season, head, patient, verb, past in [('兄', '夏', '夕方', '窓', '拭く', '拭いた'), ('姉', '春', '夜', '手紙', '書く', '書いた'), ('母', '冬', '休日', '靴', '磨く', '磨いた'),
                                                 ('弟', '秋', '平日', '本', '読む', '読んだ')]:
    value = season + 'の' + head
    text = agent + 'が' + value + '、' + patient + 'を' + past + '。'
    add(N, text, C(verb, {'agent': agent, 'patient': patient, 'time': value}), 'S4', None, 'time:の+名詞+、(主辞 副詞可能)', 'abstain', 'PLACEMENT_HEAD_RELATIONAL',
        '主辞が時を表す名詞(pos3 が 副詞可能)。1 つの部分にまとめても句の型を主辞が決めない(K96)。', [mn('time', head), mn('place', value)], terms=[agent, head, patient, verb])
# abstain: the head is a word the placement does not place / splits / types otherwise / only the role distribution decides
for agent, owner, head, verb, why in [('兄', '友人', '窪地', '走る', 'PLACEMENT_UNPLACED'), ('姉', '祖父', '洲', '歩く', 'PLACEMENT_UNPLACED'),
                                      ('兄', '祖父', '家', '走る', 'PLACEMENT_MULTIPLE'), ('母', '先生', '図書館', '歩く', 'PLACEMENT_MULTIPLE'), ('弟', '友人', '谷', '歩く', 'PLACEMENT_MULTIPLE'),
                                      ('兄', '祖父', '学校', '走る', 'PLACEMENT_TYPE_MISMATCH'), ('姉', '友人', '会社', '歩く', 'PLACEMENT_TYPE_MISMATCH')]:
    goal_no(agent, owner, head, verb, entry='abstain', w3b2=why, cons='goal:へ:の(主辞が PLACE でない・決まらない)',
            note='主辞の語の型が PLACE でない、割れる、または決まらない。' + NOTE_MOVE)
for agent, owner, head, verb in [('兄', '学校', '廊下', '走る'), ('弟', '町', '路地', '走る'), ('姉', '神社', '縁側', '歩く')]:
    value = owner + 'の' + head
    text = agent + 'が' + value + 'で' + PAST[verb] + '。'
    add(N, text, C(verb, {'agent': agent, 'place': value}), 'U3', PTYPE[verb], 'place:で:の(主辞が役割の分布の腕だけ)', 'abstain', 'PLACEMENT_SLOT_EVIDENCE_ONLY',
        '主辞の語の型が、役割の分布の腕だけで決まっている(付加の門 5)。', [mn('instrument', value)], terms=[agent, head, verb])
text = '母が町の長屋で名乗った。'
add(N, text, C('名乗る', {'agent': '母', 'place': '町の長屋'}), 'U3', 'P_COMMUNICATE', 'place:で:の(主辞が生成した定義で direct)', 'abstain', 'PLACEMENT_DIRECT_VIA_GENERATED',
    '主辞の語は生成した定義で direct に格上げされた型。', [mn('instrument', '町の長屋')], terms=['母', '長屋', '名乗る'])
# abstain: a patient or an agent X の Y whose head is split with an outlier
for agent, place, owner, head, verb in [('兄', '校庭', '友人', '挨拶', '断る'), ('姉', '神社', '先生', '日程', '断る')]:
    value = owner + 'の' + head
    text = agent + 'が' + place + 'で' + value + 'を' + PAST[verb] + '。'
    add(N, text, C(verb, {'agent': agent, 'place': place, 'patient': value}), 'U3', PTYPE[verb], 'patient:を:の(主辞が割れて外れがある)', 'abstain', 'PLACEMENT_MULTIPLE',
        '主辞の語の型が割れ、候補の 1 つが表の patient の集合の外。', [mn('recipient', value)], terms=[agent, place, head, verb])
for owner, head, place, verb in [('友人', '客', '庭', '走る'), ('先生', '夫婦', '森', '歩く')]:
    value = owner + 'の' + head
    text = value + 'が' + place + 'へ' + PAST[verb] + '。'
    add(N, text, C(verb, {'agent': value, 'goal': place}), 'U', 'P_MOVE', 'agent:が:の(主辞が割れて外れがある)', 'abstain', 'PLACEMENT_MULTIPLE',
        '主辞の語の型が割れ、候補の 1 つが agent の期待の外。' + NOTE_MOVE, [mn('agent', head)], terms=[head, place, verb])


# ===================================================================================================================================
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out-dir', default=str(HERE))
    a = ap.parse_args()
    out = Path(a.out_dir)
    ids = set()
    for name, rows in ROWS.items():
        (out / ('w3b2_%s.jsonl' % name)).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
        for r in rows:
            assert r['id'] not in ids; ids.add(r['id'])
    texts = [r['input'] for rows in ROWS.values() for r in rows]
    assert len(texts) == len(set(texts)), 'duplicate input inside the new data: %s' % sorted({t for t in texts if texts.count(t) > 1})
    (out / 'w3b2_data_terms.json').write_text(json.dumps(sorted(TERMS), ensure_ascii=False, indent=0) + '\n', encoding='utf-8')
    for name, rows in ROWS.items():
        print(name, len(rows), 'read', sum(1 for r in rows if r['entry_expect'] == 'read'), 'abstain', sum(1 for r in rows if r['entry_expect'] == 'abstain'))


if __name__ == '__main__':
    main()
