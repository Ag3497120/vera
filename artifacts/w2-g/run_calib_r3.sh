#!/bin/sh
cd /Users/motonisihikoudai/Projects/vera-impl/wt/W2-g-S || exit 1
sh artifacts/w2-g/py_live.sh tests/conduct_ask/w2g/run_map_bank.py --items artifacts/w2-g/live/calib_r3/items.jsonl --frames tests/conduct_ask/fixtures/frames \
  --mode codex --second codex --workers 3 --run-budget 120 --timeout 400 --out artifacts/w2-g/live/calib_r3/run1 > artifacts/w2-g/live/calib_r3/run1.log 2>&1
