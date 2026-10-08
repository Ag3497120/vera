#!/usr/bin/env python3
"""W3-c7 measurement tool (not a product file): every line of --inputs through semantic_read.read, one JSON line each.

  --placement none | DIR   none: placement=None; DIR: the real placement (CoarseQuery(DIR))
  --queries FILE           with a placement: the words each sentence asked, as a JSON list of lists (same order as the input)
A ReadError becomes {"text":..., "error": code, "message": ...}. Loaded verantyx* modules must be under PYTHONPATH (else exit 2).
Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-c7/tools/entry_dump.py --inputs F --placement none|DIR --out OUT.jsonl [--queries OUT.json]
"""
import argparse
import json
import os
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(TREE))


def isolation():
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.'))
               and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign:
        print('ISOLATION FAILED', foreign)
        sys.exit(2)


class Recording:
    """Wraps a placement: the same answers go through, the words asked are recorded."""
    def __init__(self, inner):
        self.inner, self.calls = inner, []

    def query(self, term):
        self.calls.append(term)
        return self.inner.query(term)

    @property
    def id(self):
        return getattr(self.inner, 'id', None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--inputs', required=True)
    ap.add_argument('--placement', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--queries')
    a = ap.parse_args()
    from verantyx import semantic_read as SR, semantic_reader as R, constructions
    constructions.discover()
    isolation()
    lines = [l.rstrip('\n') for l in Path(a.inputs).read_text(encoding='utf-8').splitlines() if l.strip()]
    inner = None if a.placement == 'none' else R.CoarseQuery(a.placement)
    if a.queries and inner is None:
        print('--queries needs a placement')
        sys.exit(2)
    out_lines, asked = [], []
    for text in lines:
        rec = Recording(inner) if inner is not None else None
        try:
            out = SR.read(text, placement=rec if rec is not None else None)
        except SR.ReadError as e:
            out = {'text': text, 'error': getattr(e, 'code', type(e).__name__), 'message': str(e)}
        out_lines.append(json.dumps(out, ensure_ascii=False, sort_keys=True))
        asked.append(rec.calls if rec is not None else [])
    Path(a.out).write_text('\n'.join(out_lines) + '\n', encoding='utf-8')
    if a.queries:
        Path(a.queries).write_text(json.dumps(asked, ensure_ascii=False) + '\n', encoding='utf-8')
    print('rows=%d' % len(out_lines))


if __name__ == '__main__':
    main()
