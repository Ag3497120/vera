#!/usr/bin/env python3
"""W3-b2: every row of the new data (and, with --data, the B1 samples) through the entry in this process, judged by tools.bank_score.v2.b1.judge.

  --mode live      the real placement (--placement DIR, else the variable VERA_PLACEMENT)
  --mode fixture   w3b2_fakes.FixtureQuery (the answers of tests/reading_soundness/w3b2_placement_fixture.json); the words it did not hold are listed
  --data           comma-separated: frame, multiple, determiner, no (rows with `entry_expect` and `w3b2_expect`), B1_v2, B1_v2_r2, B1_v2_r3 (the self-made B1 samples)
Prints, for the whole data and for each file, the verdicts (correct / misread / abstain / incomplete / UNJUDGED), the rows whose `entry_expect` the entry does not meet, the
rows whose `w3b2_expect` the diagnosis (`semantic_read.typed_explain_ja`) does not meet, and how many bad verdicts are the output with no placement. --out gets the same as JSON.
Loaded verantyx* modules must be under PYTHONPATH (else exit 2). Usage: cd <tree> && PYTHONPATH=<tree> python tests/reading_soundness/w3b2_entry_check.py --mode live --placement DIR --data frame,multiple,determiner,no --out FILE
"""
import argparse
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent.parent))
import w3b2_common as C


def load(name):
    if name in C.DATA: return C.load_data(name)
    return [dict(r, _data=name) for r in C.load_jsonl(C.TREE / 'tests' / 'bank_score' / 'fixtures' / name / 'items.jsonl')]


def expect_ok(row, ex):
    e = row['w3b2_expect']
    if e == 'READ': return ex['w3b2'] == 'READ'
    if e.startswith('FRAME:'): return (ex['frame'] or '').startswith(e[6:])
    return (ex['w3b2'] or '').startswith(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['live', 'fixture'], required=True)
    ap.add_argument('--data', required=True); ap.add_argument('--out', required=True); ap.add_argument('--placement')
    a = ap.parse_args()
    from verantyx import semantic_read as SR, semantic_reader as R, constructions
    from tools.bank_score.v2 import b1
    import w3b2_fakes as F
    constructions.discover()
    C.isolation()
    path = a.placement or __import__('os').environ.get('VERA_PLACEMENT')
    if a.mode == 'live' and not path: print('no placement: give --placement or VERA_PLACEMENT'); sys.exit(2)
    rows = [r for name in a.data.split(',') for r in load(name)]
    totals, per_file, misses = collections.Counter(), collections.defaultdict(collections.Counter), []
    entry_bad, w3b2_bad, caused, details = [], [], collections.Counter(), []
    for r in rows:
        q = F.FixtureQuery() if a.mode == 'fixture' else R.CoarseQuery(path)
        out = SR.read(r['input'], r['lang'], placement=q)
        base = SR.read(r['input'], r['lang'], placement=None)
        verdict = b1.judge(r['expect'], r['lang'], out)['verdict']
        totals[verdict] += 1; per_file[r['_data']][verdict] += 1
        if a.mode == 'fixture': misses += q.misses
        if verdict in ('misread', 'incomplete', 'UNJUDGED'):
            caused['bad_verdict_total'] += 1
            caused['bad_verdict_identical_to_no_placement' if out == base else 'bad_verdict_produced_by_the_placement'] += 1
        ex = SR.typed_explain_ja(r['input'], F.FixtureQuery() if a.mode == 'fixture' else R.CoarseQuery(path)) if 'w3b2_expect' in r else None
        if 'entry_expect' in r and (r['entry_expect'] == 'read') != bool(out['readable']):
            entry_bad.append({'id': r['id'], 'input': r['input'], 'entry_expect': r['entry_expect'], 'readable': out['readable'], 'verdict': verdict,
                              'reasons': None if out['readable'] else out['abstain']['reasons'], 'explain': ex})
        elif r.get('entry_expect') == 'read' and verdict != 'correct':
            entry_bad.append({'id': r['id'], 'input': r['input'], 'entry_expect': 'read', 'readable': True, 'verdict': verdict, 'reasons': None, 'explain': ex})
        if ex is not None and not expect_ok(r, ex): w3b2_bad.append({'id': r['id'], 'input': r['input'], 'w3b2_expect': r['w3b2_expect'], 'explain': ex})
        details.append({'id': r.get('id'), 'data': r['_data'], 'input': r['input'], 'verdict': verdict, 'readable': out['readable'], 'entry_expect': r.get('entry_expect'),
                        'reasons': None if out['readable'] else out['abstain']['reasons'], 'explain': ex})
    declared = {}
    if (HERE / 'w3b2_expect_exceptions.json').exists():
        declared = {x['id']: x for x in json.loads((HERE / 'w3b2_expect_exceptions.json').read_text(encoding='utf-8'))['exceptions']}
    undeclared_entry = [m for m in entry_bad if m['id'] not in declared]
    undeclared_w3b2 = [m for m in w3b2_bad if m['id'] not in declared]
    summary = {'mode': a.mode, 'rows': len(rows), 'verdicts': dict(sorted(totals.items())), 'verdicts_by_data': {k: dict(sorted(v.items())) for k, v in per_file.items()},
               'misread': totals['misread'], 'incomplete': totals['incomplete'], 'unjudged': totals['UNJUDGED'], 'entry_expect_mismatch': len(entry_bad),
               'w3b2_expect_mismatch': len(w3b2_bad), 'entry_expect_mismatch_declared': len(entry_bad) - len(undeclared_entry), 'entry_expect_mismatch_undeclared': len(undeclared_entry),
               'w3b2_expect_mismatch_declared': len(w3b2_bad) - len(undeclared_w3b2), 'w3b2_expect_mismatch_undeclared': len(undeclared_w3b2), 'bad_verdicts': dict(caused), 'words_missing_from_the_fixture': sorted(set(misses))}
    print('mode=' + a.mode)
    for k, v in summary.items():
        if k != 'mode': print('%s=%s' % (k, json.dumps(v, ensure_ascii=False, sort_keys=True)))
    for m in entry_bad: print('ENTRY_EXPECT_MISMATCH%s %s %s expect=%s readable=%s verdict=%s reasons=%s' % ('(declared)' if m['id'] in declared else '', m['id'], m['input'], m['entry_expect'], m['readable'], m['verdict'], m['reasons']))
    for m in w3b2_bad: print('W3B2_EXPECT_MISMATCH%s %s %s expect=%s got=%s' % ('(declared)' if m['id'] in declared else '', m['id'], m['input'], m['w3b2_expect'], m['explain']))
    Path(a.out).write_text(json.dumps({'summary': summary, 'entry_expect_mismatch': entry_bad, 'w3b2_expect_mismatch': w3b2_bad, 'rows': details}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
