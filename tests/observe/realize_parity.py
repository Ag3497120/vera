"""O8: the existing realizer's output is unchanged by the W3-c additions.

The module body of `verantyx/semantic_realize.py` at the base commit is written to a file (artifacts/w3-c/tmp/) and loaded as
`verantyx._w3c_base_semantic_realize` (inside the package, so its relative imports resolve). For every Japanese sentence of the W3-b and
W3-c test data, every clause the reader finds is realized with the base module and with the current one (`realize_clause` plain and
polite, `realize_variants`), and the `as_dict()` forms are compared.

    python tests/observe/realize_parity.py --base 5cae978 --out artifacts/w3-c/o8_realize_parity.txt
"""
import argparse
import hashlib
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TREE))


def sentences():
    files = sorted((TREE / 'tests' / 'event_cross' / 'data').glob('sentences_ja*.jsonl')) + sorted((TREE / 'tests' / 'observe' / 'data').glob('seeds_ja*.jsonl'))
    out = []
    for f in files:
        for line in f.read_text(encoding='utf-8').splitlines():
            if line.strip():
                out.append((f.name, json.loads(line)['text']))
    return out, [f.name for f in files]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--tmpdir', default=str(TREE / 'artifacts' / 'w3-c' / 'tmp'))
    args = ap.parse_args(argv)
    body = subprocess.run(['git', '-C', str(TREE), 'show', '%s:verantyx/semantic_realize.py' % args.base], capture_output=True, check=True).stdout
    tmp = Path(args.tmpdir)
    tmp.mkdir(parents=True, exist_ok=True)
    base_file = tmp / 'base_semantic_realize.py'
    base_file.write_bytes(body)
    spec = importlib.util.spec_from_file_location('verantyx._w3c_base_semantic_realize', base_file)
    base = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = base
    spec.loader.exec_module(base)
    from verantyx import semantic_realize as cur
    from verantyx.semantic_reader import document_view

    texts, files = sentences()
    checked = mismatch = clauses = 0
    bad = []
    for fname, text in texts:
        checked += 1
        try:
            view = document_view({'x': text})
        except Exception as exc:    # the reader raising is the same for both modules: not part of this comparison
            continue
        for clause in view.clauses:
            clauses += 1
            for what, fa, fb in (('plain', lambda m: m.realize_clause(clause, 'plain').as_dict(), None),
                                 ('polite', lambda m: m.realize_clause(clause, 'polite').as_dict(), None),
                                 ('variants', lambda m: [r.as_dict() for r in m.realize_variants(clause)], None)):
                a, b = fa(base), fa(cur)
                if json.dumps(a, sort_keys=True, ensure_ascii=False, default=str) != json.dumps(b, sort_keys=True, ensure_ascii=False, default=str):
                    mismatch += 1
                    bad.append({'file': fname, 'text': text, 'what': what})
    lines = ['checked %d, mismatch %d' % (checked, mismatch),
             'clauses_compared %d (each with realize_clause plain, realize_clause polite, realize_variants)' % clauses,
             'files %s' % ', '.join(files),
             'base_commit %s' % args.base,
             'base_semantic_realize_sha256 %s' % hashlib.sha256(body).hexdigest()]
    lines += ['MISMATCH %s' % json.dumps(b, ensure_ascii=False) for b in bad]
    Path(args.out).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    return 0 if mismatch == 0 and checked > 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
