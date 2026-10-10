#!/bin/sh
# G3-k2 (L-819..): the flat plane's read order eq_first (E_Q first, the counts and the kind only inside an exact E_Q tie), grammar on, combined, fast, 10 workers.
#   (a) bank3 unknown-word + paraphrase  (b) bank2 fulllead intra2 (69)  (c) the order-only run of (a) under eq_first (--standins off; the attribution run of the SAME order)
# The off, order-only-qcount_first and on-qcount_first records of G3-k stay in results/ and are not rewritten.
# usage (from the repo root): PYTHONPATH=. PYTHONHASHSEED=0 sh experiments/line3/g3/k/sweep_k2.sh
PY=${PY:-/Users/motonisihikoudai/vera-wiring/env/bin/python}
C=${CACHE:-/Users/motonisihikoudai/Projects/vera-impl/cache/t11}
R=experiments/line3/g3/k/results
M=experiments/line3/g3/k/measure_k.py
$PY $M fast $R/bank3_uwpa_fast_on_eq_first.jsonl --cache $C --grammar on --flat-order eq_first --kinds unknown-word,paraphrase --workers 10 --resume > $R/bank3_uwpa_fast_on_eq_first.jsonl.log 2>&1
$PY $M fast $R/bank2_intra2_fast_on_eq_first.jsonl --cache $C --grammar on --flat-order eq_first --bank bank2 --kinds intra2 --workers 10 --resume > $R/bank2_intra2_fast_on_eq_first.jsonl.log 2>&1
$PY $M fast $R/bank3_uwpa_fast_on_order_only_eq_first.jsonl --cache $C --grammar on --flat-order eq_first --standins off --kinds unknown-word,paraphrase --workers 10 --resume > $R/bank3_uwpa_fast_on_order_only_eq_first.jsonl.log 2>&1
