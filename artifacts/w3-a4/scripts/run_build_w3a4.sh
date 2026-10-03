#!/bin/sh
# usage: run_build_w3a4.sh <output name> <log name> [extra args...]
# (W3-a4) a copy of artifacts/w5-d/scripts/run_build_w5d.sh that points at THIS tree and writes to build/coarse-W3a/full/r8/<name>.
# Inputs are those of r7 (same files).  r6's generated frames are read only.  Logs go to artifacts/w3-a4/.
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a4-S
A=$W/artifacts/w3-a4
B=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a
R6=$B/full/r6
R7=$B/full/r7
R8=$B/full/r8
GN=$B/generated
OUT=$1; LOG=$2; shift 2
mkdir -p "$R8"
exec "$A/scripts/py.sh" "$W/tools/build_coarse_placement.py" build \
  --jawiki /Users/motonisihikoudai/vera-wiring/data/jawiki_leads.full.jsonl \
  --codex-dir /Users/motonisihikoudai/Projects/vera-impl/build/p4-W1c \
  --out "$R8/$OUT" --jobs 5 \
  --exclude-terms "$W/tests/coarse_place/data/unknown_words.jsonl" \
  --exclude-terms "$W/tests/coarse_place/data/dev_unknown.jsonl" \
  --exclude-terms "$W/artifacts/w3-a3/exclude_coined.jsonl" \
  --holdout "$W/artifacts/w3-a/holdout_2000.jsonl" \
  --holdout "$W/artifacts/w3-a/dev_l1_1000.jsonl" \
  --frozen "$W/artifacts/w3-a/FROZEN.json" \
  --generated "$GN/definitions.jsonl" --generated-ledger "$GN/ledger.jsonl" \
  --generated-frames "$R6/gen_pred/frames.jsonl" --generated-frames-ledger "$R6/gen_pred/ledger.jsonl" \
  --compare-to "$R7/run1" \
  --config "$A/config_w3a4.json" "$@" > "$A/$LOG" 2>&1
