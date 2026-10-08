#!/usr/bin/env python3
"""W1-a5 step 4: writes tests/reading_soundness/ja_r12.jsonl (the data of the ticket W1-a5; K217 of docs/READING_SOUNDNESS.md section 10G).
The expectations below were written BEFORE any code of W1-a5 existed, from the convention (docs/READING_CONVENTIONS.md 3, 4.3, 5, 6) and from the facts of the BASE entry only
(`reader_facts.py` run in the tree of df4f001: `reader_facts_prefreeze.tsv`). They are frozen with `bank_freeze.sha256`; this script is kept as the record of how the file was made.

Row: id, lang, category (aspect|quantity|adverb), behavior (read|abstain), input, text, expect (the convention's answer: `readable: false` for a sentence the entry must NOT read), entry_expect (read|abstain),
w1a5_expect ({path, reason_prefix, quantifiers, flags}; a null field is not checked; for a read row `quantifiers` / `flags` are always written, {} meaning "none"), construction, note.
Usage: cd <tree> && python artifacts/w1-a5/tools/mk_data_w1a5.py [--out FILE]"""
import argparse
import json
from pathlib import Path

TREE = Path(__file__).resolve().parents[3]
ROWS = []


def clause(pred, roles, pol='+', tense='past', quant=None):
    c = {'predicate': pred, 'roles': roles, 'polarity': pol, 'tense': tense, 'modality': None, 'voice': 'active'}
    if quant: c['quantifiers'] = quant
    return c


def w5(path, reason=None, quant=None, flags=None):
    return {'path': path, 'reason_prefix': reason, 'quantifiers': quant, 'flags': flags}


def read(rid, cat, text, cl, must_not, path, construction, note='', quant=None, flags=None):
    ROWS.append({'id': rid, 'lang': 'ja', 'category': cat, 'behavior': 'read', 'input': text, 'text': text,
                 'expect': {'readable': True, 'clauses': [cl], 'relations': [], 'must_not': must_not},
                 'entry_expect': 'read', 'w1a5_expect': w5(path, None, {} if quant is None else quant, {} if flags is None else flags),
                 'construction': construction, 'note': note})


def abstain(rid, cat, text, construction, path=None, reason=None, note=''):
    ROWS.append({'id': rid, 'lang': 'ja', 'category': cat, 'behavior': 'abstain', 'input': text, 'text': text,
                 'expect': {'readable': False, 'clauses': [], 'relations': [], 'must_not': []},
                 'entry_expect': 'abstain', 'w1a5_expect': w5(path, reason), 'construction': construction, 'note': note})


def pol_not(p): return {'clause': 0, 'field': 'polarity', 'value': p}
def tense_not(t): return {'clause': 0, 'field': 'tense', 'value': t}
def quant_not(k, v): return {'clause': 0, 'quantifier': k, 'value': v}
def role_not(r, v): return {'clause': 0, 'role': r, 'value': v}


# ------------------------------------------------------------------------------------------------ aspect: read (20)
BP = {'agent': '兄', 'patient': '本'}
def asp_read(n, text, cl, path, construction, note='', flags=None):
    read('W1A5-ASP-R-%03d' % n, 'aspect', text, cl, [pol_not('-' if cl['polarity'] == '+' else '+'), tense_not('nonpast' if cl['tense'] == 'past' else 'past')], path, construction, note, flags=flags)

