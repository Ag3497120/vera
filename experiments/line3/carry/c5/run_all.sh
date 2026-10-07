#!/bin/sh
# C5 first measurement: two lanes (at most 2 worker processes at a time), run from the repo root.
# lane A: fast, standard, full (selected path); lane B: fast, standard, full (index descent).
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
C5=experiments/line3/carry/c5
export PYTHONPATH=. PYTHONHASHSEED=0
( for p in fast standard full; do $PY $C5/measure.py RUN low $p $C5/results/RUN_low_$p.jsonl 1 none > $C5/logs/RUN_low_$p.log 2>&1; done ) &
( for p in fast standard full; do $PY $C5/measure.py RUN low $p $C5/results/RUN_low_${p}_index.jsonl 1 index > $C5/logs/RUN_low_${p}_index.log 2>&1; done ) &
wait
