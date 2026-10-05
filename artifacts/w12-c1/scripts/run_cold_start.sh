#!/bin/zsh
# S6 / X7: one domain document end to end, with and without the initial law layer (docs/INITIAL_LAYERS.md K400-K410). No LLM, no network.
# usage: run_cold_start.sh <doc> <qa.jsonl> <outdir> [<user layer sqlite>]
#   qa.jsonl rows: {"id","question","expect": {"verdict":"ANSWER","values":[...]} | "ABSTAIN"} (the W10-f05 format).
# The base placement is r9 (read only). <outdir> must be new (nothing is overwritten). Exit 0 iff no run has a wrong answer (score_qa.py's exit code).
set -u
DOC=$1; QA=$2; OUT=$3; USERLAYER=${4:-}
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W12-c1-S
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
R9=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2
LAW=$W/build/initial-layers/law_k2/law_k2.sqlite
A=$W/artifacts/w12-c1/scripts
[ -e "$OUT" ] && { echo "outdir exists: $OUT" >&2; exit 64; }
mkdir -p "$OUT" || exit 64
cd $W
RUN() { env -u VERA_PLACEMENT_LAYER -u VERA_PLACEMENT_LAYER_ROOT -u VERA_SOVEREIGN_ROOT -u VERA_SOVEREIGN_STORE PYTHONPATH=$W PYTHONDONTWRITEBYTECODE=1 VERA_PLACEMENT=$R9 $PY "$@"; }
RUN $A/run_qa.py --questions "$QA" --document "$DOC" --layer none --out "$OUT/qa_none.jsonl"
RUN $A/run_qa.py --questions "$QA" --document "$DOC" --layer "$LAW" --out "$OUT/qa_law.jsonl"
FILES=("$OUT/qa_none.jsonl" "$OUT/qa_law.jsonl")
if [ -n "$USERLAYER" ]; then
  RUN $A/run_qa.py --questions "$QA" --document "$DOC" --layer "$USERLAYER" --out "$OUT/qa_user.jsonl"; FILES+=("$OUT/qa_user.jsonl")
fi
RUN $A/score_qa.py "${FILES[@]}" > "$OUT/qa_score.txt"; RC=$?
RUN $A/why_not_gained.py "$QA" "$DOC" "$LAW" "$OUT/qa_none.jsonl" "$OUT/qa_law.jsonl" > "$OUT/why_not_gained.txt"
echo "score exit code (0 = no wrong answer in any run): $RC"; tail -4 "$OUT/qa_score.txt"
exit $RC
