#!/bin/sh
set -eu

VERA_WORKTREE=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a7-S
VERA_PYTHON=/Users/motonisihikoudai/vera-wiring/env/bin/python
VERA_ARTIFACTS="$VERA_WORKTREE/artifacts/w3-a7/current-r1"
VERA_GENERATOR="$VERA_WORKTREE/tools/gen_coarse_evidence.py"
VERA_JUDGE="$VERA_WORKTREE/artifacts/w3-a7/current-r2/trial_judge.py"
VERA_EVENTS="$VERA_ARTIFACTS/trial_runs.jsonl"
VERA_CODEX=/opt/homebrew/bin/codex
export PYTHONPATH="$VERA_WORKTREE"
export PYTHONDONTWRITEBYTECODE=1

cd "$VERA_WORKTREE"
shasum -a 256 -c "$VERA_ARTIFACTS/freeze.sha256"
"$VERA_PYTHON" "$VERA_GENERATOR" prompt --kind role | cmp - "$VERA_ARTIFACTS/prompt_role_v2.txt"
trial_id=$("$VERA_PYTHON" "$VERA_JUDGE" start --root "$VERA_WORKTREE" \
  --freeze "$VERA_ARTIFACTS/freeze.sha256" --events "$VERA_EVENTS")
VERA_TRIAL_DIR="$VERA_WORKTREE/build/coarse-W3a/full/r10/gen_role_v3_trial/$trial_id"
VERA_RESULT="$VERA_ARTIFACTS/trial_results/$trial_id.json"
trial_complete=0

on_exit() {
  exit_code=$?
  trap - EXIT
  if [ "$trial_complete" -eq 0 ]; then
    "$VERA_PYTHON" "$VERA_JUDGE" complete --root "$VERA_WORKTREE" \
      --freeze "$VERA_ARTIFACTS/freeze.sha256" --events "$VERA_EVENTS" \
      --trial-id "$trial_id" --result-file "$VERA_RESULT" --status FAIL \
      --reason "trial_command_failed_exit_$exit_code" || \
      printf '%s\n' 'failed to append trial completion; production gate remains closed' >&2
  fi
  exit "$exit_code"
}
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

mkdir -p "$VERA_TRIAL_DIR"
"$VERA_PYTHON" "$VERA_GENERATOR" run \
  --kind role \
  --needs "$VERA_ARTIFACTS/trial_needs_role_v3.jsonl" \
  --out-dir "$VERA_TRIAL_DIR" \
  --codex-bin "$VERA_CODEX" \
  --effort medium \
  --batch-size 40 --slots 1 --max-calls 1 --max-retries 0 --limit-batches 1
"$VERA_PYTHON" "$VERA_GENERATOR" collect \
  --kind role --out-dir "$VERA_TRIAL_DIR" \
  --out "$VERA_TRIAL_DIR/role_frames.jsonl"
"$VERA_PYTHON" "$VERA_GENERATOR" summarize \
  --kind role --out-dir "$VERA_TRIAL_DIR" \
  --out "$VERA_TRIAL_DIR/summary.json"

set +e
"$VERA_PYTHON" "$VERA_JUDGE" assess \
  --needs "$VERA_ARTIFACTS/trial_needs_role_v3.jsonl" \
  --out-dir "$VERA_TRIAL_DIR" \
  --collected "$VERA_TRIAL_DIR/role_frames.jsonl" \
  --v2 "$VERA_WORKTREE/artifacts/w3-a6/r9/n4_claims_run2_prefreeze.jsonl" \
  --labels "$VERA_WORKTREE/artifacts/w3-a6/r9/n4_visual_labels_run2.jsonl" \
  --out "$VERA_RESULT"
judge_status=$?
set -e

case "$judge_status" in
  0) trial_status=PASS ;;
  1) trial_status=FAIL ;;
  2) trial_status=UNKNOWN ;;
  *) exit "$judge_status" ;;
esac
"$VERA_PYTHON" "$VERA_JUDGE" complete --root "$VERA_WORKTREE" \
  --freeze "$VERA_ARTIFACTS/freeze.sha256" --events "$VERA_EVENTS" \
  --trial-id "$trial_id" --result-file "$VERA_RESULT" --status "$trial_status"
trial_complete=1
exit "$judge_status"
