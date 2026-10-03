#!/bin/sh
cd /Users/motonisihikoudai/Projects/vera-impl/wt/W2-g-S || exit 1
sh artifacts/w2-g/py_live.sh -m verantyx.conduct_ask --frame tests/conduct_ask/w2g2/frames/x04_compost.md \
  --question "In the neighbouring district's project, is the weekly report built before the handbook page?" --option Yes --option No \
  --vocab-llm codex --map-second codex --vocab-ledger artifacts/w2-g/live/review_t06/ledger.jsonl > artifacts/w2-g/live/review_t06/result.json 2> artifacts/w2-g/live/review_t06/stderr.txt
