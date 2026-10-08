#!/usr/bin/env python3
"""W3-c7: tests/reading_soundness/w3c7_placement_r9.jsonl = the answers of the REAL placement (CoarseQuery(DIR).query), recorded as they came, for every word that the entry asked
while reading every row of the data files. Nothing is written by hand. Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-c7/tools/mk_fixture.py --placement DIR --data A,B --out FILE"""
import argparse, copy, json, os, sys
from pathlib import Path
TREE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(TREE))


class Rec:
    def __init__(self, inner, store): self.inner, self.store = inner, store
    id = 'rec'
    def query(self, term):
        a = self.inner.query(term)
        self.store.setdefault(term, copy.deepcopy(a))
        return a


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--placement', required=True); ap.add_argument('--data', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    from verantyx import semantic_read as SR, semantic_reader as R, constructions
    constructions.discover()
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    if [m for k, m in sys.modules.items() if k.startswith('verantyx') and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]:
        print('ISOLATION FAILED'); sys.exit(2)
    store = {}
    real = R.CoarseQuery(a.placement)
    for path in a.data.split(','):
        for l in Path(path).read_text(encoding='utf-8').splitlines():
            if not l.strip(): continue
            r = json.loads(l)
            SR.read(r['input'], r['lang'], placement=Rec(real, store))
            R.w3c7_explain_ja(r['input'], Rec(real, store))
    Path(a.out).write_text(''.join(json.dumps({'term': t, 'answer': store[t]}, ensure_ascii=False, sort_keys=True) + '\n' for t in sorted(store)), encoding='utf-8')
    print('terms=%d' % len(store))


if __name__ == '__main__':
    main()
