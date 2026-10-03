#!/usr/bin/env python3
"""W3-b1 第 3 ラウンド(レビュー第 2 ラウンド M7): 検査データ ja_r9.jsonl を書く生成スクリプト。

このスクリプトは verantyx を import しない(読解器にも入口にも配置にも通さずに、期待を先に書いて凍結するため)。
目的: 新しい経路(U・S4)が読んだ節の述語の語尾が、今の規則が極性・時制・モダリティを決める形でなければ読まない(docs K63 の「述語の語尾の門」、表の変更記録 2)。
その門を書く前に、語尾の型を持つ文を経路ごとに 30 文(合わせて 60 文)、期待を先に書いて凍結する。
  - 語は ja_r8 で使った語(配置の問い合わせの答えは artifacts/w3-b1/r8_placement_answers.jsonl)だけを使う。型の門・構成の表で落ちる語は入れない
    (この検査は語尾の門を測るためで、型の門は ja_r8 が測っている)。
  - 1 行の形は ja_r8.jsonl と同じ(+ `tail`: 語尾の型)。`expect` は規約 §5 どおりの正しい読み。`entry_expect` は「登録した語尾の門(K63)と表と配置の答えなら
    入口は読むはず/棄権するはず」: 語尾の型が 終止形・過去(た)・単純否定(ない・なかった)なら read、それ以外は abstain。
  - `must_not` に、この経路が起こしうる取り違え(否定を + にする・モダリティを null にする)と、役割の取り違えを書く。
  - `expect_reason_prefix` は null(棄権の理由は、型を決める前に今の規則が棄権する文もあるので、先に決めない。測定で内訳を報告する)。
使い方: python tests/reading_soundness/w3b1_mk_r9.py [--out-dir DIR] [--overlap-out FILE]   (DIR の既定はこのファイルの隣)
"""
import argparse
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROWS = []
COUNTER = {'U': 0, 'S4': 0}

# ---------------------------------------------------------------------------------------------------------------------------------
# 動詞の活用(五段・一段のうち使うものだけ。語尾の型ごとの形を作る)
# ---------------------------------------------------------------------------------------------------------------------------------
GODAN = {   # 辞書形: (未然形の語幹, 連用形の語幹, て形, た形, 命令形)
    '走る': ('走ら', '走り', '走って', '走った', '走れ'), '歩く': ('歩か', '歩き', '歩いて', '歩いた', '歩け'), '飛ぶ': ('飛ば', '飛び', '飛んで', '飛んだ', '飛べ'),
    '読む': ('読ま', '読み', '読んで', '読んだ', '読め'), '書く': ('書か', '書き', '書いて', '書いた', '書け'), '洗う': ('洗わ', '洗い', '洗って', '洗った', '洗え'),
    '磨く': ('磨か', '磨き', '磨いて', '磨いた', '磨け'), '描く': ('描か', '描き', '描いて', '描いた', '描け'),
}
ICHIDAN = {  # 辞書形: 語幹
    '閉める': '閉め', '開ける': '開け',
}

# 語尾の型 -> (極性, 時制, モダリティ, entry_expect)。規約 §5 の読み。時制 None は「採点しない」(テ形・命令)
TAILS = {
    'past': ('+', 'past', None, 'read'), 'nonpast': ('+', 'nonpast', None, 'read'),
    'neg': ('-', 'nonpast', None, 'read'), 'negpast': ('-', 'past', None, 'read'),
    'prog': ('+', 'nonpast', None, 'abstain'), 'progpast': ('+', 'past', None, 'abstain'),
    'progneg': ('-', 'nonpast', None, 'abstain'), 'prognegpast': ('-', 'past', None, 'abstain'),
    'polneg': ('-', 'nonpast', None, 'abstain'), 'progpolneg': ('-', 'nonpast', None, 'abstain'),
    'proh': ('+', 'nonpast', 'prohibition', 'abstain'), 'imp': ('+', None, 'request', 'abstain'),
    'nomore': ('-', 'nonpast', 'volition', 'abstain'),
    'desire': ('+', 'nonpast', 'desire', 'abstain'), 'desirepast': ('+', 'past', 'desire', 'abstain'),
    'please': ('+', None, 'request', 'abstain'), 'shimau': ('+', 'past', None, 'abstain'), 'oku': ('+', 'nonpast', None, 'abstain'),
    'youda': ('+', 'nonpast', 'conjecture', 'abstain'), 'rashii': ('+', 'nonpast', 'hearsay', 'abstain'), 'souda': ('+', 'nonpast', 'hearsay', 'abstain'),
    'kamo': ('+', 'nonpast', 'possibility', 'abstain'), 'beki': ('+', 'nonpast', 'obligation', 'abstain'),
}


