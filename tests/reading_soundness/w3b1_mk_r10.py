#!/usr/bin/env python3
"""W3-b1 第 4 ラウンド(レビュー第 3 ラウンド M8): 検査データ ja_r10.jsonl を書く生成スクリプト。

このスクリプトは verantyx を import しない(読解器にも入口にも配置にも通さずに、期待を先に書いて凍結するため)。
目的: 新しい経路(U・S4)は、主辞の動詞が派生形(可能動詞・短い使役・自発・ら抜き)かもしれない節を読まない(docs K63 の「派生の疑いの門」、表の変更記録 3)。
その門を書く前に、可能動詞・短い使役・比べの文を、期待を先に書いて凍結する。
  - 経路 U の動詞(可能動詞・短い使役・下一段・五段・サ行)は、配置の問い合わせの答え(artifacts/w3-b1/r10_placement_answers.jsonl と
    r10_placement_answers_batch2.jsonl。読解器の出力を見る前に引いた)が `DECIDED`・`direct`・P_MOVE の語だけを使う。名詞は ja_r8 で型の門を通った語
    (artifacts/w3-b1/r8_placement_answers.jsonl)だけを使う。
  - 1 行の形は ja_r9.jsonl と同じ(+ `derived`: potential / short_causative / ichidan_plain / ichidan_upper / godan_plain / sa_not_a / dekiru / ranuki / spontaneous)。
    `expect` は規約どおりの正しい読み(可能形は元の動詞に modality ability、使役は元の動詞・voice causative・causer・causee・patient、規約 §3・§4)。
    `entry_expect` は「登録した門(語尾の門 K63・派生の疑いの門 表の変更記録 3)と表と配置の答えなら入口は読むはず/棄権するはず」:
    可能形・短い使役・下一段・ら抜き・できる・自発は abstain(門は広く棄権に倒す)、五段・上一段・サ行(原形の末尾がア段+すでない)は read。
  - `must_not` に、この経路が起こしうる取り違え(可能形・〜す のままの述語、modality null、voice active、役割の取り違え)を書く。
  - `expect_reason_prefix` は null(棄権の理由は先に決めない。測定で内訳を報告する)。
  - 1 文 1 節。語尾の門が通す 4 つの形(終止・過去・否定・否定の過去)だけを使い、K64 の標識・二重の助詞は入れない(この門だけを測る)。
  - `tests/reading_soundness/w3b1_r10_excluded.txt`(レビュー第 3 ラウンドに載った文と指示書・探りの文)と重ならない。
使い方: python tests/reading_soundness/w3b1_mk_r10.py [--out-dir DIR] [--overlap-out FILE]   (DIR の既定はこのファイルの隣)
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROWS = []
COUNTER = {'U': 0, 'S4': 0}

# ---------------------------------------------------------------------------------------------------------------------------------
# 動詞の活用(五段の行ごとの語尾。一段)。語ではなく活用の型の表
# ---------------------------------------------------------------------------------------------------------------------------------
GODAN_END = {   # 辞書形の語尾: (未然形の語尾, て形, た形, 可能の e 段)
    'う': ('わ', 'って', 'った', 'え'), 'く': ('か', 'いて', 'いた', 'け'), 'む': ('ま', 'んで', 'んだ', 'め'), 'る': ('ら', 'って', 'った', 'れ'),
    'す': ('さ', 'して', 'した', 'せ'), 'ぶ': ('ば', 'んで', 'んだ', 'べ'), 'ぐ': ('が', 'いで', 'いだ', 'げ'),
}
TAILS = ('past', 'nonpast', 'neg', 'negpast')
TAIL_VALUES = {'past': ('+', 'past'), 'nonpast': ('+', 'nonpast'), 'neg': ('-', 'nonpast'), 'negpast': ('-', 'past')}


def godan(verb, kind, tail):
    """五段の辞書形 verb の、kind(plain・potential・causative)の tail の形(句点なし)と、その kind の辞書形。"""
    stem, last = verb[:-1], verb[-1]
    a, te, ta, e = GODAN_END[last]
    if verb == '行く': ta = 'った'
    if kind == 'plain':
        base, ends = verb, {'past': stem + ta, 'nonpast': verb, 'neg': stem + a + 'ない', 'negpast': stem + a + 'なかった'}
    elif kind == 'potential':
        base = stem + e + 'る'
        ends = {'past': stem + e + 'た', 'nonpast': base, 'neg': stem + e + 'ない', 'negpast': stem + e + 'なかった'}
    else:
        base = stem + a + 'す'
        ends = {'past': stem + a + 'した', 'nonpast': base, 'neg': stem + a + 'さない', 'negpast': stem + a + 'さなかった'}
    return ends[tail], base


def ichidan(verb, kind, tail):
    """一段の辞書形 verb の、kind(plain・ranuki)の tail の形と、その kind の辞書形。"""
    stem = verb[:-1]
    if kind == 'ranuki':
        base = stem + 'れる'; s = stem + 'れ'
    else:
        base = verb; s = stem
    ends = {'past': s + 'た', 'nonpast': base, 'neg': s + 'ない', 'negpast': s + 'なかった'}
    return ends[tail], base


def mn_role(role, value, clause=0):
    return {'clause': clause, 'role': role, 'value': value}


def mn_field(field, value, clause=0):
    return {'clause': clause, 'field': field, 'value': value}


def add(path, text, behavior, clause, derived, entry, construction, pred_type, must_not, note, tail=None):
    COUNTER[path] += 1
    if behavior == 'abstain':
        expect = {'readable': False, 'clauses': [], 'relations': [], 'must_not': []}
    else:
        expect = {'readable': True, 'clauses': [clause], 'relations': [], 'must_not': must_not}
    ROWS.append({
        'id': 'W3B1-R10-%s-%03d' % (path, COUNTER[path]), 'lang': 'ja', 'behavior': behavior, 'input': text, 'text': text, 'expect': expect,
        'path': path, 'pred_type': pred_type, 'construction': construction, 'tail': tail, 'derived': derived, 'entry_expect': entry,
        'expect_reason_prefix': None, 'note': note})


NOTES = {
    'potential': '可能動詞(%s)。述語は元の動詞・modality ability(規約 §3)。可能形のまま・modality null は取り違え。派生の疑いの門を測る。',
    'short_causative': '短い使役(〜す)。述語は元の動詞・voice causative(規約 §4)。〜す のまま・voice active は取り違え。派生の疑いの門を測る。',
    'ichidan_plain': '可能形でない下一段の動詞(比べ)。登録した門は下一段を広く棄権に倒すので entry_expect は abstain(読めなくなる代償を数える)。',
    'ichidan_upper': '上一段の動詞(比べ)。門の対象ではないので read。',
    'godan_plain': '五段の動詞(比べ)。門の対象ではないので read。',
    'sa_not_a': '五段-サ行で原形の末尾がア段+すでない動詞(比べ。送り仮名が漢字に吸われる)。門の対象ではないので read。',
    'dekiru': 'できる(上一段。サ変の可能)。語は足さず、入口の既存の標識(_MODAL_MARKS)で棄権するはず。規約に決まった読みが無いので expect は readable false。',
    'ranuki': 'ら抜きの可能形(下一段)。述語は元の動詞・modality ability。派生の疑いの門で棄権するはず。',
    'spontaneous': '自発の思える(下一段)。規約に自発の読みが無いので expect は readable false。派生の疑いの門で棄権するはず。',
}

# ---------------------------------------------------------------------------------------------------------------------------------
# 経路 U(P_MOVE。<agent>が[<source>から][<time>に][<goal>へ]<動詞>)
# ---------------------------------------------------------------------------------------------------------------------------------
# (agent, goal, 辞書形, 語尾の型, source, time)
U_POTENTIAL = [
    ('弟', '公園', '歩く', 'past', None, None), ('猫', '広場', '歩く', 'nonpast', None, None), ('馬', '村', '歩く', 'neg', None, None), ('兄', '寺', '歩く', 'negpast', None, None),
    ('妹', '病院', '行く', 'past', None, None), ('父', '市場', '行く', 'nonpast', None, None), ('母', '港', '行く', 'neg', None, None), ('姉', '空港', '行く', 'negpast', None, None),
    ('兄', '部屋', '戻る', 'past', None, None), ('妹', '教室', '戻る', 'nonpast', None, None), ('弟', '台所', '戻る', 'neg', None, None), ('父', '工場', '戻る', 'negpast', None, None),
    ('姉', '空港', '向かう', 'past', '駅', None), ('祖父', '病院', '向かう', 'neg', None, '夜'), ('弟', '橋', '向かう', 'negpast', None, None),
    ('母', '部屋', '移る', 'past', '台所', None), ('兄', '町', '移る', 'nonpast', None, None),
]
U_CAUSATIVE = [
    ('先生', '公園', '歩く', 'past', None, None), ('母', '庭', '歩く', 'nonpast', None, None), ('兄', '橋', '歩く', 'negpast', None, None), ('父', '広場', '歩く', 'neg', None, None),
]
U_ICHIDAN = [   # 可能形でない下一段(出る・離れる・出かける)
    ('猫', '庭', '出る', 'past', None, None), ('犬', '森', '出る', 'nonpast', None, None), ('弟', '広場', '出る', 'negpast', None, None),
    ('兄', None, '離れる', 'past', '駅', None), ('母', '病院', '出かける', 'past', None, None), ('姉', '港', '出かける', 'negpast', None, None),
]
U_GODAN = [
    ('兄', '山', '登る', 'past', None, None), ('姉', '島', '渡る', 'nonpast', None, None), ('犬', '部屋', '戻る', 'past', None, None), ('弟', '町', '進む', 'negpast', None, None),
    ('妹', '空港', '向かう', 'past', None, None), ('祖父', '港', '帰る', 'neg', None, None), ('父', '店', '入る', 'past', None, None),
]
U_SA_NOT_A = [
    ('兄', '病院', '引き返す', 'past', None, None), ('姉', '寺', '引き返す', 'neg', None, None), ('母', '駅', '引き返す', 'negpast', None, None),
]


def u_row(spec, derived, kind, entry):
    ag, goal, verb, tail, src, tm = spec
    text = ag + 'が' + (src + 'から' if src else '') + (tm + 'に' if tm else '') + (goal + 'へ' if goal else '') + godan_or_ichidan(verb, kind, tail)[0] + '。'
    form, base = godan_or_ichidan(verb, kind, tail)
    roles = {}
    cons = []
    pol, tense = TAIL_VALUES[tail]
    if kind == 'causative': roles['causer'] = ag
    else: roles['agent'] = ag
    if goal: roles['goal'] = goal; cons.append('goal:へ:PLACE')
    if src: roles['source'] = src; cons.append('source:から:PLACE')
    if tm: roles['time'] = tm; cons.append('time:に:TIME')
    clause = {'predicate': verb, 'roles': roles, 'polarity': pol, 'tense': tense,
              'modality': 'ability' if kind in ('potential', 'ranuki') else None, 'voice': 'causative' if kind == 'causative' else 'active'}
    where = goal or src
    mn = [mn_role('recipient', where), mn_role('place', where), mn_role('patient', ag)]
    if kind in ('potential', 'ranuki'): mn += [mn_field('modality', None), mn_field('predicate', base)]
    if kind == 'causative': mn += [mn_field('voice', 'active'), mn_field('predicate', base), mn_role('agent', ag)]
    if pol == '-': mn.append(mn_field('polarity', '+'))
    note = NOTES[derived] if derived != 'potential' else NOTES[derived] % base
    add('U', text, 'read', clause, derived, entry, '+'.join(cons), 'P_MOVE', mn, note, tail)


def godan_or_ichidan(verb, kind, tail):
    return (ichidan if kind in ('ichidan', 'ranuki') else godan)(verb, 'plain' if kind in ('plain', 'ichidan') else kind, tail)


for s in U_POTENTIAL: u_row(s, 'potential', 'potential', 'abstain')
for s in U_CAUSATIVE: u_row(s, 'short_causative', 'causative', 'abstain')
for s in U_ICHIDAN: u_row(s, 'ichidan_plain', 'ichidan', 'abstain')
for s in U_GODAN: u_row(s, 'godan_plain', 'plain', 'read')
for s in U_SA_NOT_A: u_row(s, 'sa_not_a', 'plain', 'read')

# ---------------------------------------------------------------------------------------------------------------------------------
# 経路 S4(<agent>が<time>、<patient>を<動詞>。時の語が覆われずに残る)
# ---------------------------------------------------------------------------------------------------------------------------------
# (agent, time, patient, 辞書形, 語尾の型)
S4_POTENTIAL = [
    ('母', '夕方', '手紙', '書く', 'past'), ('父', '週末', '絵', '描く', 'nonpast'), ('姉', '休日', '靴', '磨く', 'neg'), ('兄', '春休み', '食器', '洗う', 'negpast'),
    ('弟', '冬', '本', '読む', 'past'), ('妹', '夏', '皿', '洗う', 'nonpast'), ('祖父', '秋', '絵', '描く', 'neg'), ('先生', '早朝', '床', '磨く', 'negpast'),
    ('生徒', '連休', '手紙', '書く', 'nonpast'), ('学生', '夜中', '本', '読む', 'neg'), ('店員', '日曜', '床', '磨く', 'past'), ('母', '真夜中', '絵', '描く', 'negpast'),
    ('父', '大晦日', '皿', '洗う', 'past'), ('姉', '正午', '靴', '磨く', 'nonpast'),
]
# (agent, time, を の語, 辞書形, 語尾の型, を の語の役割)
S4_CAUSATIVE = [
    ('先生', '放課後', '生徒', '走る', 'past', 'causee'), ('父', '週末', '弟', '歩く', 'nonpast', 'causee'), ('母', '休日', '妹', '走る', 'negpast', 'causee'),
    ('兄', '夏', '弟', '歩く', 'neg', 'causee'), ('店員', '夜', '学生', '走る', 'past', 'causee'),
    ('姉', '昼', '手紙', '書く', 'past', 'patient'), ('母', '夕方', '本', '読む', 'past', 'patient'),
]
S4_ICHIDAN = [
    ('母', '夕方', '扉', '閉める', 'neg'), ('店員', '早朝', '窓', '開ける', 'negpast'), ('祖父', '秋', '窓', '閉める', 'nonpast'),
    ('弟', '週末', '果物', '食べる', 'past'), ('妹', '夏', '食器', '並べる', 'past'),
]
S4_GODAN = [
    ('父', '週末', '靴', '洗う', 'past'), ('先生', '冬', '手紙', '書く', 'past'), ('母', '夏', '絵', '描く', 'nonpast'), ('弟', '秋', '本', '読む', 'negpast'),
]
S4_UPPER = [('母', '昼', '写真', '見る', 'past'), ('弟', '冬', '服', '着る', 'past')]
S4_SA_NOT_A = [('兄', '夕方', '手紙', '渡す', 'past'), ('母', '昼', '本', '返す', 'past'), ('先生', '冬', '本', '貸す', 'negpast')]
S4_RANUKI = [('兄', '夜', '映画', '見る', 'past'), ('弟', '冬', '果物', '食べる', 'past')]
S4_DEKIRU = [('姉', '冬', '掃除', 'past'), ('母', '昼', '洗濯', 'negpast')]
S4_SPONT = [('姉', '夜', '昔', 'past'), ('兄', '冬', '故郷', 'past')]


def s4_row(ag, tm, obj, verb, tail, derived, kind, entry, obj_role='patient'):
    form, base = godan_or_ichidan(verb, kind, tail)
    pol, tense = TAIL_VALUES[tail]
    roles = {'time': tm}
    if kind == 'causative':
        roles = {'causer': ag, 'time': tm, obj_role: obj}
    else:
        roles = {'agent': ag, 'time': tm, 'patient': obj}
    clause = {'predicate': verb, 'roles': roles, 'polarity': pol, 'tense': tense,
              'modality': 'ability' if kind in ('potential', 'ranuki') else None, 'voice': 'causative' if kind == 'causative' else 'active'}
    mn = [mn_role('place', tm), mn_role('patient', tm)]
    if kind in ('potential', 'ranuki'): mn += [mn_field('modality', None), mn_field('predicate', base)]
    if kind == 'causative': mn += [mn_field('voice', 'active'), mn_field('predicate', base), mn_role('agent', ag)]
    if pol == '-': mn.append(mn_field('polarity', '+'))
    note = NOTES[derived] if derived != 'potential' else NOTES[derived] % base
    add('S4', ag + 'が' + tm + '、' + obj + 'を' + form + '。', 'read', clause, derived, entry, 'time:∅(、):TIME', None, mn, note, tail)


for ag, tm, obj, verb, tail in S4_POTENTIAL: s4_row(ag, tm, obj, verb, tail, 'potential', 'potential', 'abstain')
for ag, tm, obj, verb, tail, orole in S4_CAUSATIVE: s4_row(ag, tm, obj, verb, tail, 'short_causative', 'causative', 'abstain', orole)
for ag, tm, obj, verb, tail in S4_ICHIDAN: s4_row(ag, tm, obj, verb, tail, 'ichidan_plain', 'ichidan', 'abstain')
for ag, tm, obj, verb, tail in S4_GODAN: s4_row(ag, tm, obj, verb, tail, 'godan_plain', 'plain', 'read')
for ag, tm, obj, verb, tail in S4_UPPER: s4_row(ag, tm, obj, verb, tail, 'ichidan_upper', 'ichidan', 'read')
for ag, tm, obj, verb, tail in S4_SA_NOT_A: s4_row(ag, tm, obj, verb, tail, 'sa_not_a', 'plain', 'read')
for ag, tm, obj, verb, tail in S4_RANUKI: s4_row(ag, tm, obj, verb, tail, 'ranuki', 'ranuki', 'abstain')
for ag, tm, obj, tail in S4_DEKIRU:
    add('S4', ag + 'が' + tm + '、' + obj + ('ができた' if tail == 'past' else 'ができなかった') + '。', 'abstain', None, 'dekiru', 'abstain', 'time:∅(、):TIME', None, [], NOTES['dekiru'], tail)
for ag, tm, obj, tail in S4_SPONT:
    add('S4', ag + 'が' + tm + '、' + obj + 'を思えた。', 'abstain', None, 'spontaneous', 'abstain', 'time:∅(、):TIME', None, [], NOTES['spontaneous'], 'past')


# ---------------------------------------------------------------------------------------------------------------------------------
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
                except ValueError: pass
    return seen


def other_values():
    root = HERE.parents[1]
    paths = [p for p in HERE.glob('*.jsonl') if p.name != 'ja_r10.jsonl'] + list((root / 'tests' / 'bank_score' / 'fixtures').rglob('*.jsonl'))
    cross = set()
    cpaths = list((root / 'tests' / 'event_cross' / 'data').glob('sentences_*.jsonl'))
    for p in cpaths:
        for line in p.read_text(encoding='utf-8').splitlines():
            if line.strip(): cross.add(json.loads(line)['text'].strip())
    excluded = {l.strip() for l in (HERE / 'w3b1_r10_excluded.txt').read_text(encoding='utf-8').splitlines() if l.strip()}
    return load_values(paths), cross, excluded, len(paths), len(cpaths)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-dir', default=str(HERE)); ap.add_argument('--overlap-out', default=None)
    a = ap.parse_args()
    inputs = [r['input'] for r in ROWS]
    assert len(set(inputs)) == len(inputs), 'duplicate input'
    for r in ROWS:
        for c in r['expect']['clauses']:
            for role, v in c['roles'].items(): assert v in r['input'], (r['id'], role, v)
    seen, cross, excluded, npaths, ncross = other_values()
    mine = set()
    for r in ROWS: mine.update(x.strip() for x in strings(r))
    inputs_shared = sorted(set(inputs) & seen)
    cross_shared = sorted(mine & cross)
    excluded_shared = sorted(set(inputs) & excluded)
    overlap = inputs_shared + cross_shared + excluded_shared
    if a.overlap_out:
        Path(a.overlap_out).write_text('files_compared=%d cross_files=%d excluded_sentences=%d\ninputs_shared_with_existing=%d\ncross_sentences_shared_with_this_data=%d\ninputs_shared_with_excluded=%d\noverlap=%d\n%s'
                                       % (npaths, ncross, len(excluded), len(inputs_shared), len(cross_shared), len(excluded_shared), len(overlap), ''.join(x + '\n' for x in overlap)), encoding='utf-8')
    if overlap:
        print('OVERLAP', len(overlap), overlap[:10]); raise SystemExit(1)
    out = Path(a.out_dir) / 'ja_r10.jsonl'
    out.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in ROWS), encoding='utf-8')
    print('ja=%d overlap=0 files_compared=%d cross_files=%d' % (len(ROWS), npaths, ncross))


if __name__ == '__main__':
    main()
