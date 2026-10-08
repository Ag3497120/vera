#!/bin/sh
# 8 runs, at most 2 worker processes (xargs -P 2); run from the repo root: sh experiments/line3/carry/c3b/run_all.sh
D=experiments/line3/carry/c3b
printf '%s\n' "WORD mid defer" "WORD mid close" "RUN mid defer" "RUN mid close" "WORD low defer" "WORD low close" "RUN low defer" "RUN low close" |
  xargs -P 2 -L 1 sh -c 'PYTHONPATH=. /Users/motonisihikoudai/vera-wiring/env/bin/python '$D'/c3b.py $0 $1 $2 300 '$D'/results/c3b_$0_$1_$2.json > '$D'/logs/c3b_$0_$1_$2.log 2>&1'
