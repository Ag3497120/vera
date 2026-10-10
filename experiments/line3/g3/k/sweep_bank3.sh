#!/bin/sh
# G3-k (a): bank3 unknown-word (18) + paraphrase (20), combined fast, grammar on then off, 10 workers each (same tree, same caches).
# usage (from the repo root): PYTHONPATH=. PYTHONHASHSEED=0 sh experiments/line3/g3/k/sweep_bank3.sh
PY=${PY:-/Users/motonisihikoudai/vera-wiring/env/bin/python}
C=${CACHE:-/Users/motonisihikoudai/Projects/vera-impl/cache/t11}
R=experiments/line3/g3/k/results
for G in on off; do
  $PY experiments/line3/g3/k/measure_k.py fast $R/bank3_uwpa_fast_$G.jsonl --cache $C --grammar $G --kinds unknown-word,paraphrase --workers 10 --resume > $R/bank3_uwpa_fast_$G.jsonl.log 2>&1
done
