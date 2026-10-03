#!/usr/bin/env python3
"""W3-b1 round 2: what the entry read BEFORE the K62 row `recipient / に / PERSON GROUP_ORG` was returned to "not read" (docs K62, table change record 1).
It puts the registered row back in memory (the file is not changed), runs the inputs of artifacts/w3-b1/entry_inputs.txt through the entry with the real placement, and
counts what is read newly against artifacts/w3-b1/entry_none.jsonl (no placement). Not a test; the numbers are the evidence of the sentences in docs K66.
Usage: cd <tree> && PYTHONPATH=<tree> VERA_PLACEMENT=<dir> python tests/reading_soundness/w3b1_before_row_returned.py > artifacts/w3-b1/before_row_returned.txt
"""
import json, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = HERE.parent.parent


def main():
    from verantyx import semantic_read as SR, semantic_reader as R
    from tools.bank_score.v2 import b1
    root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
    foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None)
               and not os.path.realpath(m.__file__).startswith(root + os.sep)]
    if foreign: print('ISOLATION FAILED', foreign); sys.exit(2)
    placement = os.environ.get('VERA_PLACEMENT')
    if not placement: print('NEEDS VERA_PLACEMENT'); sys.exit(2)
    rows = R.TYPED_FRAMES['P_COMMUNICATE']
    registered_row = ('recipient', ('に',), ('PERSON', 'GROUP_ORG'), 'arg')
    patched = dict(R.TYPED_FRAMES); patched['P_COMMUNICATE'] = (rows[0], registered_row) + tuple(rows[1:])
    texts = [json.loads(l)['text'] for l in (TREE / 'artifacts' / 'w3-b1' / 'entry_inputs.txt').read_text(encoding='utf-8').splitlines() if l.strip()]
    none = [json.loads(l) for l in (TREE / 'artifacts' / 'w3-b1' / 'entry_none.jsonl').read_text(encoding='utf-8').splitlines()]
    assert [n['text'] for n in none] == texts
    data = {r['input']: r for name in ('ja_r8.jsonl', 'en_r4.jsonl') for r in (json.loads(l) for l in (HERE / name).read_text(encoding='utf-8').splitlines() if l.strip())}
    out = {}
    for label, table in (('registered_table', patched), ('current_table', R.TYPED_FRAMES)):
        R.TYPED_FRAMES = table
        q = R.CoarseQuery(placement)
        newly = wrong = data_correct = 0; verdicts = {}
        for text, n in zip(texts, none):
            o = SR.read(text, placement=q)
            if o['readable'] and not n['out'].get('readable'): newly += 1
            if text in data:
                row = data[text]
                v = b1.judge(row['expect'], row['lang'], o)['verdict']
                verdicts[v] = verdicts.get(v, 0) + 1
                if o['readable'] and v == 'correct': data_correct += 1
                if v in ('wrong', 'misread'): wrong += 1
        out[label] = {'false->readable': newly, 'new_data_rows_read_correct': data_correct, 'new_data_wrong_or_misread': wrong, 'new_data_verdicts': verdicts}
    print('inputs=%d new_data_rows=%d' % (len(texts), len(data)))
    for k, v in out.items(): print(k, json.dumps(v, sort_keys=True))


if __name__ == '__main__':
    main()
