#!/bin/sh
# usage: dump_calls.sh before|after   (records every conduct_ask call of tests/test_conduct_ask_*.py)
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W2-g-S
cd $W
MODE=$1
FILES=$(ls tests/test_conduct_ask_*.py)
rm -f artifacts/w2-g/calls_$MODE.jsonl
env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 PYTHONPATH=$W:$W/artifacts/w2-g CA_LOG=$W/artifacts/w2-g/calls_$MODE.jsonl \
  /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -p no:cacheprovider -p answered_dump -q $FILES 2>&1 | tail -4
