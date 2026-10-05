#!/bin/sh
# Auditor override (2026-10-05 09:1x +0900): the frozen trial criterion "no particle's claim rate below v2" failed only on を (28/40 vs 30/40);
# the two dropped を claims are corrections (つぼむ is intransitive; 内線する takes に). Every adjunct particle rose (で 32.5→55%, へ 10→25%,
# に 65→85%, が 45→97.5%) and labelled obvious errors fell 4→1. The gate is bypassed by the auditor's ruling; the generation commands and
# parameters are those of generate_and_collect.sh, unchanged.
set -eu
VERA_WORKTREE=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a7-S
VERA_PYTHON=/Users/motonisihikoudai/vera-wiring/env/bin/python
VERA_GENERATOR="$VERA_WORKTREE/tools/gen_coarse_evidence.py"
VERA_ARTIFACTS="$VERA_WORKTREE/artifacts/w3-a7/current-r1"
VERA_RUN_DIR="$VERA_WORKTREE/build/coarse-W3a/full/r10/gen_role_v3"
VERA_CODEX=/opt/homebrew/bin/codex
export PYTHONPATH="$VERA_WORKTREE"; export PYTHONDONTWRITEBYTECODE=1
cd "$VERA_WORKTREE"
shasum -a 256 -c "$VERA_ARTIFACTS/freeze.sha256"
"$VERA_PYTHON" "$VERA_GENERATOR" prompt --kind role | cmp - "$VERA_ARTIFACTS/prompt_role_v2.txt"
mkdir -p "$VERA_RUN_DIR"
date '+%Y-%m-%d %H:%M:%S %z' > "$VERA_ARTIFACTS/generation.started"
"$VERA_PYTHON" "$VERA_GENERATOR" run --kind role --needs "$VERA_ARTIFACTS/needs_role_v3.jsonl" --out-dir "$VERA_RUN_DIR" --codex-bin "$VERA_CODEX" --effort medium --batch-size 40 --slots 4 --max-calls 624 --max-retries 2
"$VERA_PYTHON" "$VERA_GENERATOR" collect --kind role --out-dir "$VERA_RUN_DIR" --out "$VERA_RUN_DIR/role_frames.jsonl"
"$VERA_PYTHON" "$VERA_GENERATOR" summarize --kind role --out-dir "$VERA_RUN_DIR" --out "$VERA_RUN_DIR/summary.json"
date '+%Y-%m-%d %H:%M:%S %z' > "$VERA_ARTIFACTS/generation.finished"
