#!/bin/sh
# G3-k review fixes (L-810..): the grammar-on runs again on the fixed tree (the layer-1 seeds without the unread stand-ins; the marks via_standin / read_via_standin), 10 workers.
# The superseded runs are kept as *_on_layer1_leak.* (measured while the layers' bundles still held every stand-in's cross).
# usage (from the repo root): PYTHONPATH=. PYTHONHASHSEED=0 sh experiments/line3/g3/k/sweep_review.sh
PY=${PY:-/Users/motonisihikoudai/vera-wiring/env/bin/python}
C=${CACHE:-/Users/motonisihikoudai/Projects/vera-impl/cache/t11}
R=experiments/line3/g3/k/results
$PY experiments/line3/g3/k/measure_k.py fast $R/bank3_uwpa_fast_on.jsonl --cache $C --grammar on --kinds unknown-word,paraphrase --workers 10 --resume > $R/bank3_uwpa_fast_on.jsonl.log 2>&1
$PY experiments/line3/g3/k/measure_k.py fast $R/bank2_fast_on.jsonl --cache $C --grammar on --bank bank2 --workers 10 --resume > $R/bank2_fast_on.jsonl.log 2>&1
