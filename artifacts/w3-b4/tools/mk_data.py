#!/usr/bin/env python3
"""W3-b4: write tests/reading_soundness/ja_r10_w3b4.jsonl from mk_data_sentences.py (see mk_data_core.py). Usage: cd <tree> && PYTHONPATH=<tree> python artifacts/w3-b4/tools/mk_data.py --out FILE"""
import argparse
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mk_data_core as C
import mk_data_sentences as S

ap = argparse.ArgumentParser(); ap.add_argument('--out', required=True)
a = ap.parse_args()
root = os.path.realpath(os.environ.get('PYTHONPATH', '.').split(os.pathsep)[0])
foreign = [m.__file__ for k, m in list(sys.modules.items()) if (k == 'verantyx' or k.startswith('verantyx.')) and getattr(m, '__file__', None) and not os.path.realpath(m.__file__).startswith(root + os.sep)]
if foreign: print('ISOLATION FAILED', foreign); sys.exit(2)
S.build()
print('rows=%d' % C.write(a.out))
