#!/bin/zsh
# S3: the vocabulary layer (K401, K405-K407) and its X2 measurement. usage: build_vocab.sh (the outputs must not exist)
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W12-c1-S
A=$W/artifacts/w12-c1; B=$W/build/initial-layers
cd $W
uptime > $A/x2_uptime_before.txt
env -u VERA_PLACEMENT_LAYER PYTHONPATH=$W PYTHONDONTWRITEBYTECODE=1 /usr/bin/time -l /Users/motonisihikoudai/vera-wiring/env/bin/python tools/build_initial_layers.py vocab \
  --jawiki /Users/motonisihikoudai/vera-wiring/data/jawiki_leads.full.jsonl --heldout-root /Users/motonisihikoudai/vera-codex-corpus \
  --placement /Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2 --out $B/vocab/vocab.sqlite --report $A/x2_vocab.json \
  --jobs 2 --hash-inputs --sample-out $A/x2_sample60.tsv > $B/vocab/build.log 2>&1
echo "vocab(pass2) rc=$?" >> $B/build_done.txt
