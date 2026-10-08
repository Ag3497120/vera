#!/usr/bin/env python3
"""W3-b4 round 2 (docs 10D, table change records 1 and 2): APPEND the five sentences that the review of round 1 (F4) found misread to tests/reading_soundness/ja_r10_w3b4.jsonl as
refused rows. The first 318 rows are not rewritten (the file is only appended to; the tool checks that the head is the frozen file). The expectation of a row is the one the reviewer froze
before the run: `readable: false`. The fake placement of a row is built like the others (the real answer of r7 for each word that a plan asks), except where the review's misread
appeared only with a filler placed `direct` by a seed (the optimistic fake of W5-d: every DECIDED answer direct, decided_by ['seed']): there the word's answer is written that way.
Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-b4/tools/mk_data_r2.py --data tests/reading_soundness/ja_r10_w3b4.jsonl"""
import argparse
import hashlib
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mk_data_core as C

FROZEN_HEAD_SHA = '59d67eeae2f058b368cb519fc8d8fc7a8c695f78abb6f416e41519115a4cdfa0'      # artifacts/w3-b4/bank_freeze.sha256 (318 rows)
DIRECT_SEED = {'top': ['PLACE'], 'decided_by': ['seed']}
NEW = [
    # (type key, number, text, predicate, fillers, reason, construction, fake override {word: spec})
    ('CHANGE', 901, '会社が工場から店へ変わった。', '変わる', ['会社', '工場', '店'], '(a) へ+PLACE: goal か result か(result の型は PLACE も取る。レビュー r1 F4 の誤読)', {}),
    ('CHANGE', 902, 'チームが広場から体育館へ変わった。', '変わる', ['チーム', '広場', '体育館'], '(a) へ+PLACE: goal か result か(レビュー r1 F4 の誤読)', {}),
    ('CHANGE', 903, '兄が田舎から都会へ変わった。', '変わる', ['兄', '田舎', '都会'], '(a) へ+PLACE: goal か result か(レビュー r1 F4 の誤読)', {}),
    ('CHANGE', 904, '学校が校舎から仮校舎へ変わった。', '変わる', ['学校', '校舎', '仮校舎'], '(a) へ+PLACE: goal か result か(レビュー r1 F4 の誤読。仮校舎 は r7 では推定なので、偽の配置で direct の PLACE にしたときだけ誤読した)',
     {'仮校舎': DIRECT_SEED}),
    ('CONSUME', 901, '兄が休みに金を使った。', '使う', ['兄', '休み', '金'], '(a) に+TIME: time か使い道か(使い道は規約に役割が無い。レビュー r1 F4 の誤読。休み は r7 では role@ の腕だけなので、偽の配置で direct の TIME にしたときだけ誤読した)',
     {'休み': {'top': ['TIME'], 'decided_by': ['seed']}}),
]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--data', required=True)
    a = ap.parse_args()
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign: print('ISOLATION FAILED', foreign); sys.exit(2)
    raw = open(a.data, 'rb').read()
    lines = raw.decode('utf-8').splitlines()
    if len(lines) == 318: assert hashlib.sha256(raw).hexdigest() == FROZEN_HEAD_SHA, 'the head is not the frozen file'
    have = {json.loads(l)['id'] for l in lines}
    inputs = {json.loads(l)['input'] for l in lines}
    for typ, n, text, pred, fill, cons, over in NEW:
        C.COUNT[(typ, 'A')] = n - 1
        C.add(typ, 'A', text, pred, None, fill, 'PLACEMENT_FRAME_NOT_READ:P_' + typ, cons, 'review round 1, F4: misread by the registered table; narrowed (docs 10D table change records 1 and 2)', 'P_' + typ, readable=False)
    rows = C.ROWS
    if C.ERRORS:
        for e in C.ERRORS: print('ERROR', e[:300])
        raise SystemExit('errors; nothing written')
    for r, (typ, n, text, pred, fill, cons, over) in zip(rows, NEW):
        assert r['id'] not in have and r['input'] not in inputs, r['id']
        for w, spec in over.items(): r['placement'][w] = spec
    with open(a.data, 'a', encoding='utf-8') as fh:
        for r in rows: fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    print('appended=%d' % len(rows), [r['id'] for r in rows], [r['path'] for r in rows])


if __name__ == '__main__':
    main()
