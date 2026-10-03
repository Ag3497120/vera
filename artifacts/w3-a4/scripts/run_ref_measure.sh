#!/bin/sh
# runs the reference measurements on r7/run1 and r8/run1 (one numbered directory each under artifacts/w3-a4/eval_runs/)
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a4-S
A=$W/artifacts/w3-a4
B=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a
for P in $B/full/r7/run1 $B/full/r8/run1; do
  for C in l1 l2 l3; do
    echo "== $C $P"; $A/scripts/py.sh $A/scripts/measure_w3a4.py $C --placement $P
  done
  echo "== verbs $P"; $A/scripts/py.sh $A/scripts/measure_w3a4.py verbs --placement $P --data $W/tests/coarse_place/data/verb_check_300.jsonl
done