asp_read(1, '兄が本を読んでいる。', clause('読む', BP, '+', 'nonpast'), 'aspect_kept', 'ている: 肯定・現在', 'the base reads it right')
asp_read(2, '兄が本を読んでいた。', clause('読む', BP, '+', 'past'), 'aspect_kept', 'ていた: 肯定・過去')
asp_read(3, '兄が本を読んでいます。', clause('読む', BP, '+', 'nonpast'), 'aspect_kept', 'ています: 肯定・現在')
asp_read(4, '兄が本を読んでいました。', clause('読む', BP, '+', 'past'), 'aspect_kept', 'ていました: 肯定・過去')
asp_read(5, '兄が本を読んでしまった。', clause('読む', BP, '+', 'past'), 'aspect_kept', 'てしまった: 本動詞の時制')
asp_read(6, '兄が本を読んでおいた。', clause('読む', BP, '+', 'past'), 'aspect_kept', 'ておいた: 本動詞の時制')
asp_read(7, '兄が本を読んでおきました。', clause('読む', BP, '+', 'past'), 'aspect_kept', 'ておきました: 本動詞の時制')
asp_read(8, '母が部屋を掃除している。', clause('掃除する', {'agent': '母', 'patient': '部屋'}, '+', 'nonpast'), 'aspect_kept', 'サ変＋ている')
asp_read(9, '父が会社へ行っていない。', clause('行く', {'agent': '父', 'goal': '会社'}, '-', 'nonpast'), 'aspect_kept', 'へ の句＋ていない（基点の節の極性は 読解器が - と出す文）')
asp_read(10, '兄が本を読んでいない。', clause('読む', BP, '-', 'nonpast'), 'aspect_corrected', 'ていない: 否定・現在（基点は + と誤読する）')
asp_read(11, '兄が本を読んでいなかった。', clause('読む', BP, '-', 'past'), 'aspect_corrected', 'ていなかった: 否定・過去（基点は + と誤読する）')
asp_read(12, '兄が本を読んでいません。', clause('読む', BP, '-', 'nonpast'), 'aspect_corrected', 'ていません: 否定・現在（基点は + と誤読する）')
asp_read(13, '兄が本を読んでいませんでした。', clause('読む', BP, '-', 'past'), 'aspect_corrected', 'ていませんでした: 否定・過去（基点は + と誤読する）')
asp_read(14, '兄が本を読んでしまわなかった。', clause('読む', BP, '-', 'past'), 'aspect_corrected', 'てしまわなかった: 否定・過去（基点は + と誤読する）')
asp_read(15, '兄が本を読んでおかなかった。', clause('読む', BP, '-', 'past'), 'aspect_corrected', 'ておかなかった: 否定・過去（基点は + と誤読する）')
asp_read(16, '弟が庭で遊んでいなかった。', clause('遊ぶ', {'agent': '弟', 'place': '庭'}, '-', 'past'), 'aspect_corrected', 'で の句＋ていなかった（基点は + と誤読する）')
asp_read(17, '兄がゆっくり本を読んでいる。', clause('読む', BP, '+', 'nonpast'), 'reread', '副詞＋ている（基点は棄権: 副詞が覆われない）', flags={'adverbs': ['ゆっくり']})
asp_read(18, '兄がそっと窓を開けていた。', clause('開ける', {'agent': '兄', 'patient': '窓'}, '+', 'past'), 'reread', '副詞＋ていた', flags={'adverbs': ['そっと']})
asp_read(19, '兄が本をゆっくり読んでいる。', clause('読む', BP, '+', 'nonpast'), 'reread', '目的語の後の副詞＋ている', flags={'adverbs': ['ゆっくり']})
asp_read(20, '母がゆっくり部屋を掃除している。', clause('掃除する', {'agent': '母', 'patient': '部屋'}, '+', 'nonpast'), 'reread', 'サ変＋副詞＋ている', flags={'adverbs': ['ゆっくり']})

