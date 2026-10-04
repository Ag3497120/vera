#!/usr/bin/env python3
"""W3-b3: tests/reading_soundness/check_hardcode.py (not changed) with the sentences of the four new data files added to the sentences it looks for in the added lines of
`git diff <base> -- verantyx/`. Same arguments (--base, --repo) and the same exit code (1 when a proper noun, a numeric token or an English name of a sentence is in an added line).
Usage: cd <tree> && PYTHONPATH=<tree> python tests/reading_soundness/w3b3_check_hardcode.py --base c875ed3
"""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import w3b3_common as C

spec = importlib.util.spec_from_file_location('check_hardcode_of_the_tree_w3b3', HERE / 'check_hardcode.py')
CH = importlib.util.module_from_spec(spec); spec.loader.exec_module(CH)
_original = CH.sentences
CH.sentences = lambda: _original() + [r['input'] for name in C.DATA_ALL for r in C.load_data(name)]
C.isolation()
CH.main()