def form(verb, tail):
    """辞書形 verb を、語尾の型 tail の書かれた形にする(句点なし)。"""
    if verb in GODAN:
        a, i, te, ta, e = GODAN[verb]
        u = verb
    else:
        a = i = ICHIDAN[verb]; e = a + 'ろ'; u = verb
        te, ta = a + 'て', a + 'た'
    return {
        'past': ta, 'nonpast': u, 'neg': a + 'ない', 'negpast': a + 'なかった',
        'prog': te + 'いる', 'progpast': te + 'いた', 'progneg': te + 'いない', 'prognegpast': te + 'いなかった',
        'polneg': i + 'ません', 'progpolneg': te + 'いません',
        'proh': u + 'な', 'imp': e, 'nomore': u + 'まい',
        'desire': i + 'たい', 'desirepast': i + 'たかった', 'please': te + 'ください', 'shimau': te + 'しまった', 'oku': te + 'おく',
        'youda': u + 'ようだ', 'rashii': u + 'らしい', 'souda': u + 'そうだ', 'kamo': u + 'かもしれない', 'beki': u + 'べきだ',
    }[tail]


def mn_role(role, value, clause=0):
    return {'clause': clause, 'role': role, 'value': value}


def add(path, text, verb, roles, tail, construction, pred_type, must_not_roles, note):
    pol, tense, mod, entry = TAILS[tail]
    COUNTER[path] += 1
    must_not = list(must_not_roles)
    if pol == '-': must_not.append({'clause': 0, 'field': 'polarity', 'value': '+'})
    if mod is not None: must_not.append({'clause': 0, 'field': 'modality', 'value': None})
    ROWS.append({
        'id': 'W3B1-R9-%s-%03d' % (path, COUNTER[path]), 'lang': 'ja', 'behavior': 'read', 'input': text, 'text': text,
        'expect': {'readable': True, 'clauses': [{'predicate': verb, 'roles': roles, 'polarity': pol, 'tense': tense, 'modality': mod, 'voice': 'active'}],
                   'relations': [], 'must_not': must_not},
        'path': path, 'pred_type': pred_type, 'construction': construction, 'tail': tail, 'entry_expect': entry, 'expect_reason_prefix': None, 'note': note})


# ---------------------------------------------------------------------------------------------------------------------------------
# 経路 U(P_MOVE。<agent>が[<source>から][<time>に]<goal>へ<動詞>)
# ---------------------------------------------------------------------------------------------------------------------------------
# (agent, goal, 辞書形, 語尾の型, source, time)
U_ROWS = [
    ('犬', '畑', '走る', 'past', None, None), ('猫', '広場', '歩く', 'nonpast', None, None), ('鳥', '湖', '飛ぶ', 'negpast', None, None),
    ('馬', '村', '走る', 'neg', None, None), ('兄', '寺', '歩く', 'past', '橋', None), ('弟', '病院', '走る', 'past', None, '夜'),
    ('猫', '庭', '走る', 'prog', None, None), ('犬', '森', '走る', 'progpast', None, None), ('鳥', '島', '飛ぶ', 'progneg', None, None),
    ('馬', '畑', '走る', 'progpolneg', None, None), ('兄', '橋', '歩く', 'prognegpast', None, None), ('弟', '広場', '歩く', 'polneg', None, None),
    ('犬', '庭', '走る', 'proh', None, None), ('鳥', '島', '飛ぶ', 'proh', None, None), ('兄', '寺', '歩く', 'imp', None, None),
    ('弟', '港', '走る', 'imp', None, None), ('馬', '森', '走る', 'nomore', None, None), ('姉', '広場', '歩く', 'nomore', None, None),
    ('兄', '湖', '歩く', 'desire', None, None), ('弟', '橋', '走る', 'desirepast', None, None), ('妹', '町', '飛ぶ', 'desirepast', None, None),
    ('犬', '畑', '走る', 'please', None, None), ('母', '寺', '歩く', 'shimau', None, None), ('父', '港', '走る', 'oku', None, None),
    ('猫', '庭', '走る', 'youda', None, None), ('鳥', '森', '飛ぶ', 'rashii', None, None), ('馬', '村', '走る', 'souda', None, None),
    ('兄', '橋', '歩く', 'kamo', None, None), ('弟', '湖', '走る', 'beki', None, None), ('兄', '村', '歩く', 'prognegpast', '駅', None),
]
for ag, goal, verb, tail, src, tm in U_ROWS:
    text = ag + 'が' + (src + 'から' if src else '') + (tm + 'に' if tm else '') + goal + 'へ' + form(verb, tail) + '。'
    roles = {'agent': ag, 'goal': goal}
    if src: roles['source'] = src
    if tm: roles['time'] = tm
    cons = 'goal:へ:PLACE' + (' + source:から:PLACE' if src else '') + (' + time:に:TIME' if tm else '')
    add('U', text, verb, roles, tail, cons, 'P_MOVE', [mn_role('recipient', goal), mn_role('place', goal), mn_role('patient', ag)],
        '語尾の型 %s。述語は読解器の 4 つの一覧の外。型の門は通る語だけを使う(語尾の門だけを測る)。' % tail)