# ------------------------------------------------------------------------------------------------ aspect: abstain (20)
asp_abs = [
    ('兄が本を読んでみた。', 'てみる（規約 9.1 未決）', 'aspect_refused', 'ASPECT_NOT_IN_CONVENTION'),
    ('兄が本を読んでみる。', 'てみる（規約 9.1 未決）', 'aspect_refused', 'ASPECT_NOT_IN_CONVENTION'),
    ('母が窓を開けてある。', 'てある（規約 3 の列挙に無い・9.1 未決）', 'aspect_refused', 'ASPECT_NOT_IN_CONVENTION'),
    ('兄が本を読んでおいてある。', 'ておいてある（連鎖）', 'aspect_refused', 'ASPECT_'),
    ('兄が本を読んでしまっている。', 'てしまっている（連鎖）', 'aspect_refused', 'ASPECT_CHAIN_NOT_READ'),
    ('兄が本を読んでいたら、母が笑った。', 'ていたら（条件・2 節）', 'not_triggered', None),
    ('兄が走っていった。', 'ていく（9.1 未決）', 'not_triggered', None),
    ('兄が帰ってきた。', 'てくる（9.1 未決）', 'not_triggered', None),
    ('兄が本を読んでない。', 'てない（縮約の否定）', 'not_triggered', None),
    ('兄が本を読んでいく。', 'ていく（9.1 未決）', 'not_triggered', None),
    ('兄が本を読んでいなくはない。', 'ていなくはない（二重否定）', 'not_triggered', None),
    ('兄が本を読んでいないわけではない。', 'ていないわけではない（二重否定）', 'not_triggered', None),
    ('兄が本を読んでいたい。', 'ていたい（願望）', 'not_triggered', None),
    ('兄が本を読んでいるだろう。', 'ているだろう（推量）', 'not_triggered', None),
    ('兄が本を読んでいろ。', 'ていろ（命令形。基点は + の平叙として読む）', 'aspect_refused', 'ASPECT_ENDING_NOT_READ'),
    ('兄が本を読んでいなければならない。', 'ていなければならない（義務・2 述語）', 'not_triggered', None),
    ('兄が本を読んでいないので、母が怒った。', '2 節の文の ていない', 'not_triggered', None),
    ('兄がまだ本を読んでいない。', 'まだ＋ていない（K64 time_aspect）', 'reread_refused', 'ADVERB_MARK_NOT_READ:time_aspect:まだ'),
    ('兄はもう本を読んでいない。', 'もう＋ていない（K64 time_aspect）', 'reread_refused', 'ADVERB_MARK_NOT_READ:time_aspect:もう'),
    ('兄が本を読んじゃわなかった。', '縮約形の否定（基点は - と読む。規約 3 の字面に無い縮約形の後ろの否定）', 'aspect_refused', 'ASPECT_CONTRACTED_NEGATION'),
]
for i, (t, c, p, r) in enumerate(asp_abs, 1): abstain('W1A5-ASP-A-%03d' % i, 'aspect', t, c, p, r)

# ------------------------------------------------------------------------------------------------ quantity: read (22)
def qty_read(n, text, cl, construction, note=''):
    q = cl['quantifiers']; (k, v), = q.items()
    wrong_key = 'patient' if k != 'patient' else 'agent'
    mn = [quant_not(wrong_key, v), {'clause': 0, 'quantifier': k, 'value': ['at_least:' + v.split(':')[1], 'approx:' + v.split(':')[1]]}]
    read('W1A5-QTY-R-%03d' % n, 'quantity', text, cl, mn, 'reread', construction, note, quant=q)

