#!/usr/bin/env python3
"""W3-b4 round 3 (docs 10D K184): what protects the rows place/で/PLACE of v1 (P_MOVE, P_COMMUNICATE). For each predicate type of artifacts/w3-b4/r7members/type_members.json (the r7 members:
namespace P, DECIDED, direct, one type), ask the placement r7 (read only) for each word and count `frame_status`; for the words whose frame is CONFIRMED list the particles of the frame, count how
many have で in it, and list the words whose frame is NOT_CONFIRMED (for those `predicate_frame` of K95 decides by the table alone). Placement facts only: no sentence is read.
Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-b4/tools/v1_de_frame_status.py --placement DIR [--members JSON]"""
import argparse
import collections
import json
import os
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parents[3]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--placement', required=True); ap.add_argument('--members', default=str(TREE / 'artifacts' / 'w3-b4' / 'r7members' / 'type_members.json'))
    a = ap.parse_args()
    from verantyx import coarse_place
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign: print('ISOLATION FAILED', foreign); sys.exit(2)
    members = json.loads(Path(a.members).read_text(encoding='utf-8'))
    print('placement=%s members=%s' % (a.placement, a.members))
    for t in ('P_MOVE', 'P_COMMUNICATE', 'P_ACT', 'P_CREATE', 'P_EMOTION'):
        status, particles, with_de, not_confirmed = collections.Counter(), collections.Counter(), [], []
        for w in members[t]:
            q = coarse_place.query(w, placement=a.placement)
            st = str(q.get('frame_status')); status[st] += 1
            if st == 'CONFIRMED':
                fr = q.get('frame') or {}
                particles.update(fr.keys())
                if 'で' in fr: with_de.append(w)
            elif st == 'NOT_CONFIRMED': not_confirmed.append(w)
        print('%s members=%d frame_status=%s' % (t, len(members[t]), json.dumps(dict(sorted(status.items())), ensure_ascii=False)))
        print('  CONFIRMED: particles of the frames=%s; words whose confirmed frame has で: %d %s' % (json.dumps(dict(sorted(particles.items())), ensure_ascii=False), len(with_de), ' '.join(with_de)))
        print('  NOT_CONFIRMED (%d): %s' % (len(not_confirmed), ' '.join(not_confirmed)))


if __name__ == '__main__':
    main()
