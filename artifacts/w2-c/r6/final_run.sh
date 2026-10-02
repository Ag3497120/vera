#!/bin/sh
# Re-runs every acceptance command after the last code change (round 6). Run from the tree root.
set -u
cd /Users/motonisihikoudai/Projects/vera-impl/wt/W2-c-S
PY=artifacts/w2-c/py.sh
$PY artifacts/w2-c/q7_check.py > artifacts/w2-c/q7_grep.txt
for m in off fake; do $PY tests/conduct_ask/run_bank.py --items tests/conduct_ask/fixtures/items.jsonl --frames tests/conduct_ask/fixtures/frames --vocab-llm $m --split all --subprocess --out artifacts/w2-c/bank/$m > /dev/null 2>&1; done
for m in off fake; do $PY tests/conduct_ask/run_bank.py --recount artifacts/w2-c/bank/$m; done > artifacts/w2-c/bank/recount.txt
$PY -m pytest -p no:cacheprovider -q -v tests/test_conduct_ask_vocab.py > artifacts/w2-c/q3_vocab.txt 2>&1
$PY -m pytest -p no:cacheprovider -q -v tests/test_conduct_ask_authority.py > artifacts/w2-c/q4_authority.txt 2>&1
$PY -m pytest -p no:cacheprovider -q -v tests/test_conduct_ask_options.py > artifacts/w2-c/q5_options.txt 2>&1
$PY -m pytest -p no:cacheprovider -q tests/test_conduct_ask_cli.py > artifacts/w2-c/q8_cli_tests.txt 2>&1
$PY -m pytest -p no:cacheprovider -q -v tests/test_conduct_ask_traps2.py > artifacts/w2-c/r6/traps2_after.txt 2>&1
$PY -m pytest -p no:cacheprovider -q -v tests/test_conduct_ask_traps3.py > artifacts/w2-c/r6/traps3_after.txt 2>&1
$PY -m pytest -p no:cacheprovider -v tests/test_conduct_ask_traps4.py > artifacts/w2-c/r6/traps4_after.txt 2>&1
$PY -m pytest -p no:cacheprovider -v tests/test_conduct_ask_traps5.py > artifacts/w2-c/r6/traps_after_fix.txt 2>&1
$PY -m pytest -p no:cacheprovider -q tests/test_conduct_ask_*.py > artifacts/w2-c/r6/conduct_ask_tests_all.txt 2>&1
env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$PWD PYTHONIOENCODING=utf-8 VERA_REAL_QUESTIONS=/Users/motonisihikoudai/vera-wiring/data/real_agent_questions.jsonl /Users/motonisihikoudai/vera-wiring/env/bin/python tools/real_questions_eval.py --conduct-ask --out artifacts/w2-c/real_questions > artifacts/w2-c/real_questions/stdout.txt
$PY -m pytest -p no:cacheprovider -q -rfE --continue-on-collection-errors tests > artifacts/w2-c/after_pytest.txt 2>&1
grep -E "^(FAILED|ERROR) " artifacts/w2-c/after_pytest.txt | sed -E 's/ - .*//' | sort > artifacts/w2-c/after_failures.txt
comm -13 artifacts/w2-c/baseline_failures.txt artifacts/w2-c/after_failures.txt > artifacts/w2-c/new_failures.txt