qty_read(1, '兄が本を三冊読んだ。', clause('読む', BP, quant={'patient': 'exactly:3'}), 'を＋冊（接尾辞）')
qty_read(2, '母がりんごを五個買った。', clause('買う', {'agent': '母', 'patient': 'りんご'}, quant={'patient': 'exactly:5'}), 'を＋個', '読解器は gold_quantity の節も作る（整合する）')
qty_read(3, '姉が切手を二枚買った。', clause('買う', {'agent': '姉', 'patient': '切手'}, quant={'patient': 'exactly:2'}), 'を＋枚')
qty_read(4, '弟が犬を二匹飼った。', clause('飼う', {'agent': '弟', 'patient': '犬'}, quant={'patient': 'exactly:2'}), 'を＋匹')
qty_read(5, '兄が手紙を三通書いた。', clause('書く', {'agent': '兄', 'patient': '手紙'}, quant={'patient': 'exactly:3'}), 'を＋通')
qty_read(6, '兄が牛を十頭育てた。', clause('育てる', {'agent': '兄', 'patient': '牛'}, quant={'patient': 'exactly:10'}), 'を＋頭・漢数字の 十')
qty_read(7, '兄が本を三十五冊読んだ。', clause('読む', BP, quant={'patient': 'exactly:35'}), '漢数字の位取り（三十五）')
qty_read(8, '兄が本を百二十冊集めた。', clause('集める', BP, quant={'patient': 'exactly:120'}), '漢数字の位取り（百二十）')
qty_read(9, '母が卵を２個割った。', clause('割る', {'agent': '母', 'patient': '卵'}, quant={'patient': 'exactly:2'}), '全角の数字')
qty_read(10, '兄が本を3冊読んだ。', clause('読む', BP, quant={'patient': 'exactly:3'}), '半角の数字')
qty_read(11, '兄が本を二万冊集めた。', clause('集める', BP, quant={'patient': 'exactly:20000'}), '漢数字の位取り（二万）')
qty_read(12, '兄が本を千冊集めた。', clause('集める', BP, quant={'patient': 'exactly:1000'}), '漢数字の 千（前に数字が無い）')
qty_read(13, '学生が三人来た。', clause('来る', {'agent': '学生'}, quant={'agent': 'exactly:3'}), 'が＋人（主語の数量）')
qty_read(14, '子どもが五人遊んだ。', clause('遊ぶ', {'agent': '子ども'}, quant={'agent': 'exactly:5'}), 'が＋人（自動詞）')
qty_read(15, '学生が十人帰った。', clause('帰る', {'agent': '学生'}, quant={'agent': 'exactly:10'}), 'が＋人・漢数字の 十')
qty_read(16, '兄が本を三回読んだ。', clause('読む', BP, quant={'event': 'exactly:3'}), '回（を の後）→ event')
qty_read(17, '兄は駅に三回行った。', clause('行く', {'agent': '兄', 'goal': '駅'}, quant={'event': 'exactly:3'}), '回（に の後）→ event')
qty_read(18, '兄は京都に三度来た。', clause('来る', {'agent': '兄', 'goal': '京都'}, quant={'event': 'exactly:3'}), '度（に の後）→ event')
qty_read(19, '兄は駅に二度行った。', clause('行く', {'agent': '兄', 'goal': '駅'}, quant={'event': 'exactly:2'}), '度（に の後）→ event')
qty_read(20, '兄が三回走った。', clause('走る', {'agent': '兄'}, quant={'event': 'exactly:3'}), '回（が の後）→ event')
qty_read(21, '兄が手紙を五回書いた。', clause('書く', {'agent': '兄', 'patient': '手紙'}, quant={'event': 'exactly:5'}), '回（を の後）→ event')
qty_read(22, '兄が本を三冊読んでいる。', clause('読む', BP, '+', 'nonpast', quant={'patient': 'exactly:3'}), '数量＋ている')

