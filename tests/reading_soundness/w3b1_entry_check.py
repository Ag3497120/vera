#!/usr/bin/env python3
"""W3-b1: every row of the given data through the entry (in this process) and judged by tools.bank_score.v2.b1.judge.

  --mode live      the real placement (--placement DIR, else the variable VERA_PLACEMENT)
  --mode fixture   the fake of tests/reading_soundness/w3b1_fakes.py (answers of tests/reading_soundness/w3b1_placement_fixture.json)
  --data           comma-separated: ja_r8, en_r4, ja_r9, ja_r10 (rows with `entry_expect`), B1_v2, B1_v2_r2, B1_v2_r3 (the self-made B1 samples)
Prints, for the whole data and for each file: the verdicts (correct / misread / abstain / incomplete / UNJUDGED), and for the new data the rows whose `entry_expect`
the entry does not meet (read-expected but abstained / abstain-expected but read), the second reasons by prefix, and how many bad verdicts are the base commit's
own output (the same output with no placement) rather than something this change produced. --out gets the same as JSON with every row.
Under a tree without the placement argument the script stops (exit 2). Loaded verantyx* modules must be under PYTHONPATH (else exit 2).
"""
import argparse
import collections
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parent.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(TREE))


def load(name):
    if name in ('ja_r8', 'en_r4', 'ja_r9', 'ja_r10'):
        return [dict(r, _data=name) for r in (json.loads(l) for l in (HERE / (name + '.jsonl')).read_text(encoding='utf-8').splitlines() if l.strip())]
    return [dict(r, _data=name) for r in (json.loads(l) for l in (TREE / 'tests' / 'bank_score' / 'fixtures' / name / 'items.jsonl').read_text(encoding='utf-8').splitlines() if l.strip())]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['live', 'fixture'], required=True)
    ap.add_argument('--data', required=True); ap.add_argument('--out', required=True); ap.add_argument('--placement')
    a = ap.parse_args()
    from verantyx import semantic_read as SR, semantic_reader as R, constructions
    from tools.bank_score.v2 import b1
    import w3b1_fakes as F
    constructions.discover()
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.'))
               and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign: print('ISOLATION FAILED', foreign); sys.exit(2)
    rows = [r for name in a.data.split(',') for r in load(name)]
    if a.mode == 'live':
        path = a.placement or os.environ.get('VERA_PLACEMENT')
        if not path: print('no placement: give --placement or VERA_PLACEMENT'); sys.exit(2)
    totals, per_file = collections.Counter(), collections.defaultdict(collections.Counter)
    mismatch_read_not_read, mismatch_abstain_read, second, caused, details = [], [], collections.Counter(), collections.Counter(), []
    misses = []
    for r in rows:
        q = F.FixtureQuery() if a.mode == 'fixture' else R.CoarseQuery(path)
        out = SR.read(r['input'], r['lang'], placement=q)
        base = SR.read(r['input'], r['lang'], placement=None)
        verdict = b1.judge(r['expect'], r['lang'], out)['verdict']
        totals[verdict] += 1; per_file[r['_data']][verdict] += 1
        if a.mode == 'fixture': misses += q.misses
        if verdict in ('misread', 'incomplete', 'UNJUDGED'):
            caused['bad_verdict_total'] += 1
            if out == base: caused['bad_verdict_identical_to_no_placement'] += 1
            else: caused['bad_verdict_produced_by_the_placement'] += 1
        rs = None
        if not out['readable']:
            rs = out['abstain']['reasons']
            if len(rs) > 1: second[rs[1].split(':')[0]] += 1
        expect = r.get('entry_expect')
        if expect == 'read' and not out['readable']:
            mismatch_read_not_read.append({'id': r['id'], 'input': r['input'], 'reasons': rs})
        if expect == 'abstain' and out['readable']:
            mismatch_abstain_read.append({'id': r['id'], 'input': r['input'], 'verdict': verdict, 'identical_to_no_placement': out == base})
        details.append({'id': r.get('id'), 'data': r['_data'], 'input': r['input'], 'verdict': verdict, 'readable': out['readable'], 'entry_expect': expect, 'reasons': rs,
                        'roles': [c['roles'] for c in out['clauses']] if out['readable'] else None})
    new_rows = [r for r in rows if r.get('entry_expect')]
    reason_prefix_miss = []
    by_id = {d['id']: d for d in details}
    for r in new_rows:
        d = by_id[r['id']]
        if r['entry_expect'] == 'abstain' and r.get('expect_reason_prefix') and not d['readable']:
            rs = d['reasons']
            if not (len(rs) >= 2 and rs[1].startswith(r['expect_reason_prefix'])): reason_prefix_miss.append({'id': r['id'], 'want': r['expect_reason_prefix'], 'got': rs})
    summary = {'mode': a.mode, 'rows': len(rows), 'verdicts': dict(sorted(totals.items())),
               'verdicts_by_data': {k: dict(sorted(v.items())) for k, v in per_file.items()},
               'misread': totals['misread'], 'incomplete': totals['incomplete'], 'unjudged': totals['UNJUDGED'],
               'new_data_rows': len(new_rows),
               'entry_expect_mismatch': {'read_expected_but_abstained': len(mismatch_read_not_read), 'abstain_expected_but_read': len(mismatch_abstain_read)},
               'reason_prefix_mismatch_among_abstained': len(reason_prefix_miss),
               'second_reason_prefixes': dict(sorted(second.items())), 'bad_verdicts': dict(caused)}
    print('mode=' + a.mode)
    for k, v in summary.items():
        if k != 'mode': print('%s=%s' % (k, json.dumps(v, ensure_ascii=False, sort_keys=True)))
    for m in mismatch_read_not_read: print('READ_EXPECTED_BUT_ABSTAINED %s %s %s' % (m['id'], m['input'], m['reasons']))
    for m in mismatch_abstain_read: print('ABSTAIN_EXPECTED_BUT_READ %s %s verdict=%s identical_to_no_placement=%s' % (m['id'], m['input'], m['verdict'], m['identical_to_no_placement']))
    for m in reason_prefix_miss: print('REASON_PREFIX_MISMATCH %s want=%s got=%s' % (m['id'], m['want'], m['got']))
    Path(a.out).write_text(json.dumps({'summary': summary, 'misses_in_fixture': sorted(set(misses)), 'read_expected_but_abstained': mismatch_read_not_read,
                                       'abstain_expected_but_read': mismatch_abstain_read, 'reason_prefix_mismatch': reason_prefix_miss, 'rows': details},
                                      ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
