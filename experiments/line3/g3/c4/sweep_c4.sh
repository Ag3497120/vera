#!/bin/sh
# G3-c4 sweep: the window cache once per z_deep rule (G3-c3 defaults), then the question runs at fast for the two agreement rules, then the tables.
# usage: sweep_c4.sh CACHE_ROOT [WORKERS=6]      (run from the repository root; PYTHONHASHSEED=0 is set here; PY = the Pro python)
set -e
CACHE=${1:?cache root}; W=${2:-6}
PY=${PY:-python3}; export PYTHONPATH=. PYTHONHASHSEED=0
R=experiments/line3/g3/c4/results; M=experiments/line3/g3/c4/measure_c4.py
mkdir -p "$R"
for zd in slide order; do
  mkdir -p "$CACHE/$zd"
  $PY $M fast "$R/ask_fulllead_fast_z$zd-three.jsonl" --z-deep $zd --cache "$CACHE/$zd" --workers "$W" --agreement three --build
  $PY $M fast "$R/ask_fulllead_fast_z$zd-two_if_single_edge.jsonl" --z-deep $zd --cache "$CACHE/$zd" --workers "$W" --agreement two_if_single_edge
done
$PY experiments/line3/g3/c4/cache_stats.py "$CACHE"
$PY experiments/line3/g3/c4/c4_summary.py "$CACHE"