# ------------------------------------------------------------------------------------------------ quantity: abstain (34)
Q = 'QUANTIFIER_TARGET_UNDETERMINED'
qty_abs = [
    ('兄が本を三日読んだ。', '期間（三日）', 'reread_refused', Q + ':time'),
    ('兄が三時間走った。', '期間（三時間）', 'reread_refused', Q + ':time'),
    ('兄が牛乳を二リットル飲んだ。', '名詞の助数詞（単位）', 'reread_refused', Q + ':unit'),
    ('兄が五キロ走った。', '名詞の助数詞（単位）', 'reread_refused', Q + ':unit'),
    ('兄が車を三台買った。', '名詞の助数詞（台）', 'reread_refused', Q + ':unit'),
    ('兄が水を三杯飲んだ。', '名詞の助数詞（杯）', 'reread_refused', Q + ':unit'),
    ('兄がりんごを弟に三個あげた。', 'に の後の数量（直前の句と数量のかかり先が割れる）', 'reread_refused', Q + ':particle'),
    ('りんごを兄が三個食べた。', 'かき混ぜ（を の句が が の句より前）', 'reread_refused', Q + ':scrambled'),
    ('兄は三冊読んだ。', 'は の後の数量（かかり先の句が無い）', 'not_triggered', None),
    ('兄が本を三冊も読んだ。', '三冊も（数量の直後が述語でない）', 'reread_refused', Q + ':position'),
    ('兄がりんごを三個ずつ食べた。', '三個ずつ（配分）', 'reread_refused', Q + ':position'),
    ('兄が本を三冊しか読まなかった。', '三冊しか（限定）', 'reread_refused', Q + ':position'),
    ('兄が本を三冊だけ読んだ。', '三冊だけ（限定）', 'reread_refused', Q + ':position'),
    ('兄が三人の学生に会った。', '三人の＋名詞（遊離していない）', 'not_triggered', None),
    ('兄が三度本を読んだ。', '数詞が役割の値に溶ける（三度本）', 'not_triggered', None),
    ('兄が温度を三度上げた。', 'を の後の 度（単位と割れる）', 'reread_refused', Q + ':unit'),
    ('気温が三度下がった。', 'が の後の 度（単位と割れる）', 'reread_refused', Q + ':unit'),
    ('兄が本を三回目に読んだ。', '三回目（序数）', 'reread_refused', Q + ':position'),
    ('兄が本を二、三冊読んだ。', '二、三冊（値が決まらない）', 'reread_refused', 'QUANTIFIER_VALUE_UNDETERMINED'),
    ('兄がりんごを数個食べた。', '数個（値が決まらない）', 'reread_refused', 'QUANTIFIER_VALUE_UNDETERMINED'),
    ('兄は本を一度も読まなかった。', '一度も…ない（否定の数量）', 'reread_refused', Q + ':position'),
    ('兄が本を三冊読まなかった。', '否定の中の数量（スコープが決まらない）', 'reread_refused', 'QUANTIFIER_SCOPE_UNDETERMINED:neg'),
    ('兄がゆっくり本を三冊読んだ。', '副詞と数量の同居', 'reread_refused', 'ADVERB_WITH_QUANTITY'),
    ('兄が三日月を見た。', '量化の語を含む複合語（三日月）', 'not_triggered', None),
    ('兄が一緒に走った。', '量化の語を含む複合語（一緒）', 'not_triggered', None),
    ('兄が本を三冊読みたい。', '願望の中の数量', 'reread_refused', 'REREAD_ABSTAINS'),
    ('弟が本を三冊読まれた。', '受身の中の数量', 'reread_refused', None),
    ('兄が弟に本を三冊読ませた。', '使役の中の数量', None, None),
    ('兄が三人と走った。', 'と の句の数量（割れる）', 'not_triggered', None),
    ('兄が三人で走った。', 'で の句の数量（割れる）', None, None),
    ('兄が本を三冊読めた。', '可能形の中の数量', 'reread_refused', None),
    ('兄が本を三十冊と五冊読んだ。', '数量が 2 つ', 'not_triggered', None),
    ('兄が三位に入った。', '序数（三位）', 'not_triggered', None),
    ('兄が本を三冊読んでいない。', 'ていない＋数量（否定の中の数量）', 'reread_refused', 'QUANTIFIER_SCOPE_UNDETERMINED:neg'),
]
for i, (t, c, p, r) in enumerate(qty_abs, 1): abstain('W1A5-QTY-A-%03d' % i, 'quantity', t, c, p, r)

# ------------------------------------------------------------------------------------------------ adverb: read (20)
def adv_read(n, text, cl, flag, construction, note=''):
    mn = [pol_not('-'), {'clause': 0, 'role': ['agent', 'patient', 'goal', 'place', 'time', 'instrument'], 'value': flag}]   # the adverb itself is no role
    read('W1A5-ADV-R-%03d' % n, 'adverb', text, cl, mn, 'reread', construction, note, flags={'adverbs': [flag]})

