#!/bin/sh
set -eu

VERA_WORKTREE=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S
VERA_PYTHON=/Users/motonisihikoudai/vera-wiring/env/bin/python
VERA_ARTIFACTS="$VERA_WORKTREE/artifacts/w3-a6/current-r2"
VERA_GENERATOR="$VERA_WORKTREE/tools/gen_coarse_evidence.py"
VERA_TRIAL_DIR="$VERA_WORKTREE/build/coarse-W3a/full/r9/gen_role_v2_trial"
VERA_CODEX=/opt/homebrew/bin/codex
export PYTHONPATH="$VERA_WORKTREE"
export PYTHONDONTWRITEBYTECODE=1

cd "$VERA_WORKTREE"
shasum -a 256 -c "$VERA_ARTIFACTS/freeze.sha256"
"$VERA_PYTHON" "$VERA_GENERATOR" prompt --kind role | cmp - "$VERA_ARTIFACTS/prompt_role_v2.txt"
mkdir -p "$VERA_TRIAL_DIR"
date '+%Y-%m-%d %H:%M:%S %z' > "$VERA_ARTIFACTS/trial.started"
"$VERA_PYTHON" "$VERA_GENERATOR" run \
  --kind role \
  --needs "$VERA_ARTIFACTS/trial_needs_role_v2.jsonl" \
  --out-dir "$VERA_TRIAL_DIR" \
  --codex-bin "$VERA_CODEX" \
  --batch-size 40 --slots 1 --max-calls 1 --max-retries 0 --limit-batches 1
"$VERA_PYTHON" "$VERA_GENERATOR" collect \
  --kind role --out-dir "$VERA_TRIAL_DIR" \
  --out "$VERA_TRIAL_DIR/role_frames.jsonl"
"$VERA_PYTHON" "$VERA_GENERATOR" summarize \
  --kind role --out-dir "$VERA_TRIAL_DIR" \
  --out "$VERA_TRIAL_DIR/summary.json"

if "$VERA_PYTHON" - "$VERA_ARTIFACTS/trial_needs_role_v2.jsonl" \
  "$VERA_TRIAL_DIR/role_frames.jsonl" <<'PY'
import json
import sys

needs_path, rows_path = sys.argv[1:]
words = [json.loads(line)["word"] for line in open(needs_path, encoding="utf-8") if line.strip()]
if len(words) != 40 or len(set(words)) != 40:
    raise SystemExit("trial needs must contain 40 distinct words")
requested = set(words)
answers = {}
for line in open(rows_path, encoding="utf-8"):
    if not line.strip():
        continue
    row = json.loads(line)
    word = row.get("word")
    if word not in requested or word in answers:
        raise SystemExit("collected rows contain a foreign or duplicate word")
    answers[word] = row

targets = {"で": 2, "へ": 1, "から": 3}
baselines = {"で": "4.5%", "へ": "2.1%", "から": "5.0%"}
counts = {}
for particle, target in targets.items():
    counts[particle] = sum(
        1 for row in answers.values()
        if isinstance(row.get("frame"), dict) and particle in row["frame"]
    )
    rate = counts[particle] * 100 / 40
    print("%s: %d/40 = %.1f%%; run1=%s; target>run1 (at least %d/40)" %
          (particle, counts[particle], rate, baselines[particle], target))
passed = all(counts[particle] >= target for particle, target in targets.items())
print("trial_threshold=%s" % ("PASS" if passed else "FAIL"))
raise SystemExit(0 if passed else 1)
PY
then
  trial_status=0
  printf '%s\n' 'PASS' > "$VERA_ARTIFACTS/trial_threshold.result"
else
  trial_status=$?
  printf '%s\n' 'FAIL' > "$VERA_ARTIFACTS/trial_threshold.result"
fi
date '+%Y-%m-%d %H:%M:%S %z' > "$VERA_ARTIFACTS/trial.finished"
exit "$trial_status"
