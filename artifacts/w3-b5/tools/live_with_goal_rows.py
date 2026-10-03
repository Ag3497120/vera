#!/usr/bin/env python3
"""W3-b5 round 2: what the REAL placement r8 (not a fake) does with the two goal rows of table change record 1 put back and with the table as it is now.

Two groups of sentences go through `semantic_read.read(text, placement=<r8 directory>)`:
  * the 32 rows appended in round 2 (their predicates are estimated in r8, so the real entry stops at the predicate: the number that the real entry reads is part of the finding);
  * live probes: 旅行する (a DIRECT NOT_CONFIRMED predicate in r8 whose frame holds に:PLACE) with a purpose / event noun that r8 types PLACE, written here (not part of the frozen data); the design says the
    に phrase is the purpose, so a reading is a misread. Three goal sentences of the frozen data (the control: 旅行する + a place) show what the two rows did read.
Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-b5/tools/live_with_goal_rows.py --out TXT   (the r8 directory is fixed below, read only)"""
import argparse
import json
import os
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parents[3]
R8 = '/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2'
GOAL_ROWS = {'P_MOVE': (('goal', ('に',), ('PLACE',), 'arg'),), 'P_COMMUNICATE': (('goal', ('に',), ('PLACE',), 'arg'),), 'P_ACT': (), 'P_CREATE': (), 'P_EMOTION': ()}
PROBES = [('兄が遠足に旅行した。', 'purpose'), ('姉が展覧会に旅行した。', 'purpose'), ('妹が花火大会に旅行した。', 'purpose'), ('弟がお祭りに旅行した。', 'purpose'), ('先生が神社参拝に旅行した。', 'purpose'),
          ('先生が北海道に旅行した。', 'control_goal'), ('店員が沖縄に旅行した。', 'control_goal'), ('係員が京都に旅行した。', 'control_goal')]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    from verantyx import semantic_read as SR, semantic_reader as R
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    assert not foreign, foreign
    rows = [json.loads(l) for l in (TREE / 'tests' / 'reading_soundness' / 'ja_r11.jsonl').read_text(encoding='utf-8').splitlines() if l.strip()][617:]
    items = [(r['input'], 'round2:' + r['id']) for r in rows] + [(t, 'probe:' + k) for t, k in PROBES]
    now = dict(R.TYPED_FRAMES_FRAME_REQUIRED_W3B5)
    lines, tot = [], {}
    for label, table in (('two_goal_rows_put_back', GOAL_ROWS), ('table_as_it_is', now)):
        R.TYPED_FRAMES_FRAME_REQUIRED_W3B5 = table
        read = {'round2': [], 'probe:purpose': [], 'probe:control_goal': []}
        for text, tag in items:
            out = SR.read(text, placement=R8)
            if out['readable']:
                roles = out['clauses'][0]['roles']
                read['round2' if tag.startswith('round2') else tag].append('%s\t%s\t%s' % (tag, text, json.dumps(roles, ensure_ascii=False)))
        lines.append('== %s (the real r8; DIRECT NOT_CONFIRMED predicates only can be read through a frame)' % label)
        for k, v in read.items():
            lines.append('%s: read %d of %d' % (k, len(v), sum(1 for t, g in items if (g.startswith('round2') if k == 'round2' else g == k))))
            lines += ['  ' + x for x in v]
    R.TYPED_FRAMES_FRAME_REQUIRED_W3B5 = now
    Path(a.out).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))


if __name__ == '__main__':
    main()
