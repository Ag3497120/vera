#!/bin/sh
# usage: dump_calls.sh before|after   (records every conduct_ask call of the 8 conversation test files + traps3 + traps4 + traps5)
cd /Users/motonisihikoudai/Projects/vera-impl/wt/W2-c-S
MODE=$1
FILES="tests/test_conduct_ask_authority.py tests/test_conduct_ask_options.py tests/test_conduct_ask_order.py tests/test_conduct_ask_policy.py tests/test_conduct_ask_traps.py tests/test_conduct_ask_traps2.py tests/test_conduct_ask_traps3.py tests/test_conduct_ask_traps4.py tests/test_conduct_ask_traps5.py tests/test_conduct_ask_vocab.py tests/test_conduct_ask_cli.py"
rm -f artifacts/w2-c/r6/calls_$MODE.jsonl
PLUG="-p answered_dump"
[ "$MODE" = before ] && PLUG="-p r5_swap -p answered_dump"
env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 PYTHONPATH=$PWD:$PWD/artifacts/w2-c/r6 CA_LOG=$PWD/artifacts/w2-c/r6/calls_$MODE.jsonl \
  /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -p no:cacheprovider $PLUG -q $FILES 2>&1 | tail -4
