#!/bin/sh
# defer tower (C3b pack_overflow="defer"): fast and fast+index, then standard; run from the repo root.
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
C5=experiments/line3/carry/c5
export PYTHONPATH=. PYTHONHASHSEED=0
for p in fast standard; do
  $PY $C5/measure.py RUN low $p $C5/results/RUN_low_defer_$p.jsonl 1 none all defer > $C5/logs/RUN_low_defer_$p.log 2>&1
  $PY $C5/measure.py RUN low $p $C5/results/RUN_low_defer_${p}_index.jsonl 1 index all defer > $C5/logs/RUN_low_defer_${p}_index.log 2>&1
done
