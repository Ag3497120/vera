#!/usr/bin/env python3
"""W3-b5 step 9: run the rows of a data file (the keys of tests/reading_soundness/ja_r11.jsonl; the same for the unpublished sentences of the reviewer) through the entry with the fake placement
written in each row, and write for each row: the verdict of the judge against `expect`, whether the entry did what `entry_expect` says, whether the diagnosis
(`typed_explain_ja(...)['w3b2']`) is what `w3b5_expect` says (READ, REFUSED = any refusal, or a prefix), the license told by the plan (`role_license`), the reason of the refusal.
The fake answers come from the test file of the ticket (`answer_of`, `query_of`): the same code that the tests run.
Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-b5/tools/run_rows.py --data FILE --out JSON [--exceptions FILE] [--narrowed FILE]
Exit code 0 only when there is no misread / incomplete / UNJUDGED row and no undeclared difference of `entry_expect` or `w3b5_expect`. A row of the file given with --exceptions is compared with the
observation pinned there; a row of --narrowed (K206: taken out of the table after a misread) must be refused with the recorded diagnosis.
`per_group_counts.json` is written beside --out: rows, read, refused by role_group and the reasons of the refused rows."""
import argparse
import collections
import importlib.util
import json
import os
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parents[3]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--data', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--exceptions', default=None); ap.add_argument('--narrowed', default=None)
    a = ap.parse_args()
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    sys.path.insert(0, str(TREE / 'tests'))
    spec = importlib.util.spec_from_file_location('tw5_run_rows', TREE / 'tests' / 'test_semantic_read_w3b5.py')
    tw = importlib.util.module_from_spec(spec); sys.modules['tw5_run_rows'] = tw; spec.loader.exec_module(tw)
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None)
               and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign:
        print('ISOLATION FAILED', foreign); sys.exit(2)
    from verantyx import semantic_reader as R
    exceptions = {}
    if a.exceptions: exceptions = {e['id']: e for e in json.loads(Path(a.exceptions).read_text(encoding='utf-8'))['exceptions']}
    narrowed = {}
    if a.narrowed: narrowed = json.loads(Path(a.narrowed).read_text(encoding='utf-8'))['rows']
    rows = [json.loads(l) for l in Path(a.data).read_text(encoding='utf-8').splitlines() if l.strip()]
    result, per = [], {}
    problems = collections.Counter()
    orig = R.typed_plan_u_w3b2_ja
    caught = []

    def spy(*args, **kw):
        r = orig(*args, **kw); caught.append(r); return r
    R.typed_plan_u_w3b2_ja = spy
    try:
        for r in rows:
            q = tw.query_of(r)
            caught.clear()
            out = tw.SR.read(r['input'], placement=q)
            lic = None
            for typed, why in caught:
                if typed is not None: lic = typed.get('role_license')
            ex = tw.SR.typed_explain_ja(r['input'], tw.query_of(r))
            verdict = tw.b1.judge(r['expect'], 'ja', out)['verdict']
            entry = 'read' if out['readable'] else 'abstain'
            w3b2 = ex['w3b2'] if ex['w3b2'] is not None else 'PLACEMENT_W3B2_NOT_TRIGGERED'
            declared, narrowed_row = r['id'] in exceptions, r['id'] in narrowed
            e = r['w3b5_expect']
            match = (w3b2 == 'READ') if e == 'READ' else ((w3b2 != 'READ') if e == 'REFUSED' else w3b2.startswith(e))
            entry_ok = entry == r['entry_expect']
            if narrowed_row:
                nr = narrowed[r['id']]
                entry_ok = entry == 'abstain'; match = w3b2 == nr['observed_w3b2']
            elif declared:
                entry_ok = True; match = ex == exceptions[r['id']]['observed_explain'] and verdict == exceptions[r['id']]['observed_verdict']
            rec = {'id': r['id'], 'input': r['input'], 'role_group': r['role_group'], 'pred_type': r['pred_type'], 'path': r['path'], 'frame_source': r['frame_source'],
                   'entry_expect': r['entry_expect'], 'entry': entry, 'verdict': verdict, 'entry_ok': entry_ok, 'w3b5_expect': e, 'w3b2': w3b2, 'w3b2_ok': match,
                   'role_license': lic, 'declared_exception': declared, 'narrowed_row': narrowed_row, 'reasons': None if out['readable'] else out['abstain']['reasons']}
            result.append(rec)
            if verdict in ('misread', 'incomplete', 'UNJUDGED'): problems[verdict] += 1
            if not entry_ok: problems['entry_expect_mismatch'] += 1
            if not match: problems['w3b5_expect_mismatch'] += 1
            pt = per.setdefault(r['role_group'], {'rows': 0, 'read': 0, 'abstain': 0, 'reasons_of_the_refused_rows': {}})
            pt['rows'] += 1; pt['read' if out['readable'] else 'abstain'] += 1
            if not out['readable']:
                key = w3b2.split(':')[0]
                pt['reasons_of_the_refused_rows'][key] = pt['reasons_of_the_refused_rows'].get(key, 0) + 1
    finally:
        R.typed_plan_u_w3b2_ja = orig
    Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    Path(a.out).with_name('per_group_counts.json').write_text(json.dumps(per, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    print('rows=%d misread=%d incomplete=%d unjudged=%d entry_expect_mismatch=%d w3b5_expect_mismatch=%d declared_exceptions=%d narrowed_rows=%d' % (
        len(rows), problems['misread'], problems['incomplete'], problems['UNJUDGED'], problems['entry_expect_mismatch'], problems['w3b5_expect_mismatch'],
        sum(1 for x in result if x['declared_exception']), sum(1 for x in result if x['narrowed_row'])))
    print('read rows judged correct: %d of %d read' % (sum(1 for x in result if x['entry'] == 'read' and x['verdict'] == 'correct'), sum(1 for x in result if x['entry'] == 'read')))
    for t in sorted(per): print('%s rows=%d read=%d abstain=%d reasons=%s' % (t, per[t]['rows'], per[t]['read'], per[t]['abstain'], json.dumps(per[t]['reasons_of_the_refused_rows'], ensure_ascii=False)))
    sys.exit(1 if any(problems.values()) else 0)


if __name__ == '__main__':
    main()