adv_read(1, '兄がゆっくり本を読んだ。', clause('読む', BP), 'ゆっくり', '様態の副詞（主語の後）')
adv_read(2, '兄がそっと窓を開けた。', clause('開ける', {'agent': '兄', 'patient': '窓'}), 'そっと', '様態の副詞（主語の後）')
adv_read(3, '兄がこっそり部屋に入った。', clause('入る', {'agent': '兄', 'goal': '部屋'}), 'こっそり', '様態の副詞＋に の句')
adv_read(4, '兄がわざと窓を割った。', clause('割る', {'agent': '兄', 'patient': '窓'}), 'わざと', '様態の副詞')
adv_read(5, '兄がすぐに帰った。', clause('帰る', {'agent': '兄'}), 'すぐ', 'すぐに（すぐ＋に の格助詞。印は副詞のトークンだけ）')
adv_read(6, '兄がすぐ走った。', clause('走る', {'agent': '兄'}), 'すぐ', '時の副詞（述語の直前）')
adv_read(7, '兄がじっと空を見た。', clause('見る', {'agent': '兄', 'patient': '空'}), 'じっと', '様態の副詞')
adv_read(8, '兄が本をゆっくり読んだ。', clause('読む', BP), 'ゆっくり', '目的語の後の副詞')
adv_read(9, '兄が窓をそっと開けた。', clause('開ける', {'agent': '兄', 'patient': '窓'}), 'そっと', '目的語の後の副詞')
adv_read(10, '兄がゆっくり走った。', clause('走る', {'agent': '兄'}), 'ゆっくり', '自動詞')
adv_read(11, '兄がゆっくり歩いた。', clause('歩く', {'agent': '兄'}), 'ゆっくり', '移動の動詞')
adv_read(12, '母がゆっくり掃除した。', clause('掃除する', {'agent': '母'}), 'ゆっくり', 'サ変')
adv_read(13, '母が部屋をゆっくり掃除した。', clause('掃除する', {'agent': '母', 'patient': '部屋'}), 'ゆっくり', 'サ変＋目的語の後の副詞')
adv_read(14, '母がすぐに部屋を掃除した。', clause('掃除する', {'agent': '母', 'patient': '部屋'}), 'すぐ', 'サ変＋すぐに')
adv_read(15, '弟がさっそく手紙を書いた。', clause('書く', {'agent': '弟', 'patient': '手紙'}), 'さっそく', '時の副詞')
adv_read(16, '姉がちゃんと本を読んだ。', clause('読む', {'agent': '姉', 'patient': '本'}), 'ちゃんと', '様態の副詞')
adv_read(17, '姉がしっかり手紙を書いた。', clause('書く', {'agent': '姉', 'patient': '手紙'}), 'しっかり', '様態の副詞')
adv_read(18, '姉がきちんと窓を閉めた。', clause('閉める', {'agent': '姉', 'patient': '窓'}), 'きちんと', '様態の副詞')
adv_read(19, '兄がすぐに会社へ行った。', clause('行く', {'agent': '兄', 'goal': '会社'}), 'すぐ', 'すぐに＋へ の句')
adv_read(20, '兄がそっと部屋に入った。', clause('入る', {'agent': '兄', 'goal': '部屋'}), 'そっと', '様態の副詞＋に の句')

