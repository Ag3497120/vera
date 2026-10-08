#!/usr/bin/env python3
"""W3-b5 K206 (docs 10F, table change records 1 and 2): the rows of the frozen data whose result changed because rows of the table were taken out (`narrowed_rows.json`), and the rows whose
frozen expectation was wrong before the narrowing too, for a fact of the reader that the design had not seen (`expect_exceptions.json`, each with the observation pinned).
  --before JSON  a run of run_rows.py with the table as it was registered (artifacts/w3-b5/data_check_before_narrowing.json)
  --now JSON     a run of run_rows.py after the narrowing (no --exceptions / --narrowed given to it)
A row is a NARROWED row when it does not do what its frozen expectation says now and its (entry, diagnosis) is not the one it had before. An EXCEPTION is a row that does not do what its
frozen expectation says and did the same before. Nothing here is a misread: a row judged misread/incomplete/UNJUDGED stops the tool (exit 1).
Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-b5/tools/mk_narrowed_rows.py --before J --now J --out-narrowed F --out-exceptions F"""
import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parents[3]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--before', required=True); ap.add_argument('--now', required=True)
    ap.add_argument('--out-narrowed', required=True); ap.add_argument('--out-exceptions', required=True)
    a = ap.parse_args()
    sys.path.insert(0, str(TREE / 'tests'))
    spec = importlib.util.spec_from_file_location('tw5_mk_narrowed', TREE / 'tests' / 'test_semantic_read_w3b5.py')
    tw = importlib.util.module_from_spec(spec); sys.modules['tw5_mk_narrowed'] = tw; spec.loader.exec_module(tw)
    before = {x['id']: x for x in json.loads(Path(a.before).read_text(encoding='utf-8'))}
    now = {x['id']: x for x in json.loads(Path(a.now).read_text(encoding='utf-8'))}
    data = {r['id']: r for r in tw.DATA}
    narrowed, exceptions = {}, []
    for rid, x in now.items():
        if x['verdict'] in ('misread', 'incomplete', 'UNJUDGED'):
            print('STOP: %s is %s' % (rid, x['verdict'])); sys.exit(1)
        if x['entry_ok'] and x['w3b2_ok']: continue
        b = before[rid]; r = data[rid]
        if (b['entry'], b['w3b2']) != (x['entry'], x['w3b2']):
            assert x['entry'] == 'abstain', rid
            narrowed[rid] = {'input': r['input'], 'frozen_entry_expect': r['entry_expect'], 'frozen_w3b5_expect': r['w3b5_expect'], 'entry_before': b['entry'], 'w3b2_before': b['w3b2'],
                             'observed_entry': x['entry'], 'observed_w3b2': x['w3b2']}
        else:
            ex = tw.SR.typed_explain_ja(r['input'], tw.query_of(r))
            kind = ('reread_abstains_before_a_gate' if x['w3b2'].startswith('PLACEMENT_REREAD_ABSTAINS') else
                    'confirmed_frame_checks_the_first_role' if x['w3b2'].startswith('PLACEMENT_FRAME_PARTICLE_NOT_CONFIRMED') else
                    'frame_row_does_not_cover_every_candidate' if x['w3b2'].startswith('PLACEMENT_MULTIPLE') and r['entry_expect'] == 'read' else 'other')
            exceptions.append({'id': rid, 'input': r['input'], 'kind': kind, 'frozen_entry_expect': r['entry_expect'], 'frozen_w3b5_expect': r['w3b5_expect'], 'observed_entry': x['entry'],
                               'observed_explain': ex, 'observed_verdict': x['verdict']})
    Path(a.out_narrowed).write_text(json.dumps({'note': 'rows whose result changed when the rows of table change records 1 and 2 were taken out (docs 10F K206); the frozen expectations are not rewritten',
                                               'rows': narrowed}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    Path(a.out_exceptions).write_text(json.dumps({'note': 'frozen expectations that a fact of the reader made wrong before the narrowing too (no misread); the observation is pinned', 'kinds': sorted({e['kind'] for e in exceptions}),
                                                  'exceptions': exceptions}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('narrowed=%d exceptions=%d kinds=%s' % (len(narrowed), len(exceptions), sorted({e['kind'] for e in exceptions})))


if __name__ == '__main__':
    main()
