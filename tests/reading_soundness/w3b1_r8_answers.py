#!/usr/bin/env python3
"""W3-b1 手順 4: 検査データ ja_r8.jsonl の作成に使った語の、配置の問い合わせの答えを残す(読解器・入口は使わない)。

語 = 期待の節の述語・役割の値・must_not の値(の で割った断片も)。答えは `coarse_place.query(語, placement=<配置>)` の state・origin・estimate_basis・top・decided_by の腕の名前
(配置のパスは書かず content_sha256 だけ)。使い方: cd <木> && PYTHONPATH=<木> python tests/reading_soundness/w3b1_r8_answers.py --placement DIR --out FILE
"""
import argparse, json, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--placement', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    from verantyx import coarse_place
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.'))
               and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    print('tree=' + root)
    if foreign: print('ISOLATION FAILED', foreign); sys.exit(2)
    terms = set()
    for line in (HERE / 'ja_r8.jsonl').read_text(encoding='utf-8').splitlines():
        r = json.loads(line)
        for c in r['expect']['clauses']:
            terms.add(c['predicate'])
            for v in c['roles'].values(): terms.add(v); terms.update(x for x in v.split('の') if x)
        for m in r['expect']['must_not']:
            v = m.get('value')
            if isinstance(v, str): terms.add(v); terms.update(x for x in v.split('の') if x)
    rows = []
    for t in sorted(terms):
        ans = coarse_place.query(t, placement=a.placement)
        rows.append({'term': t, 'state': ans['state'], 'origin': ans['origin'], 'estimate_basis': ans['estimate_basis'], 'top': ans['top'],
                     'decided_by': ans.get('decided_by'), 'namespace': ans.get('namespace'), 'content_sha256': (ans.get('placement') or {}).get('content_sha256')})
    Path(a.out).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
    print('terms=%d out=%s' % (len(rows), a.out))


if __name__ == '__main__':
    main()
