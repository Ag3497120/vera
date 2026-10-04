#!/usr/bin/env python3
"""W3-b2 step 2: the predicates whose frame the placement CONFIRMED (W3-a3 `gen_frame`), asked again through `coarse_place.query`.

The sqlite file of the placement is opened read-only (`file:...?mode=ro`); the words are those of `headwords` with `by LIKE '%gen_frame%' AND origin='direct'`;
each one is asked with the placement path (word only). Writes --out (JSON, every word with its answer's frame_status / top / frame) and the same stem with `.txt`
(counts by predicate type, and the particles the frames hold). Loaded verantyx* modules must be under PYTHONPATH (else exit 2).
Usage: cd <tree> && PYTHONPATH=<tree> python tests/reading_soundness/w3b2_frames_list.py --placement DIR --out FILE.json
"""
import argparse
import collections
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w3b2_common as C


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--placement', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    from verantyx import coarse_place
    C.isolation()
    con = sqlite3.connect('file:%s?mode=ro' % (Path(a.placement) / 'placement.sqlite'), uri=True)
    words = [r[0] for r in con.execute("SELECT word FROM headwords WHERE by LIKE '%gen_frame%' AND origin='direct' ORDER BY word")]
    con.close()
    rows, by_type, particles, status = [], collections.Counter(), collections.Counter(), collections.Counter()
    for w in words:
        ans = coarse_place.query(w, placement=a.placement)
        rows.append({'word': w, 'state': ans['state'], 'top': ans['top'], 'origin': ans['origin'], 'frame_status': ans.get('frame_status'), 'frame': ans.get('frame')})
        status[ans.get('frame_status')] += 1
        if ans.get('frame_status') == 'CONFIRMED':
            by_type[tuple(ans['top'])] += 1
            for p in (ans.get('frame') or {}): particles[p] += 1
    doc = {'words': len(words), 'frame_status': dict(status), 'by_predicate_type': {'+'.join(k): v for k, v in sorted(by_type.items())},
           'particles_in_frames': dict(sorted(particles.items())), 'rows': rows}
    Path(a.out).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    lines = ['words=%d' % len(words), 'frame_status=%s' % json.dumps(doc['frame_status'], ensure_ascii=False, sort_keys=True),
             'by_predicate_type=%s' % json.dumps(doc['by_predicate_type'], ensure_ascii=False, sort_keys=True),
             'particles_in_frames=%s' % json.dumps(doc['particles_in_frames'], ensure_ascii=False, sort_keys=True)]
    for r in rows:
        lines.append('%s\t%s\t%s\t%s' % (r['word'], '+'.join(r['top']), r['frame_status'], json.dumps(r['frame'], ensure_ascii=False, sort_keys=True)))
    Path(a.out).with_suffix('.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines[:4]))


if __name__ == '__main__':
    main()
