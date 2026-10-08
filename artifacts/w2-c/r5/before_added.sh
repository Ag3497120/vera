#!/bin/sh
# the tests added to traps4 after the first before-fix run (the premise-sentence qualifier), run against the round-4 code
cd /Users/motonisihikoudai/Projects/vera-impl/wt/W2-c-S
env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 PYTHONPATH=$PWD:$PWD/artifacts/w2-c/r5 \
  /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -p no:cacheprovider -p r4_swap -v tests/test_conduct_ask_traps4.py -k "premise" 
