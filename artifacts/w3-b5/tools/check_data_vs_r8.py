#!/usr/bin/env python3
"""W3-b5 step 4/5: the data against the REAL placement r8 (read-only).
 --frames  : for every row with frame_source `r8`, the `frame_generated` of the predicate must equal the row of `generated_frames` of r8 (sqlite) character for character, and the type of the
             predicate must be the ptype of that row; `absent`: no row in r8 and `frame_generated` null; `synthetic`: only the group `mechanism`. Writes frame_source_check.txt (mismatch 0).
 --fillers : every noun of every row: the spec used in the fake placement, the real r8 answer, and whether the spec is the real answer (r8) or an optimistic one (a type the real r8 answer
             has or contradicts). Writes filler_types_r8.tsv; exits 1 if a spec contradicts r8 without being declared in the note.
Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-b5/tools/check_data_vs_r8.py --data FILE --frames OUT --fillers OUT
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mk_core as C   # noqa: E402


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--data', required=True); ap.add_argument('--frames', required=True); ap.add_argument('--fillers', required=True)
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(a.data, encoding='utf-8') if l.strip()]
    out, bad = [], 0
    n = {'r8': 0, 'absent': 0, 'synthetic': 0}
    for r in rows:
        src = r['frame_source']; n[src] += 1
        # the predicate is the key of the placement that has a `namespace: P`
        preds = [w for w, s in r['placement'].items() if s.get('namespace') == 'P']
        assert len(preds) == 1, (r['id'], preds)
        w = preds[0]; spec = r['placement'][w]
        real = C.r8_frame_row(w)
        if src == 'r8':
            ok = real is not None and spec['frame_generated'] == real and spec['top'] == [real['ptype']] and r['pred_type'] == real['ptype']
        elif src == 'absent':
            ok = real is None and spec['frame_generated'] is None
        else:
            ok = r['role_group'] == 'mechanism' and real is None or (r['role_group'] == 'mechanism')
        if not ok:
            bad += 1; out.append('MISMATCH\t%s\t%s\t%s' % (r['id'], src, w))
    out.insert(0, 'rows=%d frame_source r8=%d absent=%d synthetic=%d mismatch=%d' % (len(rows), n['r8'], n['absent'], n['synthetic'], bad))
    open(a.frames, 'w', encoding='utf-8').write('\n'.join(out) + '\n')
    print(out[0])
    # the nouns
    seen = {}
    for r in rows:
        for w, s in r['placement'].items():
            if s.get('namespace') == 'P': continue
            seen.setdefault(w, set()).add(json.dumps(s, ensure_ascii=False, sort_keys=True))
    lines = ['word\tspec_used\tr8_state\tr8_origin\tr8_top\tr8_decided_by_is_role_only\tverdict']
    contradict = 0
    for w in sorted(seen):
        ans = C.r8_answer(w)
        role_only = bool(ans.get('decided_by')) and all(x.startswith('role@') for x in ans['decided_by'])
        for sj in sorted(seen[w]):
            s = json.loads(sj)
            try: real_spec = C.noun_spec(w, 'r8')
            except ValueError: real_spec = None
            same = real_spec is not None and json.dumps(real_spec, ensure_ascii=False, sort_keys=True) == sj
            if same: v = 'REAL'
            else:
                # an optimistic spec: DECIDED direct with a type that r8's own answer has (state DECIDED or MULTIPLE containing it) is declared; anything else contradicts r8
                t = (s.get('top') or [None])[0]
                v = 'OPTIMISTIC_TYPE_IN_R8' if (s.get('decided_by') == ['seed'] and t in (ans.get('top') or [])) else 'CONTRADICTS_R8'
                if v == 'CONTRADICTS_R8': contradict += 1
            lines.append('\t'.join([w, sj, ans['state'], str(ans.get('origin')), ','.join(ans['top']), str(role_only), v]))
    open(a.fillers, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    print('nouns=%d contradict=%d' % (len(seen), contradict))
    sys.exit(1 if bad or contradict else 0)


if __name__ == '__main__':
    main()
