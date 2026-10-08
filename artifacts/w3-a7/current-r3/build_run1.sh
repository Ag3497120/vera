#!/bin/sh
set -eu

VERA_ROOT=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a7-S
VERA_A6=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S
VERA_SHARED=/Users/motonisihikoudai/Projects/vera-impl/build
VERA_PYTHON=/Users/motonisihikoudai/vera-wiring/env/bin/python
VERA_R9="$VERA_A6/build/coarse-W3a/full/r9"
VERA_R10="$VERA_ROOT/build/coarse-W3a/full/r10"
R3_ART="$VERA_ROOT/artifacts/w3-a7/current-r3"

export PYTHONPATH="$VERA_ROOT"
export PYTHONDONTWRITEBYTECODE=1
cd "$VERA_ROOT"

test ! -e "$VERA_R10/run1"
test ! -e "$R3_ART/build_run1.log"
date '+%Y-%m-%d %H:%M:%S %z' > "$R3_ART/build_started.txt"
if "$VERA_PYTHON" tools/build_coarse_placement.py build \
  --jawiki /Users/motonisihikoudai/vera-wiring/data/jawiki_leads.full.jsonl \
  --codex-dir "$VERA_SHARED/p4-W1c" \
  --out "$VERA_R10/run1" \
  --sample-stride 1 --jobs 5 \
  --exclude-terms tests/coarse_place/data/unknown_words.jsonl \
  --exclude-terms tests/coarse_place/data/dev_unknown.jsonl \
  --exclude-terms artifacts/w3-a3/exclude_coined.jsonl \
  --holdout artifacts/w3-a/holdout_2000.jsonl \
  --holdout artifacts/w3-a/dev_l1_1000.jsonl \
  --frozen artifacts/w3-a/FROZEN.json \
  --config artifacts/w3-a6/r9/r9_config_run2.json \
  --generated "$VERA_SHARED/coarse-W3a/generated/definitions.jsonl" \
  --generated-frames "$VERA_SHARED/coarse-W3a/full/r6/gen_pred/frames.jsonl" \
  --generated-frames-add "$VERA_SHARED/coarse-W3a/full/r8/gen_pred/frames.jsonl" \
  --generated-noun-types "$VERA_R9/gen_ntype/noun_types.jsonl" \
  --role-frames "$VERA_R10/gen_role_v3/role_frames.jsonl" \
  --compare-to "$VERA_R9/run2" > "$R3_ART/build_run1.log" 2>&1; then
  date '+%Y-%m-%d %H:%M:%S %z' > "$R3_ART/build_finished.txt"
else
  build_status=$?
  date '+%Y-%m-%d %H:%M:%S %z' > "$R3_ART/build_finished.txt"
  exit "$build_status"
fi
