#!/bin/sh
# usage: k606_capture.sh <outdir>   (run from the tree root, PYTHONPATH set). Same fixed inputs before and after.
O=$1; mkdir -p "$O"; F=$PWD/artifacts/w16-t6b/k606_fixture; PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
for n in none led_add led_run; do
  L=""; [ "$n" != none ] && L="--ledger $F/$n/events.jsonl"
  rm -f "$O/rec_$n.jsonl" 2>/dev/null
  $PY -P -m verantyx.cli attest $F/rep.md --tree $F/tree $L --json > "$O/$n.json"; echo $? > "$O/$n.rc"
  $PY -P -m verantyx.cli attest $F/rep.md --tree $F/tree $L --record "$O/rec_$n.jsonl" > "$O/$n.txt"; echo $? > "$O/$n.rec.rc"
done
