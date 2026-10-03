#!/usr/bin/env python3
"""W1-a5 step 8: run the rows of a data file (the keys of tests/reading_soundness/ja_r12.jsonl; the unpublished sentences of the reviewer have the same keys) through the entry and write,
for each row: the verdict of the judge against `expect` (`tools.bank_score.v2.b1.judge`), whether the entry did what `entry_expect` says, whether the diagnosis
(`semantic_reader.w1a5_explain_ja`) is what `w1a5_expect` says (null fields are not checked; a row of --exceptions is compared with the pinned observation), the path and the reason.
A row without `entry_expect` / `w1a5_expect` is run as well (its `expect` is judged; nothing else is compared).
  --placement none      no placement (`read(text, placement=None)`)
  --placement fixture   the fixture placement of W3-b2 (tests/reading_soundness/w3b2_fakes.FixtureQuery)
  --placement DIR       the real placement in DIR (read only)
  --withdrawn FILE      round 2 (K218): the list of the rows turned back to an abstention (default artifacts/w1-a5/r2/k218_withdrawn_rows.json; a missing file is an empty list). A row of the list must
                        abstain and the path and the reason of the diagnosis must be the ones the list pins; it is then counted as entry_ok and w1a5_ok (the frozen `entry_expect` of such a row
                        says `read`: the rule of K218 turned it back). The summary line gets `withdrawn=N withdrawn_mismatch=M`.
Exit code 0 only when there is no misread / incomplete / UNJUDGED row and no mismatch.
Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w1-a5/tools/run_rows.py --data FILE --placement none|fixture|DIR --out JSON [--exceptions FILE] [--withdrawn FILE]"""
import argparse
import collections
import importlib.util
import json
import os
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parents[3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', required=True); ap.add_argument('--placement', default='none'); ap.add_argument('--out', required=True)
    ap.add_argument('--exceptions', default=str(TREE / 'artifacts' / 'w1-a5' / 'expect_exceptions.json'))
    ap.add_argument('--withdrawn', default=str(TREE / 'artifacts' / 'w1-a5' / 'r2' / 'k218_withdrawn_rows.json'))
    a = ap.parse_args()
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    from tools.bank_score.v2 import b1
    from verantyx import semantic_read as SR
    from verantyx import semantic_reader as R
    fixture = None
    if a.placement == 'fixture':
        spec = importlib.util.spec_from_file_location('w3b2_fakes_run_rows_w1a5', TREE / 'tests' / 'reading_soundness' / 'w3b2_fakes.py')
        fixture = importlib.util.module_from_spec(spec); spec.loader.exec_module(fixture)
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None)
               and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign:
        print('ISOLATION FAILED', foreign); sys.exit(2)
    exceptions = {}
    if a.exceptions and Path(a.exceptions).exists(): exceptions = {e['id']: e for e in json.loads(Path(a.exceptions).read_text(encoding='utf-8'))['exceptions']}
    withdrawn = {}
    if a.withdrawn and Path(a.withdrawn).exists(): withdrawn = {e['id']: e for e in json.loads(Path(a.withdrawn).read_text(encoding='utf-8'))['rows']}
    rows = [json.loads(l) for l in Path(a.data).read_text(encoding='utf-8').splitlines() if l.strip()]

    def placement():
        if a.placement == 'none': return None
        if a.placement == 'fixture': return fixture.FixtureQuery()
        return a.placement
    result, problems, wcount = [], collections.Counter(), collections.Counter()
    by_cat = collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        text = r['input']
        out = SR.read(text, 'ja', placement=placement())
        ex = R.w1a5_explain_ja(text, placement())
        verdict = b1.judge(r['expect'], 'ja', out)['verdict'] if 'expect' in r else None
        entry = 'read' if out['readable'] else 'abstain'
        entry_ok = (entry == r['entry_expect']) if 'entry_expect' in r else None
        want = r.get('w1a5_expect')
        w_ok = None
        wd = withdrawn.get(r.get('id'))
        if wd is not None:
            entry_ok = (entry == 'abstain')
            w_ok = (ex['path'], ex['reason']) == (wd['pinned_path'], wd['pinned_reason'])
            wcount['withdrawn'] += 1
            if not (entry_ok and w_ok) or verdict not in ('correct', 'abstain'):
                wcount['withdrawn_mismatch'] += 1; problems['withdrawn_mismatch'] += 1
        elif want is not None:
            if r['id'] in exceptions:
                p = exceptions[r['id']]; w_ok = (ex['path'], ex['reason']) == (p['observed_path'], p['observed_reason'])
            else:
                w_ok = want['path'] is None or ex['path'] == want['path']
                if want['reason_prefix'] is not None: w_ok = w_ok and ex['reason'] is not None and ex['reason'].startswith(want['reason_prefix'])
                if out['readable']:
                    c = out['clauses'][0]
                    if want['quantifiers'] is not None: w_ok = w_ok and c.get('quantifiers', {}) == want['quantifiers']
                    if want['flags'] is not None: w_ok = w_ok and c.get('flags', {}) == want['flags']
        rec = {'id': r.get('id'), 'category': r.get('category'), 'behavior': r.get('behavior'), 'input': text, 'entry': entry, 'entry_ok': entry_ok, 'verdict': verdict, 'w1a5_ok': w_ok,
               'path': ex['path'], 'reason': ex['reason'], 'aspect': ex['aspect'], 'adverbs': ex['adverbs'], 'quantity': ex['quantity'],
               'reasons': None if out['readable'] else out['abstain']['reasons'],
               'clause': out['clauses'][0] if out['readable'] else None}
        result.append(rec)
        cat = r.get('category') or '-'
        by_cat[cat]['rows'] += 1; by_cat[cat]['read'] += int(out['readable']); by_cat[cat]['correct_read'] += int(out['readable'] and verdict == 'correct')
        if verdict in ('misread', 'incomplete', 'UNJUDGED'): problems[verdict] += 1
        if entry_ok is False: problems['entry_expect_mismatch'] += 1
        if w_ok is False: problems['w1a5_expect_mismatch'] += 1
    Path(a.out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('rows=%d misread=%d incomplete=%d unjudged=%d entry_expect_mismatch=%d w1a5_expect_mismatch=%d placement=%s' % (
        len(rows), problems['misread'], problems['incomplete'], problems['UNJUDGED'], problems['entry_expect_mismatch'], problems['w1a5_expect_mismatch'], a.placement))
    print('withdrawn=%d withdrawn_mismatch=%d' % (wcount['withdrawn'], wcount['withdrawn_mismatch']))
    for cat in sorted(by_cat):
        c = by_cat[cat]
        print('%-9s rows=%d read=%d read_and_judged_correct=%d' % (cat, c['rows'], c['read'], c['correct_read']))
    paths = collections.Counter(x['path'] for x in result)
    print('paths: ' + json.dumps(dict(sorted(paths.items())), ensure_ascii=False))
    for x in result:
        if x['verdict'] in ('misread', 'incomplete', 'UNJUDGED') or x['entry_ok'] is False or x['w1a5_ok'] is False:
            print('PROBLEM', x['id'], x['input'], x['verdict'], x['entry'], x['path'], x['reason'])
    sys.exit(1 if any(problems.values()) else 0)


if __name__ == '__main__':
    main()
