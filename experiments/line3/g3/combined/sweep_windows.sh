#!/bin/sh
# G3-g: the live window part of the combined list: fast and standard, evidence plain and window, members representative, z_deep slide
# (the G3-c3 default placements).  usage: sweep_windows.sh WINDOW_CACHE_DIR [WORKERS=6]   (from the repository root; PY = the Pro python)
set -e
CACHE=${1:?window cache dir (z_deep slide)}; W=${2:-6}
PY=${PY:-python3}; export PYTHONPATH=. PYTHONHASHSEED=0
R=experiments/line3/g3/combined/results; mkdir -p "$R"
for P in fast standard; do
  for EV in plain window; do
    echo "== $P $EV: load $(uptime | sed 's/.*averages: //')" >&2
    $PY experiments/line3/g3/combined/measure_windows.py "$P" "$R/win_${P}_${EV}.jsonl" --cache "$CACHE" --evidence "$EV" --workers "$W" --resume
  done
done
echo WINDOWSDONE >&2
