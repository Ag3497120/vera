#!/bin/sh
set -eu

VERA_WORKTREE=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S
VERA_PYTHON=/Users/motonisihikoudai/vera-wiring/env/bin/python
VERA_R8=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2
VERA_R9="$VERA_WORKTREE/build/coarse-W3a/full/r9"
VERA_ARTIFACTS="$VERA_WORKTREE/artifacts/w3-a6/current-r1"
export PYTHONPATH="$VERA_WORKTREE"
export PYTHONDONTWRITEBYTECODE=1

cd "$VERA_WORKTREE"
mkdir -p "$VERA_R9/gen_ntype" "$VERA_R9/gen_role"

# Rebuild both frozen target lists from r8/run2 before any model call.
"$VERA_PYTHON" "$VERA_WORKTREE/tools/gen_coarse_evidence.py" needs \
  --kind ntype --placement "$VERA_R8" --n 60000 \
  --out "$VERA_ARTIFACTS/needs_ntype.jsonl" \
  --meta "$VERA_ARTIFACTS/needs_ntype.meta.json"
"$VERA_PYTHON" "$VERA_WORKTREE/tools/gen_coarse_evidence.py" needs \
  --kind role --placement "$VERA_R8" --n 60000 \
  --out "$VERA_ARTIFACTS/needs_role.jsonl" \
  --meta "$VERA_ARTIFACTS/needs_role.meta.json"

# This round freezes the prompt, targets, expectations, and this script; generation is deferred.
shasum -a 256 -c "$VERA_ARTIFACTS/freeze.sha256"
date '+%Y-%m-%d %H:%M:%S %z' > "$VERA_ARTIFACTS/generation.started"

"$VERA_PYTHON" "$VERA_WORKTREE/tools/gen_coarse_evidence.py" run \
  --kind ntype \
  --needs "$VERA_ARTIFACTS/needs_ntype.jsonl" \
  --out-dir "$VERA_R9/gen_ntype" \
  --codex-bin /opt/homebrew/bin/codex \
  --batch-size 40 --slots 4 --max-calls 207 --max-retries 2
"$VERA_PYTHON" "$VERA_WORKTREE/tools/gen_coarse_evidence.py" collect \
  --kind ntype --out-dir "$VERA_R9/gen_ntype" \
  --out "$VERA_R9/gen_ntype/noun_types.jsonl"
"$VERA_PYTHON" "$VERA_WORKTREE/tools/gen_coarse_evidence.py" summarize \
  --kind ntype --out-dir "$VERA_R9/gen_ntype" \
  --out "$VERA_R9/gen_ntype/summary.json"

"$VERA_PYTHON" "$VERA_WORKTREE/tools/gen_coarse_evidence.py" run \
  --kind role \
  --needs "$VERA_ARTIFACTS/needs_role.jsonl" \
  --out-dir "$VERA_R9/gen_role" \
  --codex-bin /opt/homebrew/bin/codex \
  --batch-size 40 --slots 4 --max-calls 624 --max-retries 2
"$VERA_PYTHON" "$VERA_WORKTREE/tools/gen_coarse_evidence.py" collect \
  --kind role --out-dir "$VERA_R9/gen_role" \
  --out "$VERA_R9/gen_role/role_frames.jsonl"
"$VERA_PYTHON" "$VERA_WORKTREE/tools/gen_coarse_evidence.py" summarize \
  --kind role --out-dir "$VERA_R9/gen_role" \
  --out "$VERA_R9/gen_role/summary.json"

date '+%Y-%m-%d %H:%M:%S %z' > "$VERA_ARTIFACTS/generation.finished"
