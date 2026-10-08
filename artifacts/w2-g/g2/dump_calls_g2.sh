#!/bin/sh
# usage: dump_calls_g2.sh start|end   (records every conduct_ask call of tests/test_conduct_ask_*.py into artifacts/w2-g/g2/calls_<mode>.jsonl; a fresh file per mode)
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W2-g-S
cd /Users/motonisihikoudai/Projects/vera-impl/wt/W2-g-S || exit 1
MODE=$1
[ -e artifacts/w2-g/g2/calls_$MODE.jsonl ] && { echo "calls_$MODE.jsonl exists; refusing to overwrite"; exit 1; }
FILES=$(ls tests/test_conduct_ask_*.py)
env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 PYTHONPATH=$W:$W/artifacts/w2-g CA_LOG=$W/artifacts/w2-g/g2/calls_$MODE.jsonl \
  /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -p no:cacheprovider -p answered_dump -q $FILES 2>&1 | tail -4
