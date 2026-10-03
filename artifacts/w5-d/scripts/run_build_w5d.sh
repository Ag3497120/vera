#!/bin/sh
# usage: run_build_w5d.sh <run1|run2> <log name> [extra args...]
# (W5-d) a copy of artifacts/w3-a3/run_build_w3a3.sh that points at THIS tree and writes to build/coarse-W3a/full/r7/<run>.
# The inputs are those of r6 (same files, same sha256: see r7_inputs.sha256).  Logs go to artifacts/w5-d/.
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W5-d-S
B=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a
R7=$B/full/r7
GN=$B/generated
OUT=$1; LOG=$2; shift 2
mkdir -p "$R7"
exec "$W/artifacts/w5-d/scripts/py_build.sh" "$W/tools/build_coarse_placement.py" build \
  --jawiki /Users/motonisihikoudai/vera-wiring/data/jawiki_leads.full.jsonl \
  --codex-dir /Users/motonisihikoudai/Projects/vera-impl/build/p4-W1c \
  --out "$R7/$OUT" --jobs 5 \
  --exclude-terms "$W/tests/coarse_place/data/unknown_words.jsonl" \
  --exclude-terms "$W/tests/coarse_place/data/dev_unknown.jsonl" \
  --exclude-terms "$W/artifacts/w3-a3/exclude_coined.jsonl" \
  --holdout "$W/artifacts/w3-a/holdout_2000.jsonl" \
  --holdout "$W/artifacts/w3-a/dev_l1_1000.jsonl" \
  --frozen "$W/artifacts/w3-a/FROZEN.json" \
  --generated "$GN/definitions.jsonl" --generated-ledger "$GN/ledger.jsonl" \
  --config "$W/artifacts/w3-a3/config_w3a3.json" "$@" > "$W/artifacts/w5-d/$LOG" 2>&1
