#!/bin/sh
# usage: run_build.sh <out-subdir under build/coarse-W3a> <stride> <logname> [extra args...]
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S
B=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a
OUT=$1; STRIDE=$2; LOG=$3; shift 3
mkdir -p "$B/$(dirname "$OUT")"
exec "$W/artifacts/w3-a/py.sh" "$W/tools/build_coarse_placement.py" build \
  --jawiki /Users/motonisihikoudai/vera-wiring/data/jawiki_leads.full.jsonl \
  --codex-dir /Users/motonisihikoudai/Projects/vera-impl/build/p4-W1c \
  --out "$B/$OUT" --sample-stride "$STRIDE" --jobs 8 \
  --exclude-terms "$W/tests/coarse_place/data/unknown_words.jsonl" \
  --exclude-terms "$W/tests/coarse_place/data/dev_unknown.jsonl" \
  --holdout "$W/artifacts/w3-a/holdout_2000.jsonl" \
  --holdout "$W/artifacts/w3-a/dev_l1_1000.jsonl" \
  --frozen "$W/artifacts/w3-a/FROZEN.json" "$@" > "$W/artifacts/w3-a/$LOG" 2>&1
