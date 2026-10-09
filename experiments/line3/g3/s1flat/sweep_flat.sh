#!/bin/sh
# G3-f sweep: S1-flat on bank2 fulllead RUN, mid, the G3-c3 placements (window caches, z_deep slide / order), the window cross read FLAT
# (slide_flat.ask_flat).  Phase REP: members=representative (the first member of each growth), search budget 512,64, fast + standard, both
# z_deep; plus the budget sensitivity at fast (64,8 and 4096,512, z_deep slide).  Phase ALL: members=all (every strictly stable member) at fast, z slide, evidence
# plain and window, on the 57 questions whose windows hold <= 700 starts.
# Phase EV: evidence=window (the pair count of the flat reader = the window's label-blind slide + order counts, L-714), members=representative, fast +
# standard, both z_deep; phase SEAT: two_seat=n_only (one seat per shared unit, L-703), fast, z_deep slide.
# usage: sweep_flat.sh CACHE_ROOT [WORKERS=6] [PHASE=rep|ev|seat|both (= rep + ev + seat)|all]    CACHE_ROOT holds slide/ and order/ (window caches; built with --build when absent)
# (run from the repository root; PYTHONHASHSEED=0 is set here; PY = the Pro python)
set -e
CACHE=${1:?cache root}; W=${2:-6}; PHASE=${3:-both}
PY=${PY:-python3}; export PYTHONPATH=. PYTHONHASHSEED=0
R=experiments/line3/g3/s1flat/results; M=experiments/line3/g3/s1flat/measure_flat.py
mkdir -p "$R"
run() {  # name preset zdeep members budget [extra args]
  name=$1; preset=$2; zd=$3; mem=$4; bud=$5; shift 5
  echo "== $name: $preset, z_deep $zd, members $mem, budget $bud $*: load $(uptime | sed 's/.*averages: //')" >&2
  $PY $M "$preset" "$R/flat_$name.jsonl" --cache "$CACHE/$zd" --z-deep "$zd" --members "$mem" --budget "$bud" --workers "$W" --resume --build "$@"
}
if [ "$PHASE" = rep ] || [ "$PHASE" = both ]; then
  for zd in slide order; do
    run "fast_z${zd}_rep" fast $zd representative 512,64
    run "standard_z${zd}_rep" standard $zd representative 512,64
  done
  run "fast_zslide_rep_b64-8" fast slide representative 64,8
  run "fast_zslide_rep_b4096-512" fast slide representative 4096,512
fi
if [ "$PHASE" = ev ] || [ "$PHASE" = both ]; then
  for zd in slide order; do
    run "fast_z${zd}_rep_ev-window" fast $zd representative 512,64 --evidence window
    run "standard_z${zd}_rep_ev-window" standard $zd representative 512,64 --evidence window
  done
fi
if [ "$PHASE" = seat ] || [ "$PHASE" = both ]; then
  run "fast_zslide_rep_twoseat-n" fast slide representative 512,64 --two-seat n_only
fi
if [ "$PHASE" = all ]; then
  # members=all costs one settled start per strictly stable member (fulllead z slide at fast: 65128 starts over the 94 questions, ~0.4 s each): the
  # questions whose windows read at fast hold <= 700 starts together (57 questions, 17808 starts) are run, listed in results/all_subset_ids.txt
  # (made by subset_ids.py); the others are NOT run.
  IDS=$(cat "$R/all_subset_ids.txt")
  run "fast_zslide_all_sub" fast slide all 512,64 --ids "$IDS"
  run "fast_zslide_all_sub_ev-window" fast slide all 512,64 --evidence window --ids "$IDS"
fi
