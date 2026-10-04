"""W3-c4 round 2 test data (M1: written predicate forms the reader passes through as a plain past). Writes extra2/docs/*.txt, extra2/placement_extra2.json and
extra2/questions.jsonl by hand-written content. Does not import verantyx. The truth/expectation of every question is a human judgement written BEFORE the rule
was built and before any run (docs/OBSERVATION.md, 事前登録の変更記録 W3-c4, 2nd round). Sentence ids are `<file>#<line>:1` (one sentence per line, no markdown syntax).

truth.kind ONE  : the later stage may answer; the expected filler/evidence are in truth (an answer that differs is WRONG).
truth.kind NONE : the document does NOT say what the question asks (a different written form: desire, hearsay, conditional ...). `expect_no_stage_answer`:
                  the later stage must not answer or tie (door question_cross ANSWER or AMBIGUOUS_QUESTION_CROSS_TIE is WRONG). `expect_reason` is what the author
                  anticipates for the reason (not a pass/fail condition: the reader may abstain earlier)."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

DOCS = {
    'X01.txt': ['先生は本を読みたかった。', '漁師は魚を運びたがった。', '母は手紙を書きたかったです。', '校長は新聞を読んでみたかった。', '社長は資料を渡したらしかった。',
                '課長は地図を見たがっていた。', '駅員は切符を渡したら。'],
    'X02.txt': ['医者は薬を飲みたくなかった。', '看護師は書類を読んでほしかった。', '店主は鍵を探しそうだった。', '運転手は荷物を運ぶはずだった。', '画家は絵を描くようだった。',
                '弟は雑誌を買いたかったのだ。', '姉は手帳を失くしたかもしれなかった。', '兄は財布を拾ったそうだった。', '祖父は切手を集めたがらなかった。', '隣人は傘を借りるつもりだった。'],
    'X03.txt': ['猟師は鳥を撃ちたかった。', '教授は論文を書いた。', '歌手は歌を歌いました。', '農夫は米を運んでいた。', '会長は書類を渡した。', '妹は絵を描きました。',
                '先生は鍵を探したがった。'],
    'X04.txt': ['The cook wished to taste the soup.', 'The pilot had planned to fly the plane.', 'The cook did taste the soup.', 'The mayor was said to build the bridge.',
                'The doctor would read the report.'],
}

TYPES = {'PERSON': ['先生', '漁師', '母', '校長', '社長', '課長', '駅員', '医者', '看護師', '店主', '運転手', '画家', '弟', '姉', '兄', '祖父', '隣人', '猟師', '教授', '歌手',
                    '農夫', '会長', '妹', 'cook', 'pilot', 'mayor', 'doctor'],
         'ARTIFACT': ['本', '手紙', '新聞', '資料', '地図', '切符', '薬', '書類', '絵', '歌', '荷物', '鍵', '雑誌', '財布', '手帳', '傘', '切手', '米', '論文',
                      'soup', 'plane', 'bridge', 'report'],
         'ANIMAL': ['魚', '鳥']}


def q(i, doc, text, kind, filler=None, line=None, reason=None, cat='', note=''):
    truth = {'kind': kind, 'fillers': [filler] if filler else [], 'evidence': ['%s#%d:1' % (doc, line)] if line else [], 'extension_support': [], 'unread_support': []}
    out = {'id': 'X%03d' % i, 'docs': [doc], 'text': text, 'category': cat, 'truth': truth, 'note': note}
    if kind == 'NONE':
        out['expect_no_stage_answer'] = True
        out['expect_reason'] = reason or 'PREDICATE_FORM_DIFFERS'
    return out


QS = []
def add(*a, **k): QS.append(q(len(QS) + 1, *a, **k))

# --- X01: the seven written forms the first-round review found answered as a plain past (desire / hearsay / conditional) -----------------------------
add('X01.txt', '先生は何を読んだ？', 'NONE', cat='form_desire', note='たかった')
add('X01.txt', '漁師は何を運んだ？', 'NONE', cat='form_desire', note='たがった')
add('X01.txt', '母は何を書いた？', 'NONE', cat='form_desire', note='たかったです')
add('X01.txt', '校長は何を読んだ？', 'NONE', cat='form_desire', note='てみたかった')
add('X01.txt', '社長は何を渡した？', 'NONE', cat='form_desire', note='たらしかった')
add('X01.txt', '課長は何を見た？', 'NONE', cat='form_desire', note='たがっていた')
add('X01.txt', '駅員は何を渡した？', 'NONE', cat='form_desire', note='文末のたら')
add('X01.txt', '誰が本を読んだ？', 'NONE', cat='form_desire', note='誰が。既存の経路が答えるなら後段は走らない')
add('X01.txt', '誰が魚を運んだ？', 'NONE', cat='form_desire', note='誰が')
add('X01.txt', '誰が手紙を書いた？', 'NONE', cat='form_desire', note='誰が')
# the same question written in the form of the document: the stage may answer
add('X01.txt', '先生は何を読みたかった？', 'ONE', '本', 1, cat='control_match', note='問と文の述語の書き方が同じ')
add('X01.txt', '漁師は何を運びたがった？', 'ONE', '魚', 2, cat='control_match', note='問と文の述語の書き方が同じ')
add('X01.txt', '校長は何を読んでみたかった？', 'ONE', '新聞', 4, cat='control_match', note='問と文の述語の書き方が同じ')
add('X01.txt', '課長は何を見たがっていた？', 'ONE', '地図', 6, cat='control_match', note='問と文の述語の書き方が同じ')

# --- X02: forms nobody probed before (not used to build the rule) -------------------------------------------------------------------------------
for line, (who, what, verb) in enumerate([('医者', '薬', '飲んだ'), ('看護師', '書類', '読んだ'), ('店主', '鍵', '探した'), ('運転手', '荷物', '運んだ'), ('画家', '絵', '描いた'),
                                          ('弟', '雑誌', '買った'), ('姉', '手帳', '失くした'), ('兄', '財布', '拾った'), ('祖父', '切手', '集めた'), ('隣人', '傘', '借りた')], 1):
    add('X02.txt', '%sは何を%s？' % (who, verb), 'NONE', cat='form_new', note='行 %d の述語の書き方が問と違う' % line)
add('X02.txt', '誰が雑誌を買った？', 'NONE', cat='form_new', note='誰が')
add('X02.txt', '誰が傘を借りた？', 'NONE', cat='form_new', note='誰が')

# --- X03: controls (plain past, the same form) and the reverse (plain past in the document, a desire in the question) -----------------------------
add('X03.txt', '猟師は何を撃ちたかった？', 'ONE', '鳥', 1, cat='control_match', note='問と文の述語の書き方が同じ')
add('X03.txt', '教授は何を書いた？', 'ONE', '論文', 2, cat='control_plain', note='ふつうの過去')
add('X03.txt', '歌手は何を歌いました？', 'ONE', '歌', 3, cat='control_match', note='丁寧形どうし')
add('X03.txt', '農夫は何を運んでいた？', 'ONE', '米', 4, cat='control_match', note='進行形どうし')
add('X03.txt', '誰が書類を渡した？', 'ONE', '会長', 5, cat='control_plain', note='既存の経路が答える形')
add('X03.txt', '妹は何を描いた？', 'NONE', cat='polite_over', note='文は丁寧形、問は普通形: 述語の書き方が違うので棄権してよい（過剰な棄権）。答えは 絵 だが、正しい答えを要求しない')
add('X03.txt', '教授は何を書きたかった？', 'NONE', cat='reverse', note='文は過去、問は願望')
add('X03.txt', '教授は何を書きたがった？', 'NONE', cat='reverse', note='文は過去、問は願望（がる）')
add('X03.txt', '先生は何を探した？', 'NONE', cat='form_new', note='文は たがった')
add('X03.txt', '農夫は何を運んだ？', 'NONE', cat='reverse', note='文は進行形、問は過去')
add('X03.txt', '歌手は何を歌った？', 'NONE', cat='polite_over', note='文は丁寧形、問は普通形')

# --- X04: English (the rule is not applied to English; the reader abstains on the modal forms, see docs 判断記録) ---------------------------------
add('X04.txt', 'What did the cook taste?', 'NONE', cat='en_form', reason='NO_ATTESTED_CELL', note='wished to taste が先')
add('X04.txt', 'What did the pilot fly?', 'NONE', cat='en_form', reason='NO_ATTESTED_CELL', note='had planned to fly')
add('X04.txt', 'What did the mayor build?', 'NONE', cat='en_form', reason='NO_ATTESTED_CELL', note='was said to build')
add('X04.txt', 'What did the doctor read?', 'NONE', cat='en_form', reason='NO_ATTESTED_CELL', note='would read')
add('X04.txt', 'Who read the report?', 'NONE', cat='en_form', reason='NO_ATTESTED_CELL', note='would read')


def main():
    (HERE / 'docs').mkdir(exist_ok=True)
    for name, lines in DOCS.items():
        (HERE / 'docs' / name).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    lemmas = {w: {'state': 'DECIDED', 'origin': 'direct', 'types': [t]} for t, ws in TYPES.items() for w in ws}
    (HERE / 'placement_extra2.json').write_text(json.dumps({'lemmas': lemmas, 'neighbors': {}}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    (HERE / 'questions.jsonl').write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in QS), encoding='utf-8')
    print(len(DOCS), 'docs', len(QS), 'questions')


if __name__ == '__main__':
    main()
