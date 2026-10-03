#!/bin/sh
# usage: run_build_w3a3.sh <out dir under build/coarse-W3a/full/r6> <log name> [extra args...]
# (W3-a3) the inputs of run_build_w3a2.sh (a copy that points at THIS tree), plus the coined verbs
# (--exclude-terms: only the coined words, never a whole test-data file), the W3-a3 config file and the
# predicate frames when the caller passes --generated-frames.  Logs go to artifacts/w3-a3/.
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a3-S
B=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a
R6=$B/full/r6
GN=$B/generated
OUT=$1; LOG=$2; shift 2
mkdir -p "$(dirname "$R6/$OUT")"
exec "$W/artifacts/w3-a3/py.sh" "$W/tools/build_coarse_placement.py" build \
  --jawiki /Users/motonisihikoudai/vera-wiring/data/jawiki_leads.full.jsonl \
  --codex-dir /Users/motonisihikoudai/Projects/vera-impl/build/p4-W1c \
  --out "$R6/$OUT" --jobs 5 \
  --exclude-terms "$W/tests/coarse_place/data/unknown_words.jsonl" \
  --exclude-terms "$W/tests/coarse_place/data/dev_unknown.jsonl" \
  --exclude-terms "$W/artifacts/w3-a3/exclude_coined.jsonl" \
  --holdout "$W/artifacts/w3-a/holdout_2000.jsonl" \
  --holdout "$W/artifacts/w3-a/dev_l1_1000.jsonl" \
  --frozen "$W/artifacts/w3-a/FROZEN.json" \
  --generated "$GN/definitions.jsonl" --generated-ledger "$GN/ledger.jsonl" \
  --config "$W/artifacts/w3-a3/config_w3a3.json" "$@" > "$W/artifacts/w3-a3/$LOG" 2>&1
