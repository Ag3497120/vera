#!/bin/sh
# T10 sweep driver (run on the Air via tools/air.sh bg): for each preset, measure_ask.py then summarize.py.
# usage: sweep.sh CACHE_DIR GROUP_INSERT ON_COLLAPSE WORKERS PRESETS(comma) LAYERS(comma, ssp,path | ssp | none) [CORPUS=fulllead] [KINDS=all]
# Raw records: experiments/line3/t10/results/ask_<corpus>_<preset>_<gi>-<oc>.jsonl (git-ignored, --resume: a rerun continues).
CACHE=$1; GI=$2; OC=$3; W=$4; PRESETS=$5; LAYERS=$6; CORPUS=${7:-fulllead}; KINDS=${8:-all}
PY=${PY:-python3.11}        # Air: python3.11; Pro: /Users/motonisihikoudai/vera-wiring/env/bin/python (PYTHONPATH=. PYTHONHASHSEED=0)
cd "$(dirname "$0")/../../.." || exit 1
R=experiments/line3/t10/results
mkdir -p $R experiments/line3/t10/logs
for P in $(echo "$PRESETS" | tr ',' ' '); do
  echo "=== $P start $(date '+%F %T') load: $(uptime | sed 's/.*load averages*: //')"
  $PY experiments/line3/t10/measure_ask.py "$CORPUS" "$P" "$R/ask_${CORPUS}_${P}_${GI}-${OC}.jsonl" \
      --cache "$CACHE" --group-insert "$GI" --on-collapse "$OC" --layers "$LAYERS" --workers "$W" --kinds "$KINDS" --resume
  echo "=== $P measured $(date '+%F %T') exit $?"
  $PY experiments/line3/t10/summarize.py > experiments/line3/t10/logs/summarize_${P}.log 2>&1
  echo "=== $P summarized $(date '+%F %T') exit $?"
done
echo SWEEPDONE
