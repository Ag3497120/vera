#!/usr/bin/env python3
"""W3-b4 round 4 (docs 10D K186): APPEND the six sentences that the review of round 3 (F4, batches f and g) found misread through the row goal/へ of P_ACT, to
tests/reading_soundness/ja_r10_w3b4.jsonl as refused rows. The first 333 rows are not rewritten (the tool checks the sha256 of the whole file and of its first 323 and 318 rows).
The expectation of a row was fixed before the run: `readable: false`, and the diagnosis of the plan of W3-b4 is the reason of the gate of K186. The placement of a row is the real
answer of r7 for each word a plan asks (mk_data_core.add builds it; nothing is lifted to a seed): the review's misread appeared with the live r7.
Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-b4/tools/mk_data_r4.py --data tests/reading_soundness/ja_r10_w3b4.jsonl"""
import argparse
import hashlib
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mk_data_core as C

HEAD318 = '59d67eeae2f058b368cb519fc8d8fc7a8c695f78abb6f416e41519115a4cdfa0'     # artifacts/w3-b4/bank_freeze.sha256
HEAD323 = '8968c1a8fa416edf98575af85e6050f67a3e4af518cb68229b648c7e80502d9a'     # artifacts/w3-b4/r2/bank_freeze_after_r2.sha256
HEAD333 = '455a217c08daa7eab70e8252dc7a2ce03d2f2c5786c76f4a321d971138568c5c'     # artifacts/w3-b4/r3/bank_freeze_after_r3.sha256
GATE = 'PLACEMENT_FOCUS_PARTICLE_AFTER_CASE:へ:%s'
CONS = '(e) へ+係助詞・副助詞: 格助詞の後ろの助詞が読みに現れない(K180)。レビュー W3-b4-2 r1 束 f/g の誤読(live の r7 で goal 倉庫 と読まれた)'
NOTE = 'review W3-b4-2 round 1, F4 batches f/g: misread through the goal/へ row of P_ACT (K180); refused by the gate of K186'
NEW = [
    # (number, text, particle after へ)
    (911, '兄が台車を倉庫へさえ押した。', 'さえ'),
    (912, '兄が台車を倉庫へすら押した。', 'すら'),
    (913, '兄が台車を倉庫へこそ押した。', 'こそ'),
    (914, '兄が台車を倉庫へまで押した。', 'まで'),
    (915, '兄が台車を倉庫へなど押した。', 'など'),
    (916, '兄が台車を倉庫へさえ押さなかった。', 'さえ'),
]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--data', required=True)
    a = ap.parse_args()
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign: print('ISOLATION FAILED', foreign); sys.exit(2)
    raw = open(a.data, 'rb').read()
    lines = raw.decode('utf-8').splitlines()
    assert len(lines) == 333, 'the file must have exactly the 333 frozen rows, has %d' % len(lines)
    assert hashlib.sha256(raw).hexdigest() == HEAD333, 'the 333 rows are not the frozen file'
    assert hashlib.sha256(('\n'.join(lines[:323]) + '\n').encode('utf-8')).hexdigest() == HEAD323, 'the first 323 rows are not the frozen file'
    assert hashlib.sha256(('\n'.join(lines[:318]) + '\n').encode('utf-8')).hexdigest() == HEAD318, 'the first 318 rows are not the frozen file'
    have = {json.loads(l)['id'] for l in lines}
    inputs = {json.loads(l)['input'] for l in lines}
    for n, text, part in NEW:
        C.COUNT[('ACT', 'A')] = n - 1
        C.add('ACT', 'A', text, '押す', None, ['兄', '台車', '倉庫'], GATE % part, CONS, NOTE, 'P_ACT', readable=False)
    rows = C.ROWS
    if C.ERRORS:
        for e in C.ERRORS: print('ERROR', e[:300])
        raise SystemExit('errors; nothing written')
    for r, (n, text, part) in zip(rows, NEW):
        assert r['id'] == 'W3B4-ACT-A-%03d' % n and r['input'] == text, (r['id'], r['input'])
        assert r['id'] not in have and r['input'] not in inputs, r['id']
        assert r['path'] == 'U', (r['id'], r['path'])
    with open(a.data, 'a', encoding='utf-8') as fh:
        for r in rows: fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    print('appended=%d' % len(rows), [r['id'] for r in rows], [r['path'] for r in rows])


if __name__ == '__main__':
    main()
