#!/usr/bin/env python3
"""W1-a5 (copied from artifacts/w3-b4/tools/check_hardcode_w3b4.py; ja_r12.jsonl added): tests/reading_soundness/check_hardcode.py (not changed) with the sentences of ja_r12.jsonl, ja_r10_w3b4.jsonl and of the four w3b2_* data files added to the sentences it looks for in the added
lines of `git diff <base> -- verantyx/` (the data of W3-b2 is added too, so that nothing of the sentences of the ticket's tables is in an added line). Same arguments (--base, --repo) and
the same exit code (1 when a proper noun, a numeric token or an English name of a sentence is in an added line).
Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-b4/tools/check_hardcode_w1a5.py --base df4f001"""
import importlib.util
import json
import os
import sys
from pathlib import Path

TREE = Path(__file__).resolve().parents[3]
RS = TREE / 'tests' / 'reading_soundness'
root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
spec = importlib.util.spec_from_file_location('check_hardcode_of_the_tree_w1a5', RS / 'check_hardcode.py')
CH = importlib.util.module_from_spec(spec); spec.loader.exec_module(CH)
_original = CH.sentences
EXTRA = ('ja_r12.jsonl', 'ja_r10_w3b4.jsonl', 'w3b2_frame.jsonl', 'w3b2_multiple.jsonl', 'w3b2_determiner.jsonl', 'w3b2_no.jsonl')
CH.sentences = lambda: _original() + [json.loads(l)['input'] for n in EXTRA for l in (RS / n).read_text(encoding='utf-8').splitlines() if l.strip()]
foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
if foreign: print('ISOLATION FAILED', foreign); sys.exit(2)
CH.main()
