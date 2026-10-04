"""Data check for extra2 (W3-c4 round 2): the lines of every document FILE equal the lines `document_loaders.load_path` reads, every document has one sentence per line,
and every evidence id of every question names an existing line (`<file>#<line>:1`). Prints one line per document; exit 1 on a mismatch."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[3]))
from verantyx import document_loaders as DL    # noqa: E402


def main():
    bad, lines = 0, {}
    for p in sorted((HERE / 'docs').glob('*.txt')):
        raw = p.read_text(encoding='utf-8').split('\n')
        res = DL.load_path(str(p))
        loaded = res['document'].text.split('\n') if res['verdict'] == 'ANSWER' else None
        ok = loaded == raw
        one_per_line = all(sum(l.count(c) for c in '。') + (1 if l.endswith('.') else 0) <= 1 for l in raw)
        lines[p.name] = len([l for l in raw if l])
        print(p.name, 'lines', lines[p.name], 'loaded-same' if ok else 'LOAD-DIFFERS', 'one-sentence-per-line' if one_per_line else 'MULTI-SENTENCE-LINE')
        bad += (not ok) + (not one_per_line)
    n = 0
    for l in (HERE / 'questions.jsonl').read_text(encoding='utf-8').splitlines():
        q = json.loads(l)
        for ev in q['truth']['evidence']:
            name, rest = ev.split('#'); line, k = rest.split(':')
            if name not in lines or not (1 <= int(line) <= lines[name]) or k != '1': print('BAD EVIDENCE', q['id'], ev); bad += 1
            n += 1
    print('evidence ids checked', n, 'bad', bad)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
