#!/usr/bin/env python3
"""W3-b4: how many of the r7 members of each type that the second table reads (artifacts/w3-b4/r7members/type_members.json) the derived-head gate of K63 (change record 3) refuses whatever the
sentence is (the head is a 下一段 verb, or a 五段-サ行 verb whose dictionary form ends in an a-column kana + す). Reader only: the conjugation type of the dictionary form from the tagger and
`semantic_reader.DERIVED_GATE`. Nothing is read with a placement. Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-b4/tools/members_gate.py --members JSON --out TXT"""
import argparse
import json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--members', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    from verantyx import semantic_reader as R
    from verantyx.typed_edges import _base
    members = json.loads(Path(a.members).read_text(encoding='utf-8'))
    lines, total, gated_all = [], 0, 0
    for t in ('P_ACT', 'P_CHANGE', 'P_CREATE', 'P_CONSUME', 'P_EMOTION'):
        gated, free = [], []
        for w in members[t]:
            toks = R._tokens(w)
            for tok, s, e in toks: tok.feature.pos1, tok.feature.cType
            head = toks[-1][0]; ctype = head.feature.cType or ''; base = _base(head)
            g = ctype.startswith(R.DERIVED_GATE[0][0]) or (ctype == R.DERIVED_GATE[1][0] and len(base) >= 2 and base[-1] == 'す' and base[-2] in R._A_ROW_KANA)
            (gated if g else free).append(w)
        total += len(members[t]); gated_all += len(gated)
        lines.append('%s members=%d refused_by_the_derived_gate=%d free=%d' % (t, len(members[t]), len(gated), len(free)))
        lines.append('  gated: ' + ' '.join(gated)); lines.append('  free:  ' + ' '.join(free))
    lines.append('total members=%d refused_by_the_derived_gate=%d' % (total, gated_all))
    Path(a.out).write_text('\n'.join(lines) + '\n', encoding='utf-8'); print('\n'.join(l for l in lines if not l.startswith('  ')))


if __name__ == '__main__':
    main()
