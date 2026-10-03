#!/bin/bash
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W1-a2-impl3
A=/Users/motonisihikoudai/Projects/vera-impl/wt/W1-a-S/artifacts/w1-a
EX=($A/r3_probe_ja.txt $A/review_r1_examples_ja.txt $A/r4_review_examples_ja.txt $A/b1v2_inputs_ja.txt $A/review_r2_examples_ja.txt $A/b1v2_r2_inputs_ja.txt $A/w1a2r2_probe_ja.txt $A/coverage_texts_ja.txt $A/review_r3_examples_ja.txt $A/b1v2_r3_inputs_ja.txt $A/w1a2r3_probe_ja.txt)
cd $S/r2copy && $S/py.sh $S/r2copy tests/reading_soundness/dump_reads.py --banks --extra "${EX[@]}" --out $S/x3_round2code.jsonl | tail -1
