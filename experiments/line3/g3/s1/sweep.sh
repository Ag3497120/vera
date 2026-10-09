#!/bin/sh
# G3-e / S1 sweep: the window cache once, then the question runs (fulllead, bank2 intra2 + unans), then the summary.
# usage: sweep.sh CACHE_DIR [WORKERS=6]      (run from the repository root; PYTHONHASHSEED=0 is set here)
set -e
CACHE=${1:?cache dir}; W=${2:-6}
PY=${PY:-python3}; export PYTHONPATH=. PYTHONHASHSEED=0
R=experiments/line3/g3/s1/results; M=experiments/line3/g3/s1/measure_slide.py
mkdir -p "$R"
run() { tag=$1; pre=$2; shift 2; $PY $M "$pre" "$R/ask_fulllead_${pre}_${tag}.jsonl" --cache "$CACHE" --workers "$W" "$@"; }
# 1. the window cache (39 s with 6 workers on the Pro); the first run places it, the others only read it
run three fast --agreement three --build
# 2. the two agreement rules at the three presets
run two_if_single_edge fast --agreement two_if_single_edge
for pre in standard full; do run three $pre --agreement three; run two_if_single_edge $pre --agreement two_if_single_edge; done
# 3. variants at fast (L-644, L-645, L-649)
run two_if_single_edge-wnone fast --agreement two_if_single_edge --within none
run two_if_single_edge-sent fast --agreement two_if_single_edge --hold sentences
run two_if_single_edge-rep fast --agreement two_if_single_edge --members representative
run two_if_single_edge-standins fast --agreement two_if_single_edge --standins on
# 4. the exact skip on the real corpus (L-646) and the summary (with the reach rows)
$PY experiments/line3/g3/s1/skip_check.py "$CACHE" "$R/skip_check.txt" 1 two_if_single_edge representative
$PY experiments/line3/g3/s1/gold_loss.py "$CACHE" "$R/gold_loss.txt"          # review: why the seated golds are not agreed
$PY experiments/line3/g3/s1/summarize.py "$R" experiments/line3/t10/results --cache "$CACHE"
