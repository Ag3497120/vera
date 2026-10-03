#!/usr/bin/env python3
"""W3-b5 step 11 (L1): every word of the table `generated_frames` of a placement (r8: 8,030; r7: 4,788) and 200 headwords more (nouns, seed predicates) go through `coarse_place.query` of this
tree and through the function of the base commit (`git show 7494ba2:verantyx/coarse_place.py`, run under another name). The answer of this tree without the key `frame_generated` must be
the answer of the base commit byte for byte (json.dumps, ensure_ascii=False, the order of the keys kept); the key must stand just before the first key of W3-a3's tail (after `spelling`); and its
value must be the row of the table (sqlite, read-only) or null. Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-b5/tools/query_unchanged.py --placement DIR --out TXT"""
import argparse
import importlib.util
import json
import os
import sqlite3
import subprocess
import sys

TREE = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--placement', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    from verantyx import coarse_place as CP
    src = subprocess.run(['git', '-C', TREE, 'show', '7494ba2:verantyx/coarse_place.py'], capture_output=True, check=True).stdout.decode('utf-8')
    spec = importlib.util.spec_from_loader('verantyx._coarse_place_base_q', loader=None)
    base = importlib.util.module_from_spec(spec); base.__package__ = 'verantyx'; sys.modules[spec.name] = base
    exec(compile(src, 'coarse_place@7494ba2', 'exec'), base.__dict__)
    con = sqlite3.connect('file:%s/placement.sqlite?mode=ro' % a.placement, uri=True)
    words = [r[0] for r in con.execute('SELECT word FROM generated_frames ORDER BY word')]
    n_frames = len(words)
    words += [r[0] for r in con.execute("SELECT word FROM headwords WHERE ns='N' AND state='DECIDED' ORDER BY word LIMIT 100")]
    words += [r[0] for r in con.execute("SELECT word FROM headwords WHERE ns='P' AND word NOT IN (SELECT word FROM generated_frames) ORDER BY word LIMIT 100")]
    words += ['ほげほげ', 'ホゲホゲ', 'ＡＢＣ', 'abc', 'ロケット', '2024年', '10kg']
    bad, with_value, nulls, pos_bad, val_bad = [], 0, 0, 0, 0
    tail = ('generated_frame', 'frame_status', 'frame', 'frame_unconfirmed', 'frame_disagreement')
    for w in words:
        x, y = CP.query(w, placement=a.placement), base.query(w, placement=a.placement)
        rest = {k: v for k, v in x.items() if k != 'frame_generated'}
        if json.dumps(rest, ensure_ascii=False) != json.dumps(y, ensure_ascii=False) or 'frame_generated' in y: bad.append(w)
        keys = list(x)
        first = next(k for k in tail if k in x)
        if keys[keys.index('frame_generated') + 1] != first or keys[keys.index('frame_generated') - 1] != 'spelling': pos_bad += 1
        row = con.execute('SELECT model, effort, batch_id, attempt, ptype, frame FROM generated_frames WHERE word=?', (x['spelling']['normalized'],)).fetchone()
        want = None if row is None else {'origin': 'generated', 'constructed': True, 'ptype': row[4], 'frame': json.loads(row[5]), 'provenance': {'model': row[0], 'effort': row[1], 'batch_id': row[2], 'attempt': row[3]}}
        if x['frame_generated'] != want: val_bad += 1
        if want is None: nulls += 1
        else: with_value += 1
    out = ['placement %s' % a.placement, 'words=%d (generated_frames %d + headwords and probes %d)' % (len(words), n_frames, len(words) - n_frames),
           'answer without frame_generated differs from the base commit: %d' % len(bad), 'key position wrong: %d' % pos_bad, 'value differs from the row of the table: %d' % val_bad,
           'with a value: %d, null: %d' % (with_value, nulls)] + ['MISMATCH %s' % w for w in bad[:50]]
    open(a.out, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print('\n'.join(out[:6]))
    sys.exit(1 if bad or pos_bad or val_bad else 0)


if __name__ == '__main__':
    main()
