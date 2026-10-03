#!/bin/sh
# usage: dev_iter.sh <name> [config.json]  -- build (from the dev stage cache) and measure on the DEV data only
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S
B=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a
NAME=$1; CFG=$2
EXTRA=""
if [ -n "$CFG" ]; then EXTRA="--config $CFG"; fi
$W/artifacts/w3-a/run_build.sh dev/$NAME 1 build_dev_$NAME.log --stage-cache $B/dev/stage_full4.pkl $EXTRA || exit 1
tail -1 $W/artifacts/w3-a/build_dev_$NAME.log | cut -c1-260
P=$B/dev/$NAME
for m in l2 l3 l1; do $W/artifacts/w3-a/py.sh $W/artifacts/w3-a/measure_w3a.py $m --placement $P --data dev | tail -1 | cut -c1-700; done
