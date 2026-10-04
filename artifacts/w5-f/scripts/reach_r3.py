#!/usr/bin/env python3
"""W5-f r3 S2: reach check of the CONTROL rows only (read_or_abstain) of w5f_gates_r3.jsonl on the public entry (none / fake). Abstain rows' outputs are not printed. Usage: reach_r3.py ROWS.jsonl"""
import importlib.util, json, sys, os
from pathlib import Path
T = Path(__file__).resolve().parents[3]
os.environ.pop('VERA_PLACEMENT', None)
spec = importlib.util.spec_from_file_location('fk', T / 'tests/reading_soundness/w3b1_fakes.py'); fk = importlib.util.module_from_spec(spec); spec.loader.exec_module(fk)
from verantyx import semantic_read as SR, semantic_reader as R
assert R.__file__.startswith(str(T)), R.__file__
for l in Path(sys.argv[1]).read_text(encoding='utf-8').splitlines():
    r = json.loads(l)
    if r['expect'] != 'read_or_abstain': continue
    if r['placement'] is None:
        out = SR.read(r['text'], 'ja', placement=None)
    else:
        out = SR.read(r['text'], 'ja', placement=fk.MapQuery({k: fk.answer(v, term=k) for k, v in r['placement'].items()}))
    cl = out.get('clauses') or []
    print('\t'.join([r['id'], 'readable=%s' % out['readable'], json.dumps(cl[0].get('roles') if len(cl) == 1 else None, ensure_ascii=False), json.dumps(r['roles'], ensure_ascii=False)]))
