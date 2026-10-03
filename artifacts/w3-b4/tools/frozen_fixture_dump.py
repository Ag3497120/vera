#!/usr/bin/env python3
"""W3-b4 step 11: the frozen data (ja, ja_r2..r6, ja_r8..r10 (W3-b1 and W3-b2 data), en, en_r2, en_r4, table7, w3b2_*; NOT ja_r10_w3b4 and not the a3 question files) through the entry with the fake
placements the earlier tickets wrote for them (`w3b1_fakes.FixtureQuery`, `w3b2_fakes.FixtureQuery`), one JSON line per (file, row, fake): the output and the diagnosis `typed_explain_ja`.
Run once in the base tree and once in this tree (--tree), then compare with frozen_fixture_compare.py. Usage: cd <tree> && PYTHONPATH=<tree> python <this file> --tree <tree> --out FILE"""
import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

FILES = ('ja.jsonl', 'ja_r2.jsonl', 'ja_r3.jsonl', 'ja_r4.jsonl', 'ja_r5.jsonl', 'ja_r6.jsonl', 'ja_r8.jsonl', 'ja_r9.jsonl', 'ja_r10.jsonl', 'table7.jsonl',
         'en.jsonl', 'en_r2.jsonl', 'en_r4.jsonl', 'w3b2_determiner.jsonl', 'w3b2_frame.jsonl', 'w3b2_multiple.jsonl', 'w3b2_no.jsonl')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path)); mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; spec.loader.exec_module(mod); return mod


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--tree', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    tree = Path(a.tree).resolve(); rs = tree / 'tests' / 'reading_soundness'
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    if root != str(tree):
        print('PYTHONPATH is not the tree', root, tree); sys.exit(2)
    from verantyx import semantic_read as SR
    F1 = load('w3b1_fakes_ff', rs / 'w3b1_fakes.py'); F2 = load('w3b2_fakes_ff', rs / 'w3b2_fakes.py')
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None)
               and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign: print('ISOLATION FAILED', foreign); sys.exit(2)
    out = []
    for name in FILES:
        for line in (rs / name).read_text(encoding='utf-8').splitlines():
            if not line.strip(): continue
            r = json.loads(line)
            text, lang = r.get('input') or r.get('text'), r.get('lang')
            for fake_name, F in (('w3b1', F1), ('w3b2', F2)):
                try: res = SR.read(text, lang, placement=F.FixtureQuery())
                except Exception as e: res = {'error': type(e).__name__ + ':' + str(e)}
                try: ex = SR.typed_explain_ja(text, F.FixtureQuery()) if (lang or 'ja') == 'ja' else None
                except Exception as e: ex = {'error': type(e).__name__}
                out.append({'file': name, 'id': r.get('id'), 'fake': fake_name, 'text': text, 'out': res, 'explain': ex})
    Path(a.out).write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in out), encoding='utf-8')
    print('rows=%d' % len(out))


if __name__ == '__main__':
    main()
