#!/bin/sh
# the conduct tests with a guard that refuses (and logs) any start of a codex / claude process; output to artifacts/w2-g/g2/
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W2-g-S
cd /Users/motonisihikoudai/Projects/vera-impl/wt/W2-g-S || exit 1
[ -e artifacts/w2-g/g2/guard_log.jsonl ] && { echo "guard_log.jsonl exists; refusing to overwrite"; exit 1; }
FILES=$(ls tests/test_conduct_ask_*.py tests/test_conduct_map*.py tests/test_llm_choice*.py)
env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 PYTHONPATH=$W:$W/artifacts/w2-g W2G_GUARD_LOG=$W/artifacts/w2-g/g2/guard_log.jsonl \
  /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -p no:cacheprovider -p no_live_guard -q $FILES 2>&1 | tail -4
