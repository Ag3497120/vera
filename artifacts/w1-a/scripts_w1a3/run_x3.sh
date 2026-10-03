#!/bin/bash
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W1-a-S
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W1-a3-impl
A=$W/artifacts/w1-a
EX=($A/r3_probe_ja.txt $A/review_r1_examples_ja.txt $A/r4_review_examples_ja.txt $A/b1v2_inputs_ja.txt $A/review_r2_examples_ja.txt $A/b1v2_r2_inputs_ja.txt $A/w1a2r2_probe_ja.txt $A/coverage_texts_ja.txt $A/review_r3_examples_ja.txt $A/b1v2_r3_inputs_ja.txt $A/w1a2r3_probe_ja.txt $A/w1a3_review_r3_examples_ja.txt $A/w1a3_r4_inputs_ja.txt)
cd $W && $S/py.sh $W tests/reading_soundness/dump_reads.py --banks --extra "${EX[@]}" --out $A/x3_after.jsonl | tail -1
cd $S/dev191 && $S/py.sh $S/dev191 $W/tests/reading_soundness/dump_reads.py --banks --extra "${EX[@]}" --out $A/x3_dev.jsonl | tail -1
cd $W && $S/py.sh $W tests/reading_soundness/x3_compare.py --dev $A/x3_dev.jsonl --after $A/x3_after.jsonl --gold-harness $A/soundness_after.json --classified $A/x3_classified.tsv --out $A/x3_table.tsv | tee $A/x3_summary.txt; echo "exit=${PIPESTATUS[0]}"
