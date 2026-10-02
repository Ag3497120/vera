#!/bin/sh
cd /Users/motonisihikoudai/Projects/vera-impl/wt/W2-g-S || exit 1
sh artifacts/w2-g/py_live.sh -m verantyx.conduct_ask --frame tests/conduct_ask/w2g2/frames/x04_compost.md \
  --question "Which unit of mass would volunteers prefer for the reports?" \
  --vocab-llm codex --map-second codex --vocab-ledger artifacts/w2-g/live/review_v06/ledger.jsonl > artifacts/w2-g/live/review_v06/result.json 2> artifacts/w2-g/live/review_v06/stderr.txt
