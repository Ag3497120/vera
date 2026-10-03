#!/bin/sh
# usage: dev_iter_gen.sh <name> <config.json> [stage cache name, default stage_full6.pkl]
#   -- dev build with the generated definitions, then dev measurements
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S
B=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a
G=$B/generated
STAGE=${3:-stage_full6.pkl}
$W/artifacts/w3-a/run_build_w3a2.sh dev/$1 build_dev_$1.log --stage-cache $B/dev/$STAGE --config $2 --generated $G/definitions.jsonl --generated-ledger $G/ledger.jsonl || exit 1
tail -1 $W/artifacts/w3-a/build_dev_$1.log | cut -c1-300
$W/artifacts/w3-a/dev_measure.sh $1
$W/artifacts/w3-a/py.sh $W/artifacts/w3-a/gen_precision.py --placement $B/dev/$1 --out $W/artifacts/w3-a/gen_precision_dev_$1.txt | head -6
