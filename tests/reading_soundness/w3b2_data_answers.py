#!/usr/bin/env python3
"""W3-b2 step 4: the placement's answers for the words the new data could ask about (`tests/reading_soundness/w3b2_data_terms.json`, written by w3b2_mk_data.py).
Only `coarse_place.query(word, placement=<dir>)` is used (no reader). One JSON line per word: the answer's state / origin / basis / types / the kinds of arms /
frame_status. Usage: cd <tree> && PYTHONPATH=<tree> python tests/reading_soundness/w3b2_data_answers.py --placement DIR --out FILE.jsonl
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import w3b2_common as C


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--placement', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    from verantyx import coarse_place
    C.isolation()
    terms = json.loads((C.HERE / 'w3b2_data_terms.json').read_text(encoding='utf-8'))
    lines = []
    for t in terms:
        ans = coarse_place.query(t, placement=a.placement)
        arms = ans.get('decided_by') or []
        lines.append(json.dumps({'term': t, 'state': ans['state'], 'origin': ans['origin'], 'estimate_basis': ans['estimate_basis'], 'top': ans['top'],
                                 'arms': sorted({x.split('@')[0] for x in arms}), 'only_role_distribution_arms': bool(arms) and all(x.startswith('role@') for x in arms),
                                 'has_gen_definition': 'gen_definition' in arms, 'frame_status': ans.get('frame_status')}, ensure_ascii=False))
    Path(a.out).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('terms=%d out=%s' % (len(lines), a.out))


if __name__ == '__main__':
    main()
