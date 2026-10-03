#!/usr/bin/env python3
"""W3-b4: what the placement r7 (read only) answers for words, so that the fake placements of the data are not in contradiction with it.
For each word of --in (one per line): state, origin, top, decided_by, frame_status, and whether the answer passes the evidence gate of K62 (`placement_type`) as a plain term and as an
adjunct. Placement facts only; nothing here reads a sentence. Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-b4/tools/r7_words.py --placement DIR --in FILE --out TSV
"""
import argparse
import json
import os
import sys


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--placement', required=True); ap.add_argument('--in', dest='inp', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--json', default=None)
    a = ap.parse_args()
    from verantyx import coarse_place, semantic_reader as R
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None)
               and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign:
        print('ISOLATION FAILED', foreign); sys.exit(2)
    words = [l.strip() for l in open(a.inp, encoding='utf-8') if l.strip() and not l.startswith('#')]
    out = ['word\tstate\torigin\ttop\tdecided_by\tframe_status\tgate_plain\tgate_adjunct']
    dump = {}
    for w in words:
        q = coarse_place.query(w, placement=a.placement)
        t0, why0 = R.placement_type(q)
        t1, why1 = R.placement_type(q, adjunct=True)
        out.append('\t'.join([w, str(q['state']), str(q['origin']), '+'.join(q['top']), '+'.join(q.get('decided_by') or []), str(q.get('frame_status')),
                              t0 or why0, t1 or why1]))
        dump[w] = q
    open(a.out, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    if a.json: open(a.json, 'w', encoding='utf-8').write(json.dumps(dump, ensure_ascii=False, indent=1, sort_keys=True))
    print('words=%d' % len(words))


if __name__ == '__main__':
    main()
