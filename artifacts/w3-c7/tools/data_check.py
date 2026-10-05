#!/usr/bin/env python3
"""W3-c7: every row of the frozen data through the entry (tools.bank_score.v2.b1.judge), and the diagnosis against `w3c7_expect` and `structure_expect`.

  --placement DIR    the real placement (CoarseQuery(DIR))
  --fixture FILE     the recorded answers (w3c7_placement_r9.jsonl): a fake with query(term) and calls; the words it did not hold are listed
  --data A,B,...     the jsonl files
  --out FILE         the JSON with every row
Prints per file: rows out_read out_abstain (what the entry did) v_* (the verdicts of the judge) misread incomplete unjudged entry_mismatch expect_mismatch structure_mismatch. Loaded verantyx* modules must be under PYTHONPATH (else exit 2).
Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-c7/tools/data_check.py --placement DIR --data F1,F2 --out OUT.json
"""
import argparse
import collections
import copy
import json
import os
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(TREE))


def isolation():
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None)
               and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign:
        print('ISOLATION FAILED', foreign)
        sys.exit(2)


class FixtureQuery:
    id = 'w3c7-fixture'

    def __init__(self, answers):
        self.answers, self.misses, self.calls = answers, [], []

    def query(self, term):
        self.calls.append(term)
        if term not in self.answers:
            self.misses.append(term)
            return {'state': 'UNKNOWN', 'term': term}
        return copy.deepcopy(self.answers[term])


def expect_ok(row, ex):
    want = row['w3c7_expect']
    if want == 'READ': return ex['read'] is True
    if want == 'ABSTAIN': return ex['read'] is False
    return ex['read'] is False and (ex['reason'] or '').startswith(want)


def structure_ok(row, ex):
    want = row.get('structure_expect')
    if not want: return True
    if ex['edges'] != want['edges'] or len(ex['clause_reads']) != len(want['clauses']): return False
    for got, w in zip(ex['clause_reads'], want['clauses']):
        c = got['clause']
        if not got['readable'] or c is None: return False
        if (c['predicate'], c['roles'], c['polarity'], c['tense'], c['voice']) != (w['predicate'], w['roles'], w['polarity'], w['tense'], w['voice']): return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--placement')
    ap.add_argument('--fixture')
    ap.add_argument('--data', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    from verantyx import semantic_read as SR, semantic_reader as R, constructions
    from tools.bank_score.v2 import b1
    constructions.discover()
    isolation()
    if bool(a.placement) == bool(a.fixture):
        print('give exactly one of --placement / --fixture')
        sys.exit(2)
    answers = None
    if a.fixture:
        answers = {}
        for l in Path(a.fixture).read_text(encoding='utf-8').splitlines():
            if l.strip():
                r = json.loads(l)
                answers[r['term']] = r['answer']
    make = (lambda: FixtureQuery(answers)) if a.fixture else (lambda: R.CoarseQuery(a.placement))
    summaries, details, misses = {}, [], []
    totals = collections.Counter()
    for path in a.data.split(','):
        rows = [json.loads(l) for l in Path(path).read_text(encoding='utf-8').splitlines() if l.strip()]
        c = collections.Counter()
        for r in rows:
            q = make()
            out = SR.read(r['input'], r['lang'], placement=q)
            verdict = b1.judge(r['expect'], r['lang'], out)['verdict']
            q2 = make()
            ex = R.w3c7_explain_ja(r['input'], q2)
            if answers is not None: misses += q.misses + q2.misses
            c['rows'] += 1
            c['out_read' if out['readable'] else 'out_abstain'] += 1
            c['v_' + verdict] += 1
            entry_bad = (r['entry_expect'] == 'read') != bool(out['readable'])
            exp_bad = not expect_ok(r, ex)
            st_bad = not structure_ok(r, ex)
            c['entry_mismatch'] += entry_bad
            c['expect_mismatch'] += exp_bad
            c['structure_mismatch'] += st_bad
            details.append({'id': r['id'], 'file': Path(path).name, 'input': r['input'], 'verdict': verdict, 'readable': out['readable'], 'entry_expect': r['entry_expect'],
                            'w3c7_expect': r['w3c7_expect'], 'path': ex['path'], 'reason': ex['reason'], 'edges': ex['edges'], 'entry_mismatch': entry_bad,
                            'expect_mismatch': exp_bad, 'structure_mismatch': st_bad, 'reasons': None if out['readable'] else out['abstain']['reasons']})
            if verdict == 'correct' and r['behavior'] == 'read' and not out['readable']: pass
        summaries[Path(path).name] = dict(c)
        totals.update(c)
    keys = ('rows', 'out_read', 'out_abstain', 'v_correct', 'v_abstain', 'v_misread', 'v_incomplete', 'v_UNJUDGED', 'entry_mismatch', 'expect_mismatch', 'structure_mismatch')
    for name, s in summaries.items():
        print('%s ' % name + ' '.join('%s=%d' % (k, s.get(k, 0)) for k in keys))
    print('TOTAL ' + ' '.join('%s=%d' % (k, totals.get(k, 0)) for k in keys))
    print('misread=%d incomplete=%d unjudged=%d' % (totals['v_misread'], totals['v_incomplete'], totals['v_UNJUDGED']))
    for d in details:
        if d['verdict'] in ('misread', 'incomplete', 'UNJUDGED') or d['entry_mismatch'] or d['expect_mismatch'] or d['structure_mismatch']:
            print('MISMATCH %s %s verdict=%s readable=%s entry_expect=%s w3c7_expect=%s path=%s reason=%s flags=%s' % (
                d['id'], d['input'], d['verdict'], d['readable'], d['entry_expect'], d['w3c7_expect'], d['path'], d['reason'],
                ''.join(k[0] for k in ('entry_mismatch', 'expect_mismatch', 'structure_mismatch') if d[k])))
    if answers is not None: print('words_missing_from_the_fixture=%s' % json.dumps(sorted(set(misses)), ensure_ascii=False))
    Path(a.out).write_text(json.dumps({'summary': summaries, 'total': dict(totals), 'words_missing_from_the_fixture': sorted(set(misses)), 'rows': details}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
