#!/usr/bin/env python3
"""W3-b4 round 4 (K188): run sentences with a case particle followed by a focus particle through the reading entry with the real placement r7, in the tree given by PYTHONPATH,
and print one line per sentence: the readability, the roles, the diagnosis of the typed re-read (when the tree has it). Run in the tree of the base commit and in this tree and compare the lines.
Usage: PYTHONPATH=<tree> python k188_probe.py OUT.tsv"""
import json
import os
import sys
R7 = '/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1'
SENTENCES = ['兄が倉庫へさえ行った。', '兄が駅からさえ走った。', '兄が弟にさえ話した。', '兄が絵をさえ描いた。', '去年、兄が東京にさえ行った。', '兄が倉庫へすら行った。', '兄が駅からすら走った。',
             '兄が弟にすら話した。', '兄が絵をすら描いた。', '兄が倉庫へこそ行った。', '兄が駅からこそ走った。', '兄が弟にこそ話した。', '兄が絵をこそ描いた。', '兄が倉庫へまで行った。',
             '兄が弟にまで話した。', '兄が倉庫へも行った。', '兄が駅からも走った。', '兄が弟にも話した。', '兄が絵をも描いた。']
root = os.path.realpath(os.environ['PYTHONPATH'].split(os.pathsep)[0])
from verantyx import semantic_read as SR
from verantyx import semantic_reader as R
assert os.path.realpath(SR.__file__).startswith(root + os.sep) and os.path.realpath(R.__file__).startswith(root + os.sep)
lines = []
for s in SENTENCES:
    out = SR.read(s, placement=R.CoarseQuery(R7))
    ex = SR.typed_explain_ja(s, R.CoarseQuery(R7)) if hasattr(SR, 'typed_explain_ja') else None
    roles = out['clauses'][0]['roles'] if out.get('readable') else None
    lines.append('%s\treadable=%s\troles=%s\ttyped=%s' % (s, out.get('readable'), json.dumps(roles, ensure_ascii=False), json.dumps(ex, ensure_ascii=False)))
open(sys.argv[1], 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
print('\n'.join(lines))
