#!/bin/sh
# usage: dev_iter_w3a2.sh <name> <config.json>  -- dev build from stage_full6.pkl, then dev measurements
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S
B=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a
$W/artifacts/w3-a/run_build_w3a2.sh dev/$1 build_dev_$1.log --stage-cache $B/dev/stage_full6.pkl --config $2 || exit 1
tail -1 $W/artifacts/w3-a/build_dev_$1.log | cut -c1-300
$W/artifacts/w3-a/dev_measure.sh $1
