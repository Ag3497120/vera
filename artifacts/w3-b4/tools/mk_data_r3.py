#!/usr/bin/env python3
"""W3-b4 round 3 (docs 10D, table change record 3): APPEND the ten sentences that the review of round 2 (F4, batches d and c) found misread by the rows place/で/PLACE of P_ACT,
P_CREATE and P_EMOTION, to tests/reading_soundness/ja_r10_w3b4.jsonl as refused rows. The first 323 rows are not rewritten (the tool checks the sha256 of the head and of the first 318 rows).
The expectation of a row is the one the reviewer froze before the run: `readable: false`. The fake placement of a row is the real answer of r7 for each word that a plan asks, except
the filler of the で phrase (右, 段差, 口), which is placed `direct` by a seed (the optimistic fake of W5-d): the review's misread appeared only that way (live, the adjunct gate 5 stops them).
Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-b4/tools/mk_data_r3.py --data tests/reading_soundness/ja_r10_w3b4.jsonl"""
import argparse
import hashlib
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mk_data_core as C

HEAD318 = '59d67eeae2f058b368cb519fc8d8fc7a8c695f78abb6f416e41519115a4cdfa0'     # artifacts/w3-b4/bank_freeze.sha256
HEAD323 = '8968c1a8fa416edf98575af85e6050f67a3e4af518cb68229b648c7e80502d9a'     # artifacts/w3-b4/r2/bank_freeze_after_r2.sha256
DIRECT_SEED = {'top': ['PLACE'], 'decided_by': ['seed']}
DE_NOTE = '(a) で+PLACE: place か instrument／cause か(レビュー r2 F4 束 %s の誤読。%s は r7 では腕が role@ だけなので、偽の配置で direct の PLACE にしたときだけ誤読した)'
NEW = [
    # (type key, number, text, predicate, fillers, de-filler, batch)
    ('ACT', 901, '兄が右で打った。', '打つ', ['兄', '右'], '右', 'd'),
    ('ACT', 902, '兄が右で皿を洗った。', '洗う', ['兄', '右', '皿'], '右', 'd'),
    ('ACT', 903, '兄が右で皿を拭いた。', '拭く', ['兄', '右', '皿'], '右', 'd'),
    ('ACT', 904, '兄が口で戦った。', '戦う', ['兄', '口'], '口', 'c'),
    ('CREATE', 901, '兄が右で絵を描いた。', '描く', ['兄', '右', '絵'], '右', 'd'),
    ('CREATE', 902, '弟が右で記事を書いた。', '書く', ['弟', '右', '記事'], '右', 'd'),
    ('CREATE', 903, '兄が口で絵を描いた。', '描く', ['兄', '口', '絵'], '口', 'c'),
    ('CREATE', 904, '兄が口で手紙を書いた。', '書く', ['兄', '口', '手紙'], '口', 'c'),
    ('EMOTION', 901, '兄が段差で驚いた。', '驚く', ['兄', '段差'], '段差', 'd'),
    ('EMOTION', 902, '兄が口で笑った。', '笑う', ['兄', '口'], '口', 'c'),
]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--data', required=True)
    a = ap.parse_args()
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign: print('ISOLATION FAILED', foreign); sys.exit(2)
    raw = open(a.data, 'rb').read()
    lines = raw.decode('utf-8').splitlines()
    assert len(lines) == 323, 'the file must have exactly the 323 frozen rows, has %d' % len(lines)
    assert hashlib.sha256(raw).hexdigest() == HEAD323, 'the 323 rows are not the frozen file'
    assert hashlib.sha256(('\n'.join(lines[:318]) + '\n').encode('utf-8')).hexdigest() == HEAD318, 'the first 318 rows are not the frozen file'
    have = {json.loads(l)['id'] for l in lines}
    inputs = {json.loads(l)['input'] for l in lines}
    for typ, n, text, pred, fill, de, batch in NEW:
        C.COUNT[(typ, 'A')] = n - 1
        C.add(typ, 'A', text, pred, None, fill, 'PLACEMENT_PARTICLE_NOT_IN_FRAME:P_%s:で' % typ, DE_NOTE % (batch, de),
              'review round 2, F4: misread by the registered place/で row; narrowed (docs 10D table change record 3)', 'P_' + typ, readable=False)
    rows = C.ROWS
    if C.ERRORS:
        for e in C.ERRORS: print('ERROR', e[:300])
        raise SystemExit('errors; nothing written')
    for r, (typ, n, text, pred, fill, de, batch) in zip(rows, NEW):
        assert r['id'] not in have and r['input'] not in inputs, r['id']
        r['placement'][de] = dict(DIRECT_SEED)
        assert r['path'] == 'U3', (r['id'], r['path'])
    with open(a.data, 'a', encoding='utf-8') as fh:
        for r in rows: fh.write(json.dumps(r, ensure_ascii=False) + '\n')
    print('appended=%d' % len(rows), [r['id'] for r in rows], [r['path'] for r in rows])


if __name__ == '__main__':
    main()
