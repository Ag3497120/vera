#!/usr/bin/env python3
"""W1-a5 step 4: facts of the BASE entry and of the reader for candidate sentences (one sentence per line; `#` lines and blank lines are skipped). Nothing of W1-a5 is
asked: run it in the tree of the base commit (`cd <base> && PYTHONPATH=<base> python <this file> --inputs FILE --out TSV`). Per sentence: readable, the clauses of the entry
(predicate, roles, polarity, tense), the reasons, the clauses of the reader's `document_view` (rule, predicate, roles, polarity, time, unsupported), and the tokens with their
part of speech. The loaded verantyx modules must all be under PYTHONPATH."""
import argparse
import json
import os
import sys
from pathlib import Path

ap = argparse.ArgumentParser(); ap.add_argument('--inputs', required=True); ap.add_argument('--out', required=True); ap.add_argument('--tokens', action='store_true')
a = ap.parse_args()
root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
from verantyx import semantic_read as SR
from verantyx import semantic_reader as R
lines = []
for raw in Path(a.inputs).read_text(encoding='utf-8').splitlines():
    s = raw.strip()
    if s and not s.startswith('#'): lines.append(s)
rows = []
for text in lines:
    toks = [(w.surface, w.feature.pos1, w.feature.pos2, w.feature.pos3, w.feature.cForm, getattr(w.feature, 'lemma', None)) for w, x, y in R._tokens(text)] if a.tokens else None
    out = SR.read(text, 'ja', placement=None)
    view = R.document_view({'d': text})
    vc = [(c.rule, c.predicate, [(r.name, r.span.text) for r in c.roles], c.polarity, c.time, list(c.unsupported)) for c in view.clauses]
    if out['readable']:
        res = 'READ ' + json.dumps([{k: c[k] for k in ('predicate', 'roles', 'polarity', 'tense', 'modality', 'voice')} for c in out['clauses']], ensure_ascii=False)
    else:
        res = 'ABSTAIN ' + json.dumps(out['abstain']['reasons'], ensure_ascii=False)
    rows.append('%s\t%s\tview=%s\tunread=%d%s' % (text, res, json.dumps(vc, ensure_ascii=False), len(view.unread), ('\ttokens=' + json.dumps(toks, ensure_ascii=False)) if toks else ''))
foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
if foreign: print('ISOLATION FAILED', foreign); sys.exit(2)
Path(a.out).write_text('\n'.join(rows) + '\n', encoding='utf-8')
print('sentences=%d' % len(rows))
