#!/usr/bin/env python3
"""W3-b3: every row of the new data (and, with --data, the B1 samples) through the entry in this process, judged by tools.bank_score.v2.b1.judge.

  --mode live      the real placement (--placement DIR, else the variable VERA_PLACEMENT)
  --mode fixture   w3b3_fakes.FixtureQuery (the answers of tests/reading_soundness/w3b3_placement_fixture.json); the words it did not hold are in the JSON (not in the text)
  --data           comma-separated: relative, connective, parallel, w1a4 (rows with `entry_expect`, `w3b3_expect`, `structure_expect`), B1_v2, B1_v2_r2, B1_v2_r3 (the self-made B1 samples)
Prints, for the whole data and for each file, the verdicts (correct / misread / abstain / incomplete / UNJUDGED), the rows whose `entry_expect` the entry does not meet, the rows whose
`w3b3_expect` the diagnosis (`semantic_read.clause_scope_explain_ja`) does not meet, the rows whose `structure_expect` (the clauses and the edge of a te / continuative row) it does not
meet, and how many bad verdicts are the output with no placement. The text holds nothing that depends on the mode (but the first line), so the two modes can be compared.
--out gets the same as JSON with every row. Loaded verantyx* modules must be under PYTHONPATH (else exit 2).
Usage: cd <tree> && PYTHONPATH=<tree> python tests/reading_soundness/w3b3_entry_check.py --mode live --placement DIR --data relative,connective,parallel,w1a4 --out FILE
"""
import argparse
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent.parent))
import w3b3_common as C


def load(name):
    if name in C.DATA_ALL: return C.load_data(name)
    return [dict(r, _data=name) for r in C.load_jsonl(C.TREE / 'tests' / 'bank_score' / 'fixtures' / name / 'items.jsonl')]


def expect_ok(row, ex):
    want = row['w3b3_expect']
    if want == 'READ': return ex['read'] is True
    if want == 'ABSTAIN': return ex['read'] is False
    return ex['read'] is False and (ex['reason'] or '').startswith(want)


def structure_ok(row, ex):
    want = row.get('structure_expect')
    if not want: return True
    if ex['edges'] != want['edges'] or len(ex['clause_reads']) != len(want['clauses']): return False
    for got, w in zip(ex['clause_reads'], want['clauses']):
        c = got['clause']
        if not got['readable'] or (c['predicate'], c['roles'], c['polarity'], c['tense'], c['voice']) != (w['predicate'], w['roles'], w['polarity'], w['tense'], w['voice']): return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mode', choices=['live', 'fixture'], required=True)
    ap.add_argument('--data', required=True); ap.add_argument('--out', required=True); ap.add_argument('--placement')
    a = ap.parse_args()
    from verantyx import semantic_read as SR, semantic_reader as R, constructions
    from tools.bank_score.v2 import b1
    import w3b3_fakes as F
    constructions.discover()
    C.isolation()
    path = a.placement or __import__('os').environ.get('VERA_PLACEMENT')
    if a.mode == 'live' and not path: print('no placement: give --placement or VERA_PLACEMENT'); sys.exit(2)
    make = (lambda: F.FixtureQuery()) if a.mode == 'fixture' else (lambda: R.CoarseQuery(path))
    rows = [r for name in a.data.split(',') for r in load(name)]
    totals, per_file, misses = collections.Counter(), collections.defaultdict(collections.Counter), []
    entry_bad, w3b3_bad, structure_bad, caused, details = [], [], [], collections.Counter(), []
    reasons = collections.Counter()
    for r in rows:
        q = make()
        out = SR.read(r['input'], r['lang'], placement=q)
        base = SR.read(r['input'], r['lang'], placement=None)
        verdict = b1.judge(r['expect'], r['lang'], out)['verdict']
        totals[verdict] += 1; per_file[r['_data']][verdict] += 1
        if a.mode == 'fixture': misses += q.misses
        if verdict in ('misread', 'incomplete', 'UNJUDGED'):
            caused['bad_verdict_total'] += 1
            caused['bad_verdict_identical_to_no_placement' if out == base else 'bad_verdict_produced_by_the_placement'] += 1
        ex = SR.clause_scope_explain_ja(r['input'], make()) if r['lang'] == 'ja' else None
        if ex is not None and not ex['read']: reasons[(ex['reason'] or '').split(':')[0]] += 1
        if 'entry_expect' in r and (r['entry_expect'] == 'read') != bool(out['readable']):
            entry_bad.append({'id': r['id'], 'input': r['input'], 'entry_expect': r['entry_expect'], 'readable': out['readable'], 'verdict': verdict,
                              'reasons': None if out['readable'] else out['abstain']['reasons'], 'explain_reason': ex and ex['reason']})
        elif r.get('entry_expect') == 'read' and verdict != 'correct':
            entry_bad.append({'id': r['id'], 'input': r['input'], 'entry_expect': 'read', 'readable': True, 'verdict': verdict, 'reasons': None, 'explain_reason': ex and ex['reason']})
        if 'w3b3_expect' in r and not expect_ok(r, ex): w3b3_bad.append({'id': r['id'], 'input': r['input'], 'w3b3_expect': r['w3b3_expect'], 'got': ex['reason'], 'read': ex['read']})
        if 'structure_expect' in r and not structure_ok(r, ex): structure_bad.append({'id': r['id'], 'input': r['input'], 'want': r['structure_expect'], 'got_edges': ex['edges'],
                                                                                    'got_clauses': [c['clause'] for c in ex['clause_reads']]})
        details.append({'id': r.get('id'), 'data': r['_data'], 'input': r['input'], 'verdict': verdict, 'readable': out['readable'], 'entry_expect': r.get('entry_expect'),
                        'reasons': None if out['readable'] else out['abstain']['reasons'], 'explain': ex})
    summary = {'rows': len(rows), 'verdicts': dict(sorted(totals.items())), 'verdicts_by_data': {k: dict(sorted(v.items())) for k, v in per_file.items()},
               'misread': totals['misread'], 'incomplete': totals['incomplete'], 'unjudged': totals['UNJUDGED'], 'entry_expect_mismatch': len(entry_bad),
               'w3b3_expect_mismatch': len(w3b3_bad), 'structure_expect_mismatch': len(structure_bad), 'bad_verdicts': dict(caused),
               'path_stopped_by_reason': dict(sorted(reasons.items()))}
    print('mode=' + a.mode)
    for k, v in summary.items(): print('%s=%s' % (k, json.dumps(v, ensure_ascii=False, sort_keys=True)))
    for m in entry_bad: print('ENTRY_EXPECT_MISMATCH %s %s expect=%s readable=%s verdict=%s reasons=%s path=%s' % (m['id'], m['input'], m['entry_expect'], m['readable'], m['verdict'], m['reasons'], m['explain_reason']))
    for m in w3b3_bad: print('W3B3_EXPECT_MISMATCH %s %s expect=%s got=%s' % (m['id'], m['input'], m['w3b3_expect'], m['got']))
    for m in structure_bad: print('STRUCTURE_EXPECT_MISMATCH %s %s got_edges=%s got_clauses=%s' % (m['id'], m['input'], m['got_edges'], json.dumps(m['got_clauses'], ensure_ascii=False)))
    Path(a.out).write_text(json.dumps({'summary': summary, 'words_missing_from_the_fixture': sorted(set(misses)), 'entry_expect_mismatch': entry_bad, 'w3b3_expect_mismatch': w3b3_bad,
                                       'structure_expect_mismatch': structure_bad, 'rows': details}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
