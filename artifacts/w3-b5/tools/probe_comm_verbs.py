#!/usr/bin/env python3
"""W3-b5 round 2: which P_COMMUNICATE verbs whose r8 frame holds に:PLACE can carry a worst-case row (type 3 of the review: に is an organization that receives the information)?
For each of the 12 words of `generated_frames` (r8) with ptype P_COMMUNICATE and に:PLACE: the real r8 answer (state, origin, frame_status), the past form, and for four organizations the trigger path of the
sentence (U, U3 or none: the reader alone, no placement) and the two gates on the ending and on a derived head. Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-b5/tools/probe_comm_verbs.py --out TXT"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mk_core as C   # noqa: E402

VERBS = ['アップロードする', '呼び出せる', '届け出る', '投稿する', '掲示する', '案内する', '申し込める', '登壇する', '送付する', '通じる', '通ずる', '配信する']
ORGS = ('警察署', '区役所', '営業所', '公民館')


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    out = []
    for v in VERBS:
        fr = C.r8_frame_row(v); ans = C.r8_answer(v)
        out.append('%s\t%s\tに=%s\t%s %s %s\tpast=%s' % (v, fr['ptype'] if fr else None, fr['frame'].get('に') if fr else None, ans['state'], ans.get('origin'), ans.get('frame_status'), C.past(v)))
        p = C.past(v)
        if p is None: continue
        for org in ORGS:
            t = '兄が%sに%s。' % (org, p)
            path, f = C.path_of(t)
            out.append('\t%s\tpath=%s tail=%s derived=%s predicate=%s' % (t, path, f['tail_gate'], f['derived_gate'], f['predicate']))
    open(a.out, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print('\n'.join(out[:6]))


if __name__ == '__main__':
    main()
