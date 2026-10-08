#!/bin/sh
# usage: dev_measure.sh <name under build/coarse-W3a/dev>   (W3-a2) dev data only
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S
B=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a
N=$1
P=$B/dev/$N
for m in l2 l3 l1; do $W/artifacts/w3-a/py.sh $W/artifacts/w3-a/measure_w3a.py $m --placement $P --data dev | tail -1 | cut -c1-600; done
$W/artifacts/w3-a/py.sh $W/artifacts/w3-a/hub_spread.py --placement $P --out $W/artifacts/w3-a/hub_spread_dev_$N.txt | head -4
$W/artifacts/w3-a/py.sh $W/artifacts/w3-a/recovered_precision.py --placement $P --out $W/artifacts/w3-a/recovered_precision_dev_$N.txt | head -3
