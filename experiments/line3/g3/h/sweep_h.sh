#!/bin/sh
# G3-h sweep: the 12 cells of the grid {arm_cap budget, x} x {z_deep slide, order, order_window} x {seat_empty_axis allow, deny}, each with the four runs
# fast/standard x evidence plain/window (members representative, budget 512/64), one cell after the other (6 workers inside a cell).
# usage: sweep_h.sh CACHE_DIR [WORKERS=6]    (from the repository root; PYTHONHASHSEED=0 is set here; PY = the Pro python; the caches are built by build_caches.py)
set -e
CACHE=${1:?cache dir}; W=${2:-6}
PY=${PY:-python3}; export PYTHONPATH=. PYTHONHASHSEED=0
H=experiments/line3/g3/h; R=$H/results; mkdir -p "$R" "$H/logs"
for SEAT in allow deny; do
  for CAP in budget x; do
    for ZD in slide order order_window; do
      echo "== $CAP $ZD $SEAT: load $(uptime | sed 's/.*averages: //')" >&2
      $PY $H/measure_h.py --cache "$CACHE" --arm-cap $CAP --z-deep $ZD --seat-empty $SEAT --out-dir "$R" --workers "$W" --resume 2> "$H/logs/measure_${CAP}_${ZD}_${SEAT}.log"
      tail -4 "$H/logs/measure_${CAP}_${ZD}_${SEAT}.log" >&2
    done
  done
done
echo SWEEPDONE >&2
