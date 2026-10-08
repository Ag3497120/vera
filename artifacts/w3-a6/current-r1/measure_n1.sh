#!/bin/sh
set -eu

VERA_WORKTREE=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S
VERA_PYTHON=/Users/motonisihikoudai/vera-wiring/env/bin/python
VERA_SCRATCH=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/codex-w3-a6-current-r1
export PYTHONPATH="$VERA_WORKTREE"
export PYTHONDONTWRITEBYTECODE=1

date '+%Y-%m-%d %H:%M:%S %z' > "$VERA_WORKTREE/artifacts/w3-a6/current-r1/n1.started"
"$VERA_PYTHON" "$VERA_WORKTREE/artifacts/w3-a6/scripts/n1_query_bytes.py" \
  "$VERA_WORKTREE" /Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1 \
  "$VERA_SCRATCH/r7_current.tsv" > "$VERA_WORKTREE/artifacts/w3-a6/current-r1/n1_r7_current.txt"
"$VERA_PYTHON" "$VERA_WORKTREE/artifacts/w3-a6/scripts/n1_query_bytes.py" \
  "$VERA_WORKTREE" /Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2 \
  "$VERA_SCRATCH/r8_current.tsv" > "$VERA_WORKTREE/artifacts/w3-a6/current-r1/n1_r8_current.txt"
"$VERA_PYTHON" "$VERA_WORKTREE/artifacts/w3-a6/scripts/n1_query_bytes.py" \
  "$VERA_WORKTREE" none "$VERA_SCRATCH/none_current.tsv" \
  "$VERA_WORKTREE/artifacts/w3-a6/n1/noplace_words.txt" > "$VERA_WORKTREE/artifacts/w3-a6/current-r1/n1_none_current.txt"
date '+%Y-%m-%d %H:%M:%S %z' > "$VERA_WORKTREE/artifacts/w3-a6/current-r1/n1.finished"
