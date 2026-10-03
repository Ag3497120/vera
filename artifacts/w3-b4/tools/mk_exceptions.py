#!/usr/bin/env python3
"""W3-b4 step 8 (ii): the rows of the frozen data whose registered REASON (`w3b4_expect`) is not what the entry says although the entry does what the row registered (read / refused)
and is never wrong: the reason that was registered was a prediction about a placement fact or about the reader that turned out different. The expectation of the row is not changed; the
observed result is written here (as W3-b2's w3b2_expect_exceptions.json) and the test pins it. Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-b4/tools/mk_exceptions.py --out FILE
Each id and its kind are chosen by hand from the output of run_rows.py; the observed values are computed here."""
import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parents[3]
KINDS = {
    'adjunct_arms_are_role_distributions_only': 'the filler stands in an adjunct (a place with で, a time with に) and every arm of its answer is a role distribution (role@...): the evidence gate 5 (K62) stops it '
                                                 'first, whatever its types are (SLOT_EVIDENCE_ONLY); the registered reason named the later test of the types',
    'entry_refuses_before_the_typed_step': 'the entry itself refuses the input before any typed step runs (the reader finds no predicate token), so `typed_explain_ja` has nothing to say (all None)',
    'reread_refuses_before_the_derived_gate': 'the entry\'s own rules refuse the re-read first (the head 疲れた looks like a potential: UNDETERMINED_MODALITY), before the derived-head gate that was registered',
}
CHOSEN = [
    ('W3B4-ACT-A-008', 'adjunct_arms_are_role_distributions_only'), ('W3B4-CHANGE-A-013', 'adjunct_arms_are_role_distributions_only'),
    ('W3B4-CREATE-A-023', 'adjunct_arms_are_role_distributions_only'), ('W3B4-CONSUME-A-006', 'adjunct_arms_are_role_distributions_only'),
    ('W3B4-CONSUME-A-001', 'adjunct_arms_are_role_distributions_only'), ('W3B4-CONSUME-A-002', 'adjunct_arms_are_role_distributions_only'),
    ('W3B4-CONSUME-A-003', 'adjunct_arms_are_role_distributions_only'),
    ('W3B4-CHANGE-A-025', 'entry_refuses_before_the_typed_step'),
    ('W3B4-EMOTION-A-035', 'reread_refuses_before_the_derived_gate'),
]


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True)
    a = ap.parse_args()
    sys.path.insert(0, str(TREE / 'tests'))
    spec = importlib.util.spec_from_file_location('tw4', TREE / 'tests' / 'test_semantic_read_w3b4.py')
    tw = importlib.util.module_from_spec(spec); sys.modules['tw4'] = tw; spec.loader.exec_module(tw)
    rows = {r['id']: r for r in tw.DATA}
    out = []
    for rid, kind in CHOSEN:
        r = rows[rid]
        res = tw.SR.read(r['input'], placement=tw.query_of(r))
        ex = tw.explain(r)
        out.append({'id': rid, 'input': r['input'], 'kind': kind, 'frozen_entry_expect': r['entry_expect'], 'frozen_w3b4_expect': r['w3b4_expect'],
                    'observed_entry': 'read' if res['readable'] else 'abstain', 'observed_explain': ex, 'observed_verdict': tw.b1.judge(r['expect'], 'ja', res)['verdict']})
    Path(a.out).write_text(json.dumps({'kinds': KINDS, 'exceptions': out}, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    print('exceptions=%d' % len(out))


if __name__ == '__main__':
    main()
