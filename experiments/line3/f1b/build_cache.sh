#!/bin/sh
# F1b: the question path reads EVERY cross of a tier (cycle.plan_read scans all seeds for the query units), so a probe needs the
# full ordered placement cache.  Built through the command itself (line3 build --group-insert ordered), 2 workers, tier by tier.
# usage: build_cache.sh CACHE_DIR
CACHE=$1
cd "$(dirname "$0")/../../.." || exit 1
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
for T in RUN WORD CHAR; do
  PYTHONHASHSEED=0 $PY -m verantyx.cli line3 build --data experiments/line3/bank2/data/fulllead_sents.jsonl --cache "$CACHE" \
      --tiers $T --group-insert ordered --workers 2 >> experiments/line3/f1b/build_cache.log 2>&1
done
echo done >> experiments/line3/f1b/build_cache.log
