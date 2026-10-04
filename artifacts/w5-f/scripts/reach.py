#!/usr/bin/env python3
"""W5-f S2: which rows of w5f_gates.jsonl reach the typed step (typed_explain_ja has a trigger) in the tree it runs in. Usage: reach.py TREE ROWS.jsonl > reach.txt
Prints one line per F1/F2 row: id, reach (0/1), readable of the entry, the two triggers. Reach is a property of the sentence and the fake placement, not of the gates."""
import importlib.util, json, sys
from pathlib import Path
T = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location('fk', T / 'tests/reading_soundness/w3b1_fakes.py'); fk = importlib.util.module_from_spec(spec); spec.loader.exec_module(fk)
from verantyx import semantic_read as SR, semantic_reader as R
assert R.__file__.startswith(str(T)), R.__file__
for l in Path(sys.argv[2]).read_text(encoding='utf-8').splitlines():
    r = json.loads(l)
    if r['group'] not in ('F1', 'F2'): continue
    mk = lambda: fk.MapQuery({k: fk.answer(v, term=k) for k, v in r['placement'].items()})
    out = SR.read(r['text'], 'ja', placement=mk()); ex = SR.typed_explain_ja(r['text'], mk())
    reach = int(bool(ex['w3b1_trigger'] or ex['w3b2_trigger']))
    print('\t'.join([r['id'], str(reach), str(out['readable']), str(ex['w3b1_trigger']), str(ex['w3b2_trigger']), str(ex['w3b1']), str(ex['w3b2'])]))
