"""W5-d: run a question file (place / noplace) through run_questions.run_one + classify and report the counts.
Copied from the intermediary's proto_evidence/qrun.py (W5-d plan, step 0.4); changed only to also write a per-question JSONL.

    run_questions_both.py <tree> <questions.jsonl> <docs_dir> <placement_dir> place|noplace [<out.jsonl>]

stdout: one JSON line {cls, status, unchecked_fillers_in_FILLED_TIE, wrong}. The JSONL (when given) has one row per question: id, status, fillers, excluded reasons.
"""
import json, sys, importlib.util
from pathlib import Path
from collections import Counter
tree, qfile, docs, pdir, mode = sys.argv[1:6]
outp = sys.argv[6] if len(sys.argv) > 6 else None
sys.path.insert(0, tree)
spec = importlib.util.spec_from_file_location('rq', Path(tree) / 'tests/observe/question/run_questions.py')
rq = importlib.util.module_from_spec(spec); spec.loader.exec_module(rq)
import verantyx.observe as O
assert O.__file__.startswith(tree), O.__file__
cls = Counter(); st = Counter(); wrong = []; unchecked_filled = 0; rows = []
for line in open(qfile, encoding='utf-8'):
    q = json.loads(line)
    if mode == 'noplace': q = dict(q, placement=None)
    res, _ = rq.run_one(q, docs, pdir)
    out = json.loads(res.stdout) if res.stdout else {}
    a = out.get('answer') or {}
    s = a.get('status'); st[s] += 1
    c, d = rq.classify(q.get('truth'), s, a); cls[c] += 1
    if c == 'WRONG': wrong.append((q['id'], d))
    unch = 0
    if s in ('FILLED', 'TIE'):
        unch = sum(1 for f in a['fillers'] if f['hole_type_check']['verdict'] != 'AGREE')
        unchecked_filled += unch
    rows.append({'id': q['id'], 'status': s, 'class': c,
                 'fillers': [{'surface': f['surface'], 'verdict': f['hole_type_check']['verdict']} for f in a.get('fillers', [])],
                 'excluded': [{'surface': (e.get('surface') if isinstance(e, dict) else None), 'reason': (e.get('reason') if isinstance(e, dict) else str(e))} for e in a.get('excluded', [])],
                 'reasons': a.get('reasons'), 'unchecked_fillers': unch})
if outp:
    Path(outp).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')
print(json.dumps({'cls': cls, 'status': st, 'unchecked_fillers_in_FILLED_TIE': unchecked_filled, 'wrong': wrong}, ensure_ascii=False))
