#!/usr/bin/env python3
"""W3-b4 round 3 (docs 10D, table change record 3): record which rows of the FROZEN data (the first 323 rows of tests/reading_soundness/ja_r10_w3b4.jsonl) have a different diagnosis
(`typed_explain_ja(...)['w3b2']`) because the rows place/で/PLACE of P_ACT, P_CREATE and P_EMOTION were taken out of the table. The old table is rebuilt IN MEMORY (the three rows are put back
into `TYPED_FRAMES_W3B4` and taken out again in a `finally`); no file of the tree is changed except the --out file. The tool refuses to write when a collected row has no で, when its new
diagnosis is not `PLACEMENT_PARTICLE_NOT_IN_FRAME:<type>:で` or when its type is not one of the three.
Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-b4/tools/mk_narrowed_rows.py --data tests/reading_soundness/ja_r10_w3b4.jsonl --out artifacts/w3-b4/narrowed_rows.json"""
import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parents[3]
DE_ROW = ('place', ('で',), ('PLACE',), 'adjunct')
TYPES = ('P_ACT', 'P_CREATE', 'P_EMOTION')


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path)); mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; spec.loader.exec_module(mod); return mod


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--data', required=True); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    F = load('w3b2_fakes_in_mk_narrowed_rows', TREE / 'tests' / 'reading_soundness' / 'w3b2_fakes.py')
    from verantyx import semantic_read as SR
    from verantyx import semantic_reader as R
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign: print('ISOLATION FAILED', foreign); sys.exit(2)

    def answer_of(word, spec):      # the same construction as query_of of tests/test_semantic_read_w3b4.py
        if 'state' in spec: return F.bare(spec['state'], term=word)
        if spec.get('origin') == 'estimated': return F.to_estimated(F.answer(spec['top'], decided_by=['seed'], term=word), spec['basis'])
        return F.answer(spec['top'], decided_by=spec['decided_by'], term=word)

    def explain(row): return SR.typed_explain_ja(row['input'], F.MapQuery({w: answer_of(w, s) for w, s in row['placement'].items()}))

    rows = [json.loads(l) for l in Path(a.data).read_text(encoding='utf-8').splitlines() if l.strip()]
    frozen, appended = rows[:323], rows[323:]
    exceptions = {e['id'] for e in json.loads((TREE / 'artifacts' / 'w3-b4' / 'expect_exceptions.json').read_text(encoding='utf-8'))['exceptions']}
    now = {r['id']: explain(r) for r in frozen}
    saved = {t: R.TYPED_FRAMES_W3B4[t] for t in TYPES}
    try:
        for t in TYPES: R.TYPED_FRAMES_W3B4[t] = saved[t] + (DE_ROW,)
        before = {r['id']: explain(r) for r in frozen}
    finally:
        for t in TYPES: R.TYPED_FRAMES_W3B4[t] = saved[t]
    changed = {}
    for r in frozen:
        if before[r['id']] == now[r['id']]: continue
        w = now[r['id']]['w3b2']
        assert '\u3067' in r['input'] and r['pred_type'] in TYPES, r['id']
        assert w == 'PLACEMENT_PARTICLE_NOT_IN_FRAME:%s:\u3067' % r['pred_type'], (r['id'], w)
        changed[r['id']] = {'pred_type': r['pred_type'], 'frozen_entry_expect': r['entry_expect'], 'frozen_w3b4_expect': r['w3b4_expect'], 'declared_exception': r['id'] in exceptions,
                            'diagnosis_with_the_rows_put_back': before[r['id']]['w3b2'], 'observed_w3b2': w}
    t0 = (TREE / 'artifacts' / 'w3-b4' / 'r3' / 'narrow_prereg_time.txt').read_text(encoding='utf-8').splitlines()[0]
    out = {
        'about': 'Rows of the FROZEN data (the first 323 rows of tests/reading_soundness/ja_r10_w3b4.jsonl) whose diagnosis changed when the rows place/で/PLACE of P_ACT, P_CREATE and P_EMOTION were taken out of the table '
                 '(docs/READING_SOUNDNESS.md 10D, table change record 3). They are NOT rewritten: the tests and tools/run_rows.py read such a row as "the entry refuses it, and the diagnosis is observed_w3b2". '
                 'Made by tools/mk_narrowed_rows.py (the old table rebuilt in memory). Only narrowing is recorded; nothing is widened.',
        'narrowed_at': t0, 'recorded_in': 'docs/READING_SOUNDNESS.md 10D, table change record 3; artifacts/w3-b4/r3/narrow_prereg_time.txt',
        'decided_by': 'auditor, 2026-10-04 04:20 (ticket, last section): way (b), K165 exception',
        'reason': 'The adjunct で is place, or instrument / cause: the conventions (section 2) decide no type for instrument and cause and a PLACE word takes them (右 = the right hand, 段差 = the cause), '
                  'so place/で/PLACE is not disjoint from them: the table read an instrument / a cause as a place.',
        'source': 'review of round 2 (review.r2.md), F4 batches d (6 sentences) and c (4 sentences with 口) and B1 (b)',
        'rows_removed': [{'type': t, 'role': 'place', 'particle': '\u3067', 'types': ['PLACE'], 'kind': 'adjunct'} for t in TYPES],
        'rows_appended_to_the_data': [r['id'] for r in appended],
        'data_rows_refused_by_the_narrowing': changed,
    }
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    by = {}
    for v in changed.values(): by.setdefault(v['pred_type'], [0, 0])[0 if v['frozen_entry_expect'] == 'read' else 1] += 1
    print('rows_changed=%d' % len(changed), json.dumps({k: {'frozen_read': v[0], 'frozen_abstain': v[1]} for k, v in sorted(by.items())}), 'declared_exceptions=%d' % sum(1 for v in changed.values() if v['declared_exception']),
          'appended=%d' % len(appended))


if __name__ == '__main__':
    main()
