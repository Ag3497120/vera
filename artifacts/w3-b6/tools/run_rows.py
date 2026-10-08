#!/usr/bin/env python3
"""W3-b6 step 3: run the rows of a data file (the keys of tests/reading_soundness/ja_r13.jsonl; any file of the same shape, for example the unpublished sentences of the reviewer)
through the entry with the fake placement written in each row (`placement`: word -> spec, see tests/reading_soundness/w3b6_fakes.py), and write for each row: the verdict of the judge
against `expect`, what the entry did, the diagnosis (`typed_explain_ja(...)['w3b2']`), what the plan returned (the plan of the entry as it was called), the path that read the sentence
(`base` | `W3-b1` | `W3-b4` | `R`; for a refusal the trigger `U` | `U3` | `none`, or `R-blocked` when the plan read it and a later gate of the entry refused it) and `role_basis`.
The file may leave out `w3b6_expect`, `plan_expect`, `path`, `role_basis`, `keyless_same`: only the checks whose key is there are made. `misread` = the judge's verdict.
Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-b6/tools/run_rows.py --data FILE --out JSON [--exceptions FILE]
Exit code 0 only when there is no misread / incomplete / UNJUDGED row and no undeclared difference of an expectation."""
import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parents[3]


def _fakes():
    spec = importlib.util.spec_from_file_location('w3b6_fakes_in_run_rows', TREE / 'tests' / 'reading_soundness' / 'w3b6_fakes.py')
    mod = importlib.util.module_from_spec(spec); sys.modules['w3b6_fakes_in_run_rows'] = mod; spec.loader.exec_module(mod)
    return mod


def _diag_ok(diag, expect):
    if expect == 'READ': return diag == 'READ'
    if expect == 'NOT_RUN': return diag is None
    if diag is None: return False
    return diag.startswith(expect)


def _plan_ok(plan, expect):
    if expect in ('READ', 'NOT_CALLED'): return plan == expect
    return plan != 'READ' and plan != 'NOT_CALLED' and plan.startswith(expect)


def run_rows(rows, exceptions=None):
    """Returns (records, problems: Counter-like dict)."""
    from tools.bank_score.v2 import b1
    from verantyx import semantic_read as SR
    from verantyx import semantic_reader as R
    W = _fakes()
    exceptions = exceptions or {}
    records, problems = [], {}

    def bump(k): problems[k] = problems.get(k, 0) + 1
    orig = R.typed_plan_u_w3b2_ja
    caught = []

    def spy(*args, **kw):
        r = orig(*args, **kw); caught.append(r); return r
    R.typed_plan_u_w3b2_ja = spy
    try:
        for r in rows:
            caught.clear()
            out = SR.read(r['input'], placement=W.query_of(r))
            plan_calls = list(caught)
            ex = SR.typed_explain_ja(r['input'], W.query_of(r))
            verdict = b1.judge(r['expect'], 'ja', out)['verdict']
            entry = 'read' if out['readable'] else 'abstain'
            diag = ex['w3b2']
            typed = next((t for t, why in plan_calls if t is not None), None)
            if not plan_calls: plan = 'NOT_CALLED'
            else:
                t, why = plan_calls[-1]
                plan = 'READ' if t is not None else why
            basis = dict(typed['role_basis']) if typed is not None else None
            trig = ex['w3b1_trigger'] or ex['w3b2_trigger'] or 'none'
            if out['readable']:
                if not plan_calls: path = 'base'
                elif ex['w3b1'] == 'READ': path = 'W3-b1'
                elif basis and any(str(v).startswith('role_frame:') for v in basis.values()): path = 'R'
                else: path = 'W3-b4'
            else:
                path = 'R-blocked' if typed is not None else trig
            declared = r['id'] in exceptions
            checks = {}
            if 'entry_expect' in r: checks['entry'] = entry == r['entry_expect']
            if 'w3b6_expect' in r: checks['diag'] = _diag_ok(diag, r['w3b6_expect'])
            pe = r.get('plan_expect')
            if pe is None and 'w3b6_expect' in r: pe = 'NOT_CALLED' if r['w3b6_expect'] in ('NOT_RUN', 'PLACEMENT_W3B2_NOT_TRIGGERED') else r['w3b6_expect']      # no trigger: the plan is not called
            if pe is not None: checks['plan'] = _plan_ok(plan, pe)
            if 'path' in r: checks['path'] = path == r['path']
            if r.get('role_basis') is not None: checks['role_basis'] = basis == r['role_basis']
            if r.get('keyless_same'):
                kl = W.strip_role_frame(r)
                out2 = SR.read(kl['input'], placement=W.query_of(kl))
                checks['keyless_same'] = json.dumps(out, ensure_ascii=False, sort_keys=True) == json.dumps(out2, ensure_ascii=False, sort_keys=True)
            if declared:
                for k in checks: checks[k] = True
            rec = {'id': r['id'], 'input': r['input'], 'rule': r.get('rule'), 'entry_expect': r.get('entry_expect'), 'entry': entry, 'verdict': verdict, 'w3b6_expect': r.get('w3b6_expect'),
                   'diag': diag, 'plan': plan, 'path_expect': r.get('path'), 'path': path, 'role_basis': basis, 'checks': checks, 'declared_exception': declared,
                   'reasons': None if out['readable'] else out['abstain']['reasons']}
            records.append(rec)
            if verdict in ('misread', 'incomplete', 'UNJUDGED'): bump(verdict)
            for k, ok in checks.items():
                if not ok: bump('mismatch_' + k)
    finally:
        R.typed_plan_u_w3b2_ja = orig
    return records, problems


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--data', required=True); ap.add_argument('--out', required=True); ap.add_argument('--exceptions', default=None)
    a = ap.parse_args()
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    sys.path.insert(0, str(TREE / 'tests'))
    sys.path.insert(0, str(TREE))
    import verantyx.semantic_read    # noqa: F401  (loaded to check where it comes from)
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None)
               and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign:
        print('ISOLATION FAILED', foreign); sys.exit(2)
    exceptions = {}
    if a.exceptions: exceptions = {e['id']: e for e in json.loads(Path(a.exceptions).read_text(encoding='utf-8'))['exceptions']}
    rows = [json.loads(l) for l in Path(a.data).read_text(encoding='utf-8').splitlines() if l.strip()]
    records, problems = run_rows(rows, exceptions)
    Path(a.out).write_text(json.dumps(records, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    read = sum(1 for x in records if x['entry'] == 'read')
    print('rows=%d read=%d abstain=%d misread=%d incomplete=%d unjudged=%d mismatches=%s' % (len(records), read, len(records) - read, problems.get('misread', 0),
          problems.get('incomplete', 0), problems.get('UNJUDGED', 0), json.dumps({k: v for k, v in problems.items() if k.startswith('mismatch_')}, sort_keys=True)))
    print('read rows judged correct: %d of %d read' % (sum(1 for x in records if x['entry'] == 'read' and x['verdict'] == 'correct'), read))
    by = {}
    for x in records: by.setdefault(x['path'], []).append(x)
    for p in sorted(by): print('path %s rows=%d read=%d' % (p, len(by[p]), sum(1 for x in by[p] if x['entry'] == 'read')))
    for x in records:
        bad = [k for k, ok in x['checks'].items() if not ok]
        if bad or x['verdict'] in ('misread', 'incomplete', 'UNJUDGED'):
            print('PROBLEM %s %s verdict=%s bad=%s diag=%s plan=%s path=%s expect_path=%s' % (x['id'], x['input'], x['verdict'], bad, x['diag'], x['plan'], x['path'], x['path_expect']))
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
