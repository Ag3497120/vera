#!/usr/bin/env python3
"""W3-b4 step 8: run the rows of a data file (the keys of tests/reading_soundness/ja_r10_w3b4.jsonl, the same for the unpublished sentences of the reviewer) through the entry with
the fake placement written in each row, and write for each row: the verdict of the judge against `expect`, whether the entry did what `entry_expect` says, whether the
diagnosis (`typed_explain_ja(...)['w3b2']`) starts with `w3b4_expect`, the triggers and the reason of W3-b2/W3-b4's plan. Also the number of rows read and the reasons of the refused rows per
predicate type (`per_type_counts.json` beside --out).
Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-b4/tools/run_rows.py --data FILE --out JSON [--exceptions FILE]
Round 2: a row whose predicate type is in artifacts/w3-b4/narrowed_types.json (taken out of the table after the review of round 1) must be refused by the entry (whatever its frozen
`entry_expect` says), with the diagnosis `PLACEMENT_FRAME_NOT_READ:<type>` -- or, for a row refused before the type is asked, the registered reason (`BEFORE_THE_TYPE` of the test file).
Round 3: a row of artifacts/w3-b4/narrowed_rows.json (a frozen row whose diagnosis changed when the place/で rows of P_ACT, P_CREATE, P_EMOTION were taken out) must be refused by the entry with the recorded
diagnosis `observed_w3b2` (checked before the declared rows). The output has `narrowed_row: true/false` for each row.
Exit code 0 only when there is no misread / incomplete / UNJUDGED row and no undeclared difference of `entry_expect` or `w3b4_expect`. A row that the file given with --exceptions declares is
compared with the observation pinned there instead of with `w3b4_expect`."""
import argparse
import collections
import importlib.util
import json
import os
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parents[3]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--data', required=True); ap.add_argument('--out', required=True); ap.add_argument('--exceptions', default=None)
    a = ap.parse_args()
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    sys.path.insert(0, str(TREE / 'tests'))
    spec = importlib.util.spec_from_file_location('tw4_run_rows', TREE / 'tests' / 'test_semantic_read_w3b4.py')
    tw = importlib.util.module_from_spec(spec); sys.modules['tw4_run_rows'] = tw; spec.loader.exec_module(tw)
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None)
               and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign:
        print('ISOLATION FAILED', foreign); sys.exit(2)
    exceptions = {}
    if a.exceptions: exceptions = {e['id']: e for e in json.loads(Path(a.exceptions).read_text(encoding='utf-8'))['exceptions']}
    rows = [json.loads(l) for l in Path(a.data).read_text(encoding='utf-8').splitlines() if l.strip()]
    result, per_type = [], {}
    problems = collections.Counter()
    for r in rows:
        q = tw.query_of(r)
        out = tw.SR.read(r['input'], placement=q)
        ex = tw.SR.typed_explain_ja(r['input'], tw.query_of(r))
        verdict = tw.b1.judge(r['expect'], 'ja', out)['verdict']
        entry = 'read' if out['readable'] else 'abstain'
        e = r['w3b4_expect']
        w3b2 = ex['w3b2']
        match = (w3b2 == 'READ') if e == 'READ' else (w3b2 or '').startswith(e)
        declared = r['id'] in exceptions
        narrowed = r['pred_type'] in tw.NARROWED
        narrowed_row = r['id'] in tw.NARROWED_ROWS
        if narrowed:
            pre = r['entry_expect'] == 'abstain' and e in tw.BEFORE_THE_TYPE and ((ex == exceptions[r['id']]['observed_explain']) if declared else (w3b2 or '').startswith(e))
            match = w3b2 == 'PLACEMENT_FRAME_NOT_READ:' + r['pred_type'] or pre
        elif r['id'] in tw.NARROWED_ROWS:
            # round 3: a frozen row that the removal of the place/で rows of P_ACT, P_CREATE, P_EMOTION changed (artifacts/w3-b4/narrowed_rows.json): the entry refuses it, with the recorded diagnosis.
            # This comes BEFORE the declared rows: the three declared rows of these types are refused now with another reason
            nr = tw.NARROWED_ROWS[r['id']]
            match = (not out['readable']) and w3b2 == nr['observed_w3b2'] and nr['frozen_entry_expect'] == r['entry_expect'] and nr['frozen_w3b4_expect'] == e
        elif declared: match = ex == exceptions[r['id']]['observed_explain'] and verdict == exceptions[r['id']]['observed_verdict']
        rec = {'id': r['id'], 'input': r['input'], 'pred_type': r['pred_type'], 'path': r['path'], 'entry_expect': r['entry_expect'], 'entry': entry, 'verdict': verdict,
               'narrowed_type': narrowed, 'narrowed_row': narrowed_row, 'entry_ok': (entry == 'abstain') if (narrowed or narrowed_row) else (entry == r['entry_expect']), 'w3b4_expect': e, 'w3b2': w3b2, 'w3b2_ok': match, 'declared_exception': declared, 'w3b1_trigger': ex['w3b1_trigger'],
               'w3b2_trigger': ex['w3b2_trigger'], 'reasons': None if out['readable'] else out['abstain']['reasons']}
        result.append(rec)
        if verdict in ('misread', 'incomplete', 'UNJUDGED'): problems[verdict] += 1
        if not rec['entry_ok']: problems['entry_expect_mismatch'] += 1
        if not match: problems['w3b4_expect_mismatch'] += 1
        pt = per_type.setdefault(r['pred_type'], {'rows': 0, 'read': 0, 'abstain': 0, 'reasons_of_the_refused_rows': {}})
        pt['rows'] += 1; pt['read' if out['readable'] else 'abstain'] += 1
        if not out['readable']:
            key = (w3b2 or 'NO_TYPED_STEP_RAN').split(':')[0]
            pt['reasons_of_the_refused_rows'][key] = pt['reasons_of_the_refused_rows'].get(key, 0) + 1
    Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    Path(a.out).with_name('per_type_counts.json').write_text(json.dumps(per_type, ensure_ascii=False, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    print('rows=%d misread=%d incomplete=%d unjudged=%d entry_expect_mismatch=%d w3b4_expect_mismatch=%d declared_exceptions=%d' % (
        len(rows), problems['misread'], problems['incomplete'], problems['UNJUDGED'], problems['entry_expect_mismatch'], problems['w3b4_expect_mismatch'], sum(1 for x in result if x['declared_exception'])))
    print('read rows judged correct: %d of %d read' % (sum(1 for x in result if x['entry'] == 'read' and x['verdict'] == 'correct'), sum(1 for x in result if x['entry'] == 'read')))
    for t in sorted(per_type): print('%s rows=%d read=%d abstain=%d reasons=%s' % (t, per_type[t]['rows'], per_type[t]['read'], per_type[t]['abstain'], json.dumps(per_type[t]['reasons_of_the_refused_rows'], ensure_ascii=False)))
    sys.exit(1 if any(problems.values()) else 0)


if __name__ == '__main__':
    main()