# ---------------------------------------------------------------------------------------------------------------------------------
# 経路 S4(<agent>が<time>、<patient>を<動詞>。時の語が覆われずに残る)
# ---------------------------------------------------------------------------------------------------------------------------------
# (agent, time, patient, 辞書形, 語尾の型)
S4_ROWS = [
    ('兄', '夜', '窓', '開ける', 'past'), ('母', '昼', '手紙', '書く', 'nonpast'), ('姉', '冬', '皿', '洗う', 'negpast'),
    ('弟', '休日', '靴', '磨く', 'neg'), ('妹', '放課後', '絵', '描く', 'past'), ('父', '年末', '扉', '閉める', 'negpast'),
    ('兄', '夜', '本', '読む', 'prog'), ('母', '昼', '手紙', '書く', 'progpast'), ('姉', '冬', '窓', '閉める', 'progneg'),
    ('弟', '休日', '皿', '洗う', 'prognegpast'), ('妹', '平日', '靴', '磨く', 'progpolneg'), ('父', '月末', '絵', '描く', 'polneg'),
    ('先生', '夜', '本', '読む', 'proh'), ('生徒', '昼', '窓', '開ける', 'proh'), ('学生', '冬', '手紙', '書く', 'imp'),
    ('祖父', '休日', '窓', '閉める', 'imp'), ('店員', '平日', '床', '磨く', 'imp'), ('兄', '年末', '皿', '洗う', 'nomore'),
    ('姉', '月末', '本', '読む', 'nomore'), ('弟', '放課後', '絵', '描く', 'desire'), ('妹', '誕生日', '手紙', '書く', 'desirepast'),
    ('母', '夜', '靴', '磨く', 'desire'), ('父', '昼', '扉', '開ける', 'please'), ('先生', '冬', '本', '読む', 'shimau'),
    ('生徒', '休日', '食器', '洗う', 'oku'), ('祖父', '平日', '窓', '閉める', 'youda'), ('学生', '年末', '手紙', '書く', 'rashii'),
    ('店員', '月末', '床', '磨く', 'souda'), ('兄', '誕生日', '絵', '描く', 'kamo'), ('姉', '放課後', '本', '読む', 'beki'),
]
for ag, tm, obj, verb, tail in S4_ROWS:
    text = ag + 'が' + tm + '、' + obj + 'を' + form(verb, tail) + '。'
    add('S4', text, verb, {'agent': ag, 'time': tm, 'patient': obj}, tail, 'time:∅(、):TIME', None,
        [mn_role('place', tm), mn_role('patient', tm)],
        '語尾の型 %s。時の語は ja_r8 で読めた型(門 5 を通る)。語尾の門だけを測る。' % tail)


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
    paths = [p for p in HERE.glob('*.jsonl') if p.name != 'ja_r9.jsonl'] + list((root / 'tests' / 'bank_score' / 'fixtures').rglob('*.jsonl'))
    cross = set()
    cpaths = list((root / 'tests' / 'event_cross' / 'data').glob('sentences_*.jsonl'))
    for p in cpaths:
        for line in p.read_text(encoding='utf-8').splitlines():
            if line.strip(): cross.add(json.loads(line)['text'].strip())
    return load_values(paths), cross, len(paths), len(cpaths)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out-dir', default=str(HERE)); ap.add_argument('--overlap-out', default=None)
    a = ap.parse_args()
    inputs = [r['input'] for r in ROWS]
    assert len(set(inputs)) == len(inputs), 'duplicate input'
    for r in ROWS:
        for c in r['expect']['clauses']:
            for role, v in c['roles'].items(): assert v in r['input'], (r['id'], role, v)
    seen, cross, npaths, ncross = other_values()
    mine = set()
    for r in ROWS: mine.update(x.strip() for x in strings(r))
    inputs_shared = sorted(set(inputs) & seen)
    cross_shared = sorted(mine & cross)
    overlap = inputs_shared + cross_shared
    if a.overlap_out:
        Path(a.overlap_out).write_text('files_compared=%d cross_files=%d\ninputs_shared_with_existing=%d\ncross_sentences_shared_with_this_data=%d\noverlap=%d\n%s'
                                       % (npaths, ncross, len(inputs_shared), len(cross_shared), len(overlap), ''.join(x + '\n' for x in overlap)), encoding='utf-8')
    if overlap:
        print('OVERLAP', len(overlap), overlap[:10]); raise SystemExit(1)
    out = Path(a.out_dir) / 'ja_r9.jsonl'
    out.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in ROWS), encoding='utf-8')
    print('ja=%d overlap=0 files_compared=%d cross_files=%d' % (len(ROWS), npaths, ncross))


if __name__ == '__main__':
    main()
