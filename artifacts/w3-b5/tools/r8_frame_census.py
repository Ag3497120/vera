#!/usr/bin/env python3
"""W3-b5 step 2: census of the generated frames of a placement (r8 or r7).
Every word of the table `generated_frames` goes through `coarse_place.query(word, placement=...)`; the words are counted by
(state, origin, predicate type of the answer, frame_status, has gen_definition) and the words that hold `で:PLACE` / `に:{PERSON,GROUP_ORG,PLACE,TIME}` are listed
(every `direct` word; the `estimated` words by predicate type, as counts and the first ones). Also written: `frames_by_type` (predicate type -> particle -> noun type -> words),
for the choice of the predicates of the data (only the DECIDED direct words are listed with their frame_status).
The sqlite is opened read-only (uri mode=ro). Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-b5/tools/r8_frame_census.py --placement DIR --out TXT [--json JSON]
"""
import argparse
import collections
import json
import os
import sqlite3
import sys


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--placement', required=True); ap.add_argument('--out', required=True); ap.add_argument('--json', default=None)
    a = ap.parse_args()
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    from verantyx import coarse_place as CP
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None)
               and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign:
        print('ISOLATION FAILED', foreign); sys.exit(2)
    con = sqlite3.connect('file:%s?mode=ro' % os.path.join(a.placement, 'placement.sqlite'), uri=True)
    rows = con.execute('SELECT word, ptype, frame FROM generated_frames ORDER BY word').fetchall()
    cnt = collections.Counter(); ptype_gf_vs_answer = collections.Counter()
    part = collections.defaultdict(lambda: collections.defaultdict(list))      # (origin, answer type) -> 'で:PLACE' -> [words]
    by_type = {}
    direct_rows = []
    for word, gptype, frame in rows:
        r = CP.query(word, placement=a.placement)
        top = (r.get('top') or [None])[0]
        has_def = 'gen_definition' in (r.get('decided_by') or [])
        cnt[(r['state'], r.get('origin'), top, r.get('frame_status'), 'gen_def' if has_def else 'no_gen_def')] += 1
        ptype_gf_vs_answer[(r['state'], r.get('origin'), 'same' if top == gptype else 'different')] += 1
        fr = json.loads(frame)
        for p, ts in fr.items():
            for t in ts:
                by_type.setdefault(gptype, {}).setdefault(p, {}).setdefault(t, []).append(
                    {'word': word, 'state': r['state'], 'origin': r.get('origin'), 'answer_top': top, 'frame_status': r.get('frame_status'), 'gen_definition': has_def})
        keys = [k for k in ('で:PLACE', 'に:PERSON', 'に:GROUP_ORG', 'に:PLACE', 'に:TIME') if k.split(':')[0] in fr and k.split(':')[1] in fr[k.split(':')[0]]]
        for k in keys:
            part[(r.get('origin'), top)][k].append((word, r.get('frame_status')))
        if r['state'] == 'DECIDED' and r.get('origin') == 'direct': direct_rows.append((word, top, r.get('frame_status'), fr))
    out = ['placement: %s' % a.placement, 'generated_frames words: %d' % len(rows), '',
           '# (state, origin, answer predicate type, frame_status, gen_definition) -> number of words']
    for k, v in sorted(cnt.items(), key=lambda kv: (str(kv[0]), kv[1])): out.append('%s\t%d' % (' | '.join(str(x) for x in k), v))
    out += ['', '# (state, origin) -> by(table ptype == answer type)']
    for k, v in sorted(ptype_gf_vs_answer.items(), key=lambda kv: str(kv[0])): out.append('%s\t%d' % (' | '.join(str(x) for x in k), v))
    out += ['', '# (state, origin) -> words']
    agg = collections.Counter()
    for (s, o, t, f, g), n in cnt.items(): agg[(s, o)] += n
    for k, v in sorted(agg.items(), key=lambda kv: str(kv[0])): out.append('%s | %s\t%d' % (k[0], k[1], v))
    out += ['', '# words that hold a particle:type of the licensed rows, by (origin, answer type): count']
    for k in sorted(part, key=str):
        for key in sorted(part[k]): out.append('%s\t%s\t%d' % (' | '.join(str(x) for x in k), key, len(part[k][key])))
    out += ['', '# DECIDED direct words that hold a particle:type of the rows: word (frame_status)']
    for k in sorted(part, key=str):
        if k[0] != 'direct': continue
        for key in sorted(part[k]): out.append('%s\t%s\t%s' % (k[1], key, ' '.join('%s(%s)' % (w, s) for w, s in part[k][key])))
    out += ['', '# DECIDED estimated words that hold them: the first 12 by (answer type, particle:type)']
    for k in sorted(part, key=str):
        if k[0] != 'estimated': continue
        for key in sorted(part[k]): out.append('%s\t%s\t%d\t%s' % (k[1], key, len(part[k][key]), ' '.join(w for w, s in part[k][key][:12])))
    open(a.out, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    if a.json: open(a.json, 'w', encoding='utf-8').write(json.dumps(by_type, ensure_ascii=False, indent=1, sort_keys=True) + '\n')
    print('words=%d direct_decided=%d' % (len(rows), len(direct_rows)))


if __name__ == '__main__':
    main()
