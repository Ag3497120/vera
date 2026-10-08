#!/bin/sh
# F1: all builds (4 workers each, one after another).  repo root.
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
export PYTHONHASHSEED=0
FL=experiments/line3/bank2/data/fulllead_sents.jsonl
S3=experiments/line3/data/S300.jsonl
for D in $FL $S3; do
  for M in ordered whole reverse; do
    for T in RUN WORD CHAR; do
      $PY experiments/line3/f1/build.py $D $T $M mid 4
    done
  done
done
echo ALLDONE
