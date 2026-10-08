#!/bin/bash
# r2: 同じ検査データを qwen3.5:4b（手元の Ollama に後から加わった。設計書の推奨）で流して採点する。層 0・層 1。
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W10-f01-S; A=$W/artifacts/w10-f01
PY="env PYTHONPATH=$W PYTHONDONTWRITEBYTECODE=1 /Users/motonisihikoudai/vera-wiring/env/bin/python"
R8=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2
cd $W
$PY $A/scripts/run_eval.py --docs-dir $A/data/docs --questions $A/data/questions.jsonl --port 18775 --model qwen3.5:4b --placement $R8 --max-tokens 200 --out $A/eval_q35_layer0.jsonl --tree $W > $A/eval_q35_layer0.log 2>&1
$PY $A/scripts/score.py --questions $A/data/questions.jsonl --run $A/eval_q35_layer0.jsonl --out $A/score_q35_layer0.json > $A/score_q35_layer0.txt
$PY $A/scripts/run_eval.py --docs-dir $A/data/docs --questions $A/data/questions.jsonl --port 18776 --model qwen3.5:4b --placement $R8 --strict --out $A/eval_q35_layer1.jsonl --tree $W > $A/eval_q35_layer1.log 2>&1
$PY $A/scripts/score.py --questions $A/data/questions.jsonl --run $A/eval_q35_layer1.jsonl --out $A/score_q35_layer1.json > $A/score_q35_layer1.txt
echo done > $A/run_q35.done
