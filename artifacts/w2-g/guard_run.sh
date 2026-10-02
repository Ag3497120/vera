#!/bin/sh
# the conduct tests with a guard that refuses (and logs) any start of a codex / claude process
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W2-g-S
cd $W
rm -f artifacts/w2-g/guard_log.jsonl
FILES=$(ls tests/test_conduct_ask_*.py tests/test_conduct_map*.py tests/test_llm_choice*.py)
env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 PYTHONPATH=$W:$W/artifacts/w2-g W2G_GUARD_LOG=$W/artifacts/w2-g/guard_log.jsonl \
  /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -p no:cacheprovider -p no_live_guard -q $FILES 2>&1 | tail -4
