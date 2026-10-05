#!/bin/zsh
# R7: one domain document end to end -- candidates, growth (fake table or the real local back end), growth indicators, the ledger, the QA without and with the layer, the score and the reasons.
# usage: run_domain.sh <doc> <qa.jsonl> <outdir> <layer-name> <fake-table.json | ollama>
# The base placement is r9 (read only). The outdir must be new (nothing is overwritten). Exit 0 only if no wrong answer and no intended-wrong... (the exit code is the score's: 1 on any wrong answer).
set -u
DOC=$1; QA=$2; OUT=$3; NAME=$4; BACK=$5
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W10-f05-S
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
R9=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2
[ -e "$OUT" ] && { echo "outdir exists: $OUT" >&2; exit 64; }
mkdir -p "$OUT/layers" || exit 64
cd $W
RUN() { env -u VERA_PLACEMENT_LAYER -u VERA_SOVEREIGN_ROOT -u VERA_SOVEREIGN_STORE PYTHONPATH=$W PYTHONDONTWRITEBYTECODE=1 VERA_PLACEMENT=$R9 VERA_PLACEMENT_LAYER_ROOT=$OUT/layers $PY "$@"; }
RUN artifacts/w10-f05/scripts/count_candidates.py "$DOC" $R9 "$OUT/candidates_r9.txt" > "$OUT/candidates.txt"
if [ "$BACK" = "ollama" ]; then BARGS=(--backend ollama --model qwen3.5:4b); else BARGS=(--backend fake --fake-table "$BACK"); fi
RUN -m verantyx.cli placement grow --documents "$DOC" --layer $NAME "${BARGS[@]}" --ledger-file "$OUT/ledger.jsonl" --placement $R9 --dump-sent "$OUT/sent.jsonl" > "$OUT/grow.json"
RUN -m verantyx.cli placement growth --layer $NAME --ledger-file "$OUT/ledger.jsonl" --placement $R9 --list > "$OUT/growth.txt"
RUN -m verantyx.cli ledger list --ledger-file "$OUT/ledger.jsonl" > "$OUT/ledger_list.txt"
RUN artifacts/w10-f05/scripts/run_qa.py --questions "$QA" --document "$DOC" --layer none --out "$OUT/qa_none.jsonl"
RUN artifacts/w10-f05/scripts/run_qa.py --questions "$QA" --document "$DOC" --layer "$OUT/layers/$NAME.sqlite" --out "$OUT/qa_layer.jsonl"
RUN artifacts/w10-f05/scripts/score_qa.py "$OUT/qa_none.jsonl" "$OUT/qa_layer.jsonl" > "$OUT/qa_score.txt"; RC=$?
RUN artifacts/w10-f05/scripts/why_not_gained.py "$QA" "$DOC" "$OUT/layers/$NAME.sqlite" "$OUT/qa_none.jsonl" "$OUT/qa_layer.jsonl" > "$OUT/why_not_gained.txt"
echo "score exit code (0 = no wrong answer in either run): $RC"; tail -4 "$OUT/qa_score.txt"
exit $RC
