"""Append the 14 rows of round 2 (W1-a5-2, K218) to tests/reading_soundness/ja_r12.jsonl (append mode: the 151 rows of round 1 are not rewritten).

Usage: python append_k218_rows.py [--dry-run]
Refuses to run when the file does not start with the frozen 151 rows of round 1 (sha256 of the first 151 lines) or already has more than 151 lines.
"""
import hashlib
import json
import pathlib
import sys

TREE = pathlib.Path(__file__).resolve().parents[3]
DATA = TREE / 'tests' / 'reading_soundness' / 'ja_r12.jsonl'
FROZEN_R1 = 'd6050258d452715c837a5eb12594b46ef6ae57bb3bc4bde637b85886035dcf96'
NP = {'path': 'reread_refused', 'reason_prefix': 'QUANTIFIER_TARGET_UNDETERMINED:noun_phrase', 'quantifiers': None, 'flags': None}
NT = {'path': 'not_triggered', 'reason_prefix': None, 'quantifiers': None, 'flags': None}
R1C3 = 'review.r1 C3 の誤読'
PLAN = 'W1-a5-2 指示書の探りの誤読'
ROWS = [
    ('W1A5-QTY-A-901', 'quantity', '学生が論文を三人書いた。', NP, '主語の遊離数量が目的語を挟む', R1C3),
    ('W1A5-QTY-A-902', 'quantity', '客がケーキを五人食べた。', NP, '主語の遊離数量が目的語を挟む', R1C3),
    ('W1A5-QTY-A-903', 'quantity', '子供たちが絵を三人描いた。', NP, '主語の遊離数量が目的語を挟む', R1C3),
    ('W1A5-QTY-A-904', 'quantity', '学生は論文を三人書いた。', NP, '主語が は（遊離数量が目的語を挟む）', PLAN),
    ('W1A5-QTY-A-905', 'quantity', '論文を三人書いた。', NP, '主語の省略', PLAN),
    ('W1A5-QTY-A-906', 'quantity', '兄が三冊読んだ。', NP, '目的語の省略', PLAN),
    ('W1A5-QTY-A-907', 'quantity', '母が五個買った。', NP, '目的語の省略', PLAN),
    ('W1A5-QTY-A-908', 'quantity', '本は兄が三冊読んだ。', NP, '目的語が主題（は）', PLAN),
    ('W1A5-QTY-A-909', 'quantity', '手紙は姉が二通書いた。', NP, '目的語が主題（は）', PLAN),
    ('W1A5-ADV-A-901', 'adverb', '兄がおおかた家に帰った。', NT, '推量の副詞', R1C3),
    ('W1A5-ADV-A-902', 'adverb', '兄がどうやら家に帰った。', NT, '証拠の副詞', R1C3),
    ('W1A5-ADV-A-903', 'adverb', '兄がたしか本を読んだ。', NT, '記憶の留保の副詞', R1C3),
    ('W1A5-ADV-A-904', 'adverb', '兄がまさか本を読んだ。', NT, '不信の副詞', R1C3),
    ('W1A5-ADV-A-905', 'adverb', '兄がさぞ喜んだ。', NT, '推量の副詞', R1C3),
]


def row(rid, cat, text, w1a5, construction, source):
    return {'id': rid, 'lang': 'ja', 'category': cat, 'behavior': 'abstain', 'input': text, 'text': text,
            'expect': {'readable': False, 'clauses': [], 'relations': [], 'must_not': []}, 'entry_expect': 'abstain',
            'w1a5_expect': dict(w1a5), 'construction': construction, 'note': source}


def main():
    raw = DATA.read_bytes()
    lines = raw.split(b'\n')
    assert lines[-1] == b'', 'the file must end with a newline'
    lines = lines[:-1]
    assert len(lines) == 151, 'expected the 151 frozen rows, found %d (already appended?)' % len(lines)
    assert hashlib.sha256(b'\n'.join(lines) + b'\n').hexdigest() == FROZEN_R1, 'the first 151 rows differ from the round-1 freeze'
    texts = {json.loads(l)['input'] for l in lines}
    assert not any(r[2] in texts for r in ROWS), 'a sentence is already in the data'
    out = ''.join(json.dumps(row(*r), ensure_ascii=False) + '\n' for r in ROWS)
    if '--dry-run' in sys.argv:
        print(out, end='')
        return
    with open(DATA, 'a', encoding='utf-8') as fh:       # append mode: nothing before is rewritten
        fh.write(out)
    print('appended', len(ROWS), 'rows')


if __name__ == '__main__':
    main()
