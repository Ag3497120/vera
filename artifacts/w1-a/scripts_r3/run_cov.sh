#!/bin/bash
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W1-a-S
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W1-a2-impl3
A=$W/artifacts/w1-a
LEADS=/Users/motonisihikoudai/vera-wiring/data/jawiki_leads.full.jsonl
DEV=$S/dev191
PYB=/Users/motonisihikoudai/vera-wiring/env/bin/python
ENVV="env -i HOME=$HOME PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 VERA_LEADS=$LEADS"
(cd $DEV && $ENVV PYTHONPATH=$DEV $PYB tools/read_coverage.py --n 1500 --stride 200 --json $S/coverage_before.json > $S/coverage_before.out 2>&1)
(cd $DEV && $ENVV PYTHONPATH=$DEV $PYB $W/tests/reading_soundness/coverage_sentences.py --n 1500 --stride 200 --out $S/coverage_sentences_before.jsonl > $S/coverage_sentences_before.out 2>&1)
cmp $S/coverage_before.json $A/coverage_before.json > $A/coverage_before_cmp.txt 2>&1; echo "cmp_json_exit=$?" >> $A/coverage_before_cmp.txt
cmp $S/coverage_sentences_before.jsonl $A/coverage_sentences_before.jsonl >> $A/coverage_before_cmp.txt 2>&1; echo "cmp_sentences_exit=$?" >> $A/coverage_before_cmp.txt
cd $W && $ENVV PYTHONPATH=$W $PYB tools/read_coverage.py --n 1500 --stride 200 --json $A/coverage_after.json > $S/coverage_after.out 2>&1
cd $W && $ENVV PYTHONPATH=$W $PYB tests/reading_soundness/coverage_sentences.py --n 1500 --stride 200 --out $A/coverage_sentences_after.jsonl --all-clauses $A/coverage_clauses_after.jsonl --expect $A/coverage_after.json > $S/coverage_sentences_after.out 2>&1
echo done > $S/cov.done
