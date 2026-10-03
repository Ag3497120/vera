"""No word of the frozen question data appears in the code added under verantyx/ (W3-c2; the manner of tests/observe/check_no_data_words.py).

    python tests/observe/question/check_no_data_words_q.py --base 2478fc7
Scans the lines added to tracked files under verantyx/ since BASE. A data word is: a whole sentence of a document, a whole text of a question, a
placement word, a filler of a truth, and every content word (noun, verb, adjective, adverb of Japanese by the tagger; a word of 3 or more letters
of English, minus a closed list of function words) of the documents and the questions. One-character words are not scanned: they occur in any text.
The wh words of the registered table (WH_TABLE) are the table's own words and not data; they are removed from the scan.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parents[2]
if str(TREE) not in sys.path: sys.path.insert(0, str(TREE))
EN_FUNCTION = frozenset('the and did does not for with that this from into are was were has have had but its his her their who what which when where why how a an to of in on at by is be as it or'.split())
# English words that are the code's own vocabulary and not data: the words of the reading entry's names (read, build, wrote as in "the reader wrote it") and the
# role / type names of the convention (a table of the registered kind lists them). They are removed from the scan by name, here, and nowhere else.
CODE_VOCABULARY = frozenset('read build wrote written reader person patient agent recipient'.split())


def data_words():
    from verantyx import semantic_reader as R
    from verantyx import semantic_read as SR
    words = set()
    texts = []
    for f in sorted((HERE / 'docs').glob('*.jsonl')):
        texts += [json.loads(l)['text'] for l in f.read_text(encoding='utf-8').splitlines() if l.strip()]
    questions = [json.loads(l) for l in (HERE / 'questions.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()]
    texts += [q['text'] for q in questions]
    for q in questions:
        words.update(x for x in q['truth']['fillers'])
    words.update(texts)
    words.update(json.loads((HERE / 'placement_q.json').read_text(encoding='utf-8'))['lemmas'])
    for t in texts:
        if re.search('[぀-ヿ㐀-䶿一-鿿]', t):
            for w, _, _ in R._tokens(t):
                if w.feature.pos1 in ('名詞', '動詞', '形容詞', '副詞', '代名詞', '形状詞'):
                    words.add(w.surface)
                    words.add(w.feature.lemma.split('-')[0] if w.feature.lemma else w.surface)
        for m in re.findall(r"[A-Za-z][A-Za-z'\-]+", t):
            if m.lower() not in EN_FUNCTION and len(m) >= 3: words.add(m)
    from verantyx.event_cross import NOUN_TYPE_IDS, ROLE_NAMES
    table_words = {w for row in SR.WH_TABLE for w in row['ja'] + row['en']}
    code_words = CODE_VOCABULARY | set(ROLE_NAMES) | {t.lower() for t in NOUN_TYPE_IDS}
    return sorted(w for w in words if len(w) >= 2 and w not in table_words and w.lower() not in table_words and w.lower() not in code_words
                  and not any(w in t for t in table_words))    # a piece of a wh word (the やっ of どうやって) is the table's


def added_lines(base):
    out = subprocess.run(['git', '-C', str(TREE), 'diff', '-U0', base, '--', 'verantyx/'], capture_output=True, text=True, check=True).stdout
    return [l[1:] for l in out.splitlines() if l.startswith('+') and not l.startswith('+++')]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    args = ap.parse_args(argv)
    words = data_words()
    lines = added_lines(args.base)
    hits = [(w, l.strip()[:110]) for l in lines for w in words if (w in l if not w.isascii() else re.search(r'(?<![A-Za-z])' + re.escape(w) + r'(?![A-Za-z])', l, re.I))]
    print('data words scanned: %d; added lines scanned: %d; hits: %d' % (len(words), len(lines), len(hits)))
    for w, l in hits[:40]: print('  HIT %r in: %s' % (w, l))
    return 0 if not hits else 1


if __name__ == '__main__':
    raise SystemExit(main())
