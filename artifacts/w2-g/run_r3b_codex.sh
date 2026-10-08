#!/bin/sh
cd /Users/motonisihikoudai/Projects/vera-impl/wt/W2-g-S || exit 1
sh artifacts/w2-g/py_live.sh tests/conduct_ask/w2g/run_map_bank.py --items tests/conduct_ask/w2g2/items.jsonl --frames tests/conduct_ask/w2g2/frames \
  --mode codex --second codex --subset artifacts/w2-g/live/w2g2_r3_subset.txt --workers 3 --run-budget 130 \
  --out artifacts/w2-g/live/w2g2/codex_codex_r3b_order > artifacts/w2-g/live/w2g2/codex_codex_r3b_order.log 2>&1
