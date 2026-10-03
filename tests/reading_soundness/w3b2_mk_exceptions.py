#!/usr/bin/env python3
"""W3-b2: the declaration of the rows of the frozen data whose expectation the entry does not meet, `w3b2_expect_exceptions.json`.

The data (w3b2_*.jsonl) was frozen before the entry was run, and its `entry_expect` / `w3b2_expect` were predicted from the placement and the code of the reader. For some rows the
prediction was wrong because of a fact about the reader of the base commit (listed in w3b2_common.EXCEPTION_KINDS). The data is NOT changed: this script runs every row with the fixture
(w3b2_fakes.FixtureQuery), takes the rows where the entry does not read as `entry_expect` says or the diagnosis does not say what `w3b2_expect` says, and writes for each the observed
result and the fact of the reader that explains it (`exception_kind`: a function of the reader alone). A row that no fact explains makes the script stop (exit 1): it would be a
defect of the new paths, not of the prediction. Usage: cd <tree> && PYTHONPATH=<tree> python tests/reading_soundness/w3b2_mk_exceptions.py [--out FILE]
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent.parent))
import w3b2_common as C


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', default=str(HERE / 'w3b2_expect_exceptions.json'))
    a = ap.parse_args()
    from verantyx import semantic_read as SR
    from tools.bank_score.v2 import b1
    import w3b2_fakes as F
    C.isolation()
    out, unexplained = [], []
    for name in C.DATA:
        for r in C.load_data(name):
            o = SR.read(r['input'], placement=F.FixtureQuery())
            ex = SR.typed_explain_ja(r['input'], F.FixtureQuery())
            verdict = b1.judge(r['expect'], 'ja', o)['verdict']
            e = r['w3b2_expect']
            ok = (ex['w3b2'] == 'READ') if e == 'READ' else ((ex['frame'] or '').startswith(e[6:]) if e.startswith('FRAME:') else (ex['w3b2'] or '').startswith(e))
            entry_ok = (r['entry_expect'] == 'read') == bool(o['readable']) and not (r['entry_expect'] == 'read' and verdict != 'correct')
            if entry_ok and ok: continue
            kind = C.exception_kind(r['input'])
            if kind == 'UNEXPLAINED' or verdict in ('misread', 'incomplete', 'UNJUDGED'): unexplained.append(r['id'])
            out.append({'id': r['id'], 'input': r['input'], 'kind': kind, 'entry_expect': r['entry_expect'], 'w3b2_expect': r['w3b2_expect'],
                        'observed_entry': 'read' if o['readable'] else 'abstain', 'observed_verdict': verdict, 'observed_explain': ex})
    doc = {'note': 'rows of the frozen data whose registered expectation the entry does not meet because of a fact about the reader of the base commit (kind). The data is not changed. '
                   'Written by w3b2_mk_exceptions.py with the fixture of the placement r6.', 'kinds': list(C.EXCEPTION_KINDS), 'exceptions': out}
    Path(a.out).write_text(json.dumps(doc, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
    kinds = {}
    for x in out: kinds[x['kind']] = kinds.get(x['kind'], 0) + 1
    print('declared=%d kinds=%s unexplained=%s' % (len(out), json.dumps(kinds, ensure_ascii=False, sort_keys=True), unexplained))
    sys.exit(1 if unexplained else 0)


if __name__ == '__main__':
    main()
