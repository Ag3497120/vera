#!/usr/bin/env python3
"""補助測定の要約: qa_probe.py の出力(dev と修正後、seed ごと)を突き合わせる。受入基準ではない。
使い方: python qa_summary.py [--dir artifacts/w1-a] > artifacts/w1-a/qa_probe_summary.txt
"""
import argparse, collections, json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--dir', default='artifacts/w1-a'); d = Path(ap.parse_args().dir)
    for seed in (7, 101):
        dev = json.loads((d / f'qa_probe_dev_seed{seed}.json').read_text(encoding='utf-8'))
        aft = json.loads((d / f'qa_probe_after_seed{seed}.json').read_text(encoding='utf-8'))
        key = lambda r: (r['ph'], r['s'], r['q'])
        da = {key(r): r for r in dev}; aa = {key(r): r for r in aft}
        cd, ca = collections.Counter(r['st'] for r in dev), collections.Counter(r['st'] for r in aft)
        lost = [k for k in da if da[k]['st'] == 'correct' and aa.get(k, {}).get('st') != 'correct']
        won = [k for k in da if da[k]['st'] != 'correct' and aa.get(k, {}).get('st') == 'correct']
        causative = [k for k in lost if 'させ' in k[1] or '使役' in k[0]]
        print(f"seed {seed}: dev {dict(cd)} / after {dict(ca)} / correct->not-correct {len(lost)} (うち使役系 {len(causative)}) / not-correct->correct {len(won)}")
        newly_wrong = [k for k in da if da[k]['st'] != 'wrong' and aa.get(k, {}).get('st') == 'wrong']
        for k in newly_wrong:
            r = aa[k]
            print(f"   new wrong-graded: {k[0]} | {k[1]} | {k[2]} | gold={r['gold']} ans={r['vals']}")


if __name__ == '__main__':
    main()
