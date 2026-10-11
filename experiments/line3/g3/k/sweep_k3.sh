#!/bin/sh
# G3-k3 (L-826..): the flat plane's read order eq_first with the stand-in seeds' crosses in the group holds_query_unit, grammar on, combined, fast, 10 workers.
#   (a) bank3 unknown-word + paraphrase  (b) bank2 fulllead intra2 (69)  (c) bank2 fulllead unans (25)
# The off / order-only / on-qcount_first / on-eq_first (G3-k2) records stay in results/ and are not rewritten; the order-only run under eq_first is unchanged by the group
# (no stand-in => no stand-in seed), so the G3-k2 record bank3_uwpa_fast_on_order_only_eq_first.jsonl is the attribution run here, too.
# usage (from the repo root): PYTHONPATH=. PYTHONHASHSEED=0 sh experiments/line3/g3/k/sweep_k3.sh
PY=${PY:-/Users/motonisihikoudai/vera-wiring/env/bin/python}
C=${CACHE:-/Users/motonisihikoudai/Projects/vera-impl/cache/t11}
R=experiments/line3/g3/k/results
M=experiments/line3/g3/k/measure_k.py
$PY $M fast $R/bank3_uwpa_fast_on_eq_first_group.jsonl --cache $C --grammar on --flat-order eq_first --kinds unknown-word,paraphrase --workers 10 --resume > $R/bank3_uwpa_fast_on_eq_first_group.jsonl.log 2>&1
$PY $M fast $R/bank2_intra2_fast_on_eq_first_group.jsonl --cache $C --grammar on --flat-order eq_first --bank bank2 --kinds intra2 --workers 10 --resume > $R/bank2_intra2_fast_on_eq_first_group.jsonl.log 2>&1
$PY $M fast $R/bank2_unans_fast_on_eq_first_group.jsonl --cache $C --grammar on --flat-order eq_first --bank bank2 --kinds unans --workers 10 --resume > $R/bank2_unans_fast_on_eq_first_group.jsonl.log 2>&1
