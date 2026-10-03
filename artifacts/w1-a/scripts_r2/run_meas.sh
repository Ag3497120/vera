#!/bin/bash
# the measurements of X1-X3 and X6 (coverage), in order; every output goes to artifacts/w1-a
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W1-a-S
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W1-a2-impl2
A=$W/artifacts/w1-a
DEV=$S/dev191
LEADS=/Users/motonisihikoudai/vera-wiring/data/jawiki_leads.full.jsonl
P=$S/py.sh
cd $W
$P $W tests/reading_soundness/harness.py --out $A/soundness_after.json > $A/soundness_after.txt 2>&1
(cd $DEV && $P $DEV $W/tests/reading_soundness/harness.py --out $A/soundness_dev.json > $A/soundness_dev.txt 2>&1)
$P $W tests/reading_soundness/a3_check.py > $A/a3_after.txt 2>&1; echo "exit=$?" >> $A/a3_after.txt
(cd $DEV && $P $DEV $W/tests/reading_soundness/a3_check.py > $A/a3_dev.txt 2>&1; echo "exit=$?" >> $A/a3_dev.txt)
$P $W tests/reading_soundness/r3_review_check.py > $A/r4_review_check_after.txt 2>&1; echo "exit=$?" >> $A/r4_review_check_after.txt
(cd $DEV && $P $DEV $W/tests/reading_soundness/r3_review_check.py > $A/r4_review_check_dev.txt 2>&1; echo "exit=$?" >> $A/r4_review_check_dev.txt)
$P $W tests/reading_soundness/w1a2_review_r1_check.py > $A/r2_review_check_after.txt 2>&1; echo "exit=$?" >> $A/r2_review_check_after.txt
(cd $DEV && $P $DEV $W/tests/reading_soundness/w1a2_review_r1_check.py > $A/r2_review_check_dev.txt 2>&1; echo "exit=$?" >> $A/r2_review_check_dev.txt)
for f in bank_freeze bank_freeze_r2 bank_freeze_r3 bank_freeze_r4 bank_freeze_r5 b1v2_fixture_freeze b1v2_r2_fixture_freeze; do shasum -a 256 -c $A/$f.sha256; done > $A/freeze_check.txt 2>&1
$P $W tests/reading_soundness/check_hardcode.py --base 191db17 > $A/a6_hardcode.txt 2>&1; echo "exit=$?" >> $A/a6_hardcode.txt
# coverage
(cd $DEV && env -i HOME=$HOME PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$DEV VERA_LEADS=$LEADS /Users/motonisihikoudai/vera-wiring/env/bin/python tools/read_coverage.py --n 1500 --stride 200 --json $S/coverage_before.json > $S/coverage_before.out 2>&1)
(cd $DEV && env -i HOME=$HOME PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$DEV VERA_LEADS=$LEADS /Users/motonisihikoudai/vera-wiring/env/bin/python $W/tests/reading_soundness/coverage_sentences.py --n 1500 --stride 200 --out $S/coverage_sentences_before.jsonl > $S/coverage_sentences_before.out 2>&1)
cmp $S/coverage_before.json $A/coverage_before.json > $A/coverage_before_cmp.txt 2>&1; echo "cmp_json_exit=$?" >> $A/coverage_before_cmp.txt
cmp $S/coverage_sentences_before.jsonl $A/coverage_sentences_before.jsonl >> $A/coverage_before_cmp.txt 2>&1; echo "cmp_sentences_exit=$?" >> $A/coverage_before_cmp.txt
env -i HOME=$HOME PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$W VERA_LEADS=$LEADS /Users/motonisihikoudai/vera-wiring/env/bin/python tools/read_coverage.py --n 1500 --stride 200 --json $A/coverage_after.json > $S/coverage_after.out 2>&1
env -i HOME=$HOME PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$W VERA_LEADS=$LEADS /Users/motonisihikoudai/vera-wiring/env/bin/python tests/reading_soundness/coverage_sentences.py --n 1500 --stride 200 --out $A/coverage_sentences_after.jsonl --all-clauses $A/coverage_clauses_after.jsonl --expect $A/coverage_after.json > $S/coverage_sentences_after.out 2>&1
echo done > $S/meas_done.txt