# ------------------------------------------------------------------------------------------------ adverb: abstain (35)
M = 'ADVERB_MARK_NOT_READ'
adv_abs = [
    ('兄が急に走った。', '急に（名詞＋だ の連用形。品詞が副詞でない）', 'not_triggered', None),
    ('兄が静かに走った。', '静かに（形状詞＋に。品詞が副詞でない）', 'not_triggered', None),
    ('兄がすでに本を読んだ。', 'K64 time_aspect', 'reread_refused', M + ':time_aspect:すでに'),
    ('兄が全然本を読まなかった。', 'K64 neg', 'reread_refused', M + ':neg:全然'),
    ('兄がきっと本を読んだ。', 'K64 modal', 'reread_refused', M + ':modal:きっと'),
    ('兄がたぶん本を読んだ。', 'K64 modal', 'reread_refused', M + ':modal:たぶん'),
    ('兄が多分本を読んだ。', 'K64 modal の漢字表記（読みで照合）', 'reread_refused', M + ':modal:多分'),
    ('兄が恐らく本を読んだ。', 'K64 modal の漢字表記（読みで照合）', 'reread_refused', M + ':modal:恐らく'),
    ('兄がよく本を読んだ。', 'K64 quant', 'reread_refused', M + ':quant:よく'),
    ('兄がまた本を読んだ。', 'K64 conn', 'reread_refused', M + ':conn:また'),
    ('兄がゆっくり本を読まなかった。', '否定の焦点（副詞の範囲が決まらない）', 'reread_refused', 'ADVERB_SCOPE_UNDETERMINED:neg'),
    ('兄がゆっくり本を読みたい。', 'モダリティ（願望）の中の副詞', 'reread_refused', 'REREAD_ABSTAINS'),
    ('兄がゆっくり本を読むだろう。', 'モダリティ（推量）の中の副詞', 'not_triggered', None),
    ('兄がすぐ近くの店に行った。', '名詞句の修飾（すぐ近くの店）', 'reread_refused', 'ADVERB_MAY_MODIFY_NP:すぐ'),
    ('兄がすぐ隣の部屋に入った。', '名詞句の修飾（すぐ隣の部屋）', 'reread_refused', 'ADVERB_MAY_MODIFY_NP:すぐ'),
    ('兄がとても古い本を読んだ。', '名詞句の修飾（とても古い本）', 'reread_refused', 'ADVERB_MAY_MODIFY_NP:とても'),
    ('兄がゆっくり古い本を読んだ。', '名詞句の修飾になりうる形（形容詞が続く）', 'reread_refused', 'ADVERB_MAY_MODIFY_NP:ゆっくり'),
    ('兄が弟よりゆっくり走った。', '比較（より）', 'not_triggered', None),
    ('兄がゆっくりそっと窓を開けた。', '副詞の連続', 'reread_refused', 'ADVERB_STACKED'),
    ('兄がゆっくり、そして静かに窓を開けた。', '接続詞を挟む', 'not_triggered', None),
    ('兄が一番走った。', '規約 4.4 の最上級（一番）', 'reread_refused', M + ':convention:一番'),
    ('兄がちょうど本を読んだ。', '規約 6 の exactly（ちょうど）', 'reread_refused', M + ':convention:ちょうど'),
    ('兄がほぼ本を読んだ。', '近似の副詞（ほぼ）', 'reread_refused', M + ':approx:ほぼ'),
    ('兄があやうく本を落とした。', '近似・未遂（あやうく。タガーは形容詞と切る）', 'not_triggered', None),
    ('どうぞ本を読んでください。', '依頼の副詞（どうぞ）', None, None),
    ('兄がひょっとしたら本を読んだ。', 'ひょっとしたら（タガーは ひょっと＋し＋たら と切る）', 'not_triggered', None),
    ('兄がゆっくり三回読んだ。', '副詞と数量の同居', 'reread_refused', 'ADVERB_WITH_QUANTITY'),
    ('兄がそっとドアを開けて入った。', '述語が 2 つ', 'not_triggered', None),
    ('兄がもう走った。', 'K64 time_aspect', 'reread_refused', M + ':time_aspect:もう'),
    ('兄がずっと走った。', 'K64 time_aspect', 'reread_refused', M + ':time_aspect:ずっと'),
    ('兄が少し走った。', 'K64 quant', 'reread_refused', M + ':quant:少し'),
    ('兄が弟よりすぐ帰った。', '比較（より）', 'not_triggered', None),
    ('兄がゆっくり本を読んで、母が笑った。', '2 節', None, None),
    ('兄がもしかしたら本を読んだ。', 'もしかしたら（基点は疑問と読む）', 'not_triggered', None),
    ('兄がだいたい本を読んだ。', 'だいたい（タガーは名詞と切る。基点は たい を願望と読む）', 'not_triggered', None),
]
for i, (t, c, p, r) in enumerate(adv_abs, 1): abstain('W1A5-ADV-A-%03d' % i, 'adverb', t, c, p, r)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default=str(TREE / 'tests' / 'reading_soundness' / 'ja_r12.jsonl'))
    a = ap.parse_args()
    ids = [r['id'] for r in ROWS]; assert len(ids) == len(set(ids))
    texts = [r['input'] for r in ROWS]; assert len(texts) == len(set(texts)), [t for t in texts if texts.count(t) > 1]
    for r in ROWS:
        assert r['behavior'] != 'read' or r['expect']['must_not'], r['id']
    Path(a.out).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in ROWS), encoding='utf-8')
    import collections
    print('rows=%d' % len(ROWS), dict(collections.Counter((r['category'], r['behavior']) for r in ROWS)))


if __name__ == '__main__':
    main()
