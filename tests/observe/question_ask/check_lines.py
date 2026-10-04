"""Data check (W3-c4): for every document, the lines of the FILE equal the lines of the text `document_loaders.load_path` gives (a `# ` heading mark aside),
so that the line of a sentence id means the same in both. Also: every evidence id of every question names a line that exists in the file and a k-th piece that
exists, counted by a hand-written cutter (str methods, not the product's regular expression). Prints one line per document and the result; exit 1 on a mismatch."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parents[2]
sys.path.insert(0, str(TREE))
from verantyx import document_loaders as DL    # noqa: E402


def pieces(line):
    out, cur, i = [], '', 0
    while i < len(line):
        ch = line[i]
        cur += ch
        if ch == '。' or (ch == '.' and i + 1 < len(line) and line[i + 1].isspace()):
            out.append(cur); cur = ''
        i += 1
    out.append(cur)
    return [p.strip() for p in out if p.strip()]


def doc_files(root):
    return sorted(p for p in root.rglob('*.txt'))


def main():
    bad = 0
    files = {}
    for root in (HERE / 'docs', HERE / 'b2like' / 'docs', HERE / 'w3c2'):
        for p in doc_files(root):
            raw = p.read_text(encoding='utf-8')
            res = DL.load_path(str(p))
            if res['verdict'] != 'ANSWER':
                print('NOT LOADED', p, res['verdict']); bad += 1; continue
            loaded = res['document'].text.split('\n')
            want = [(l[2:] if l.startswith('# ') else l) for l in raw.split('\n')]
            while loaded and loaded[-1] == '': loaded.pop()    # the final newline of the file is not a line (it does not move the number of any sentence)
            while want and want[-1] == '': want.pop()
            ok = loaded == want
            print('%-28s file_lines=%d loaded_lines=%d %s' % (p.relative_to(HERE), len(want), len(loaded), 'SAME' if ok else 'DIFFERENT'))
            if not ok:
                bad += 1
                for i, (a, b) in enumerate(zip(want, loaded), 1):
                    if a != b: print('   first difference at line %d: file=%r loaded=%r' % (i, a, b)); break
            files[p.name] = raw.split('\n')
    n_ids = 0
    for qf in (HERE / 'questions.jsonl', HERE / 'b2like' / 'questions.jsonl', HERE / 'w3c2' / 'questions.jsonl', HERE / 'w3c2' / 'questions_corrected.jsonl'):
        for l in qf.read_text(encoding='utf-8').splitlines():
            if not l.strip(): continue
            q = json.loads(l)
            for sid in q['truth']['evidence'] + q['truth'].get('extension_support', []):
                n_ids += 1
                name, rest = sid.split('#'); ln, k = rest.split(':')
                lines = files.get(name)
                if lines is None or int(ln) > len(lines) or int(k) > len(pieces(lines[int(ln) - 1] if int(ln) - 1 < len(lines) else '')):
                    print('BAD ID', q['id'], sid); bad += 1
    print('evidence ids checked: %d' % n_ids)
    print('RESULT: %s' % ('OK' if not bad else 'MISMATCH %d' % bad))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
