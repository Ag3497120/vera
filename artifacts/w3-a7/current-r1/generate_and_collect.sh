#!/bin/sh
set -eu

VERA_WORKTREE=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a7-S
VERA_PYTHON=/Users/motonisihikoudai/vera-wiring/env/bin/python
VERA_ARTIFACTS="$VERA_WORKTREE/artifacts/w3-a7/current-r1"
VERA_GENERATOR="$VERA_WORKTREE/tools/gen_coarse_evidence.py"
VERA_JUDGE="$VERA_WORKTREE/artifacts/w3-a7/current-r2/trial_judge.py"
VERA_EVENTS="$VERA_ARTIFACTS/trial_runs.jsonl"
VERA_RUN_DIR="$VERA_WORKTREE/build/coarse-W3a/full/r10/gen_role_v3"
VERA_CODEX=/opt/homebrew/bin/codex
export PYTHONPATH="$VERA_WORKTREE"
export PYTHONDONTWRITEBYTECODE=1

cd "$VERA_WORKTREE"
shasum -a 256 -c "$VERA_ARTIFACTS/freeze.sha256"
"$VERA_PYTHON" "$VERA_GENERATOR" prompt --kind role | cmp - "$VERA_ARTIFACTS/prompt_role_v2.txt"
if "$VERA_PYTHON" "$VERA_JUDGE" gate --root "$VERA_WORKTREE" \
  --freeze "$VERA_ARTIFACTS/freeze.sha256" --events "$VERA_EVENTS"; then
  :
else
  printf '%s\n' 'latest frozen trial is not a completed PASS; production role generation is held' >&2
  exit 2
fi

mkdir -p "$VERA_RUN_DIR"
date '+%Y-%m-%d %H:%M:%S %z' > "$VERA_ARTIFACTS/generation.started"
"$VERA_PYTHON" "$VERA_GENERATOR" run \
  --kind role \
  --needs "$VERA_ARTIFACTS/needs_role_v3.jsonl" \
  --out-dir "$VERA_RUN_DIR" \
  --codex-bin "$VERA_CODEX" \
  --effort medium \
  --batch-size 40 --slots 4 --max-calls 624 --max-retries 2
"$VERA_PYTHON" "$VERA_GENERATOR" collect \
  --kind role --out-dir "$VERA_RUN_DIR" \
  --out "$VERA_RUN_DIR/role_frames.jsonl"
"$VERA_PYTHON" "$VERA_GENERATOR" summarize \
  --kind role --out-dir "$VERA_RUN_DIR" \
  --out "$VERA_RUN_DIR/summary.json"
date '+%Y-%m-%d %H:%M:%S %z' > "$VERA_ARTIFACTS/generation.finished"
