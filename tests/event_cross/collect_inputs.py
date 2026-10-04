"""Collect the input set of the E1 comparison (one JSON object per line: {"id", "argv"}, argv = the arguments handed to `main`).

Order (fixed, duplicates dropped at their later occurrences): the `text` and `question` of tests/reading_soundness/*.jsonl (file names in
alphabetical order), every frozen test sentence of tests/event_cross/data, then the edge inputs of the entry (empty, blanks, 1001 characters,
a control character, a text that starts with `-`, a `--lang` that does not match, no text at all, a bad `--lang`).
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parent.parent
sys.path.insert(0, str(HERE))
import classify    # noqa: E402


def texts():
    seen, out = set(), []

    def add(source, text):
        if isinstance(text, str) and text not in seen:
            seen.add(text); out.append((source, text))
    for p in sorted((TREE / 'tests' / 'reading_soundness').glob('*.jsonl'), key=lambda q: q.name):
        for n, line in enumerate(p.read_text(encoding='utf-8').splitlines(), 1):
            if not line.strip(): continue
            row = json.loads(line)
            for key in ('text', 'question'):
                add('%s:%d:%s' % (p.name, n, key), row.get(key))
    for lang in classify.LANGS:
        for s in classify.load_all('sentences', lang):
            add('event_cross/data:' + s['id'], s['text'])
    return out


def edge_inputs():
    return [
        ('edge:empty', ['--text=']), ('edge:blanks', ['--text=   ']), ('edge:too_long', ['--text=' + 'あ' * 1001]),
        ('edge:exactly_1000', ['--text=' + 'あ' * 1000]), ('edge:control_char', ['--text=犬が\x01走った。']),
        ('edge:dash_start', ['--text=-犬が走った。']), ('edge:dashes_start', ['--text=--先生が笑った。']),
        ('edge:lang_mismatch', ['--text=犬が走った。', '--lang=en']), ('edge:lang_mismatch_2', ['--text=A dog ran.', '--lang=ja']),
        ('edge:bad_lang', ['--text=A dog ran.', '--lang=fr']), ('edge:no_text', []), ('edge:no_language', ['--text=1234']),
        ('edge:explicit_lang_ja', ['--text=犬が猫を追いかけた。', '--lang=ja']), ('edge:explicit_lang_en', ['--text=The dog chased the cat.', '--lang=en']),
        ('edge:newline', ['--text=犬が走った。\n猫が鳴いた。']), ('edge:tab', ['--text=犬が\t走った。']),
        ('edge:unknown_arg', ['--text=犬が走った。', '--bogus']),
        ('edge:abbrev_e', ['--text=犬が走った。', '--e']), ('edge:abbrev_ev', ['--text=犬が走った。', '--ev']),
        ('edge:abbrev_eve', ['--text=犬が走った。', '--eve']), ('edge:abbrev_event', ['--text=犬が走った。', '--event']),
    ]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    args = ap.parse_args(argv)
    rows = [{'id': src, 'argv': ['--text=' + t]} for src, t in texts()]
    rows += [{'id': i, 'argv': a} for i, a in edge_inputs()]
    Path(args.out).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    print('wrote %d inputs (%d from texts, %d edge)' % (len(rows), len(rows) - len(edge_inputs()), len(edge_inputs())))
    return 0


if __name__ == '__main__':
    sys.exit(main())
