#!/bin/sh
# frozen-data measurements on a placement dir; each writes a NEW numbered eval_runs directory
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S
P=$1
for m in l2 l3 l1 pred l5; do
  $W/artifacts/w3-a/py.sh $W/artifacts/w3-a/measure_w3a.py $m --placement $P | tail -1 | cut -c1-900
done
