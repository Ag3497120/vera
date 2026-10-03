"""P15: no word of the frozen test data (sentences, placement words, ledger utterances, corpus rows) appears in the code that was added under verantyx/.

    python tests/observe/check_no_data_words.py --base 5cae978
Scans the lines added to tracked files under verantyx/ since BASE and the whole of the untracked/new verantyx/observe.py and verantyx/salience.py.
A data word is a seed sentence, a placement lemma or neighbour of 2 or more characters, an utterance text of a ledger, a corpus row (one-character words are not scanned: they occur in any text).
"""
import argparse
import json
import subprocess
from pathlib import Path

TREE = Path(__file__).resolve().parents[2]
DATA = TREE / 'tests' / 'observe' / 'data'


def data_words():
    words = set()
    for f in DATA.glob('seeds_*.jsonl'):
        for l in f.read_text(encoding='utf-8').splitlines():
            if l.strip(): words.add(json.loads(l)['text'])
    pl = json.loads((DATA / 'placement.json').read_text(encoding='utf-8'))
    for k, v in pl['lemmas'].items(): words.add(k)
    for k, v in pl['neighbors'].items():
        words.add(k); words.update(v)
    for f in (DATA / 'ledgers').glob('*.jsonl'):
        for l in f.read_text(encoding='utf-8').splitlines():
            if l.strip():
                ev = json.loads(l)
                if 'text' in ev['payload']: words.add(ev['payload']['text'])
    for l in (DATA / 'corpus_root' / 'out' / 'sentences.jsonl').read_text(encoding='utf-8').splitlines():
        if l.strip(): words.add(json.loads(l)['text'])
    return sorted(w for w in words if len(w) >= 2)


def added_lines(base):
    out = subprocess.run(['git', '-C', str(TREE), 'diff', '-U0', base, '--', 'verantyx/'], capture_output=True, text=True, check=True).stdout
    lines = [l[1:] for l in out.splitlines() if l.startswith('+') and not l.startswith('+++')]
    for name in ('verantyx/observe.py', 'verantyx/salience.py'):
        tracked = subprocess.run(['git', '-C', str(TREE), 'ls-files', '--error-unmatch', name], capture_output=True).returncode == 0
        path = TREE / name
        if path.exists() and not tracked: lines += path.read_text(encoding='utf-8').splitlines()
    return lines


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    args = ap.parse_args(argv)
    words = data_words()
    lines = added_lines(args.base)
    hits = [(w, l.strip()[:100]) for l in lines for w in words if w in l]
    print('data words scanned: %d; added or new lines scanned: %d; hits: %d' % (len(words), len(lines), len(hits)))
    for w, l in hits[:20]: print('  HIT %r in: %s' % (w, l))
    return 0 if not hits else 1


if __name__ == '__main__':
    raise SystemExit(main())
