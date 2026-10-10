#!/bin/sh
# G3-k (b): bank2 fulllead (intra2 69 + unans 25), combined fast, 10 workers (same tree, the T10 / T11 ordered cache): grammar on; then the ORDER-ONLY attribution run on the
# bank3 unknown-word + paraphrase items (--standins off); then grammar off, the clean baseline of the same tree.  (equiv_off.py, run by hand, compares the off path with the T10 records.)
# usage (from the repo root): PYTHONPATH=. PYTHONHASHSEED=0 sh experiments/line3/g3/k/sweep_bank2.sh
PY=${PY:-/Users/motonisihikoudai/vera-wiring/env/bin/python}
C=${CACHE:-/Users/motonisihikoudai/Projects/vera-impl/cache/t11}
R=experiments/line3/g3/k/results
$PY experiments/line3/g3/k/measure_k.py fast $R/bank2_fast_on.jsonl --cache $C --grammar on --bank bank2 --workers 10 --resume > $R/bank2_fast_on.jsonl.log 2>&1
# attribution: the grammar ORDER alone (stand-ins dropped from the intake) on the bank3 unknown-word + paraphrase items
$PY experiments/line3/g3/k/measure_k.py fast $R/bank3_uwpa_fast_on_order_only.jsonl --cache $C --grammar on --standins off --kinds unknown-word,paraphrase --workers 10 --resume > $R/bank3_uwpa_fast_on_order_only.jsonl.log 2>&1
# the clean off baseline of the same tree (the windows read on the committed default placements, which the recorded G3-g window records are not)
$PY experiments/line3/g3/k/measure_k.py fast $R/bank2_fast_off.jsonl --cache $C --grammar off --bank bank2 --workers 10 --resume > $R/bank2_fast_off.jsonl.log 2>&1
