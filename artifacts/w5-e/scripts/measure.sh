#!/bin/sh
# measure.sh OUT : the measurements of the ticket's H2-H6 (plan §6), written under OUT.
# Used with OUT=$A/before before any product change, and OUT=$A after (plan step 5).
# Every python is the tree's own (py.sh / py_r7.sh set PYTHONPATH to this tree).
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W5-e-S
A=$W/artifacts/w5-e
E=$A/scripts/py.sh
EP=$A/scripts/py_r7.sh
R7=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1
FZ=/Users/motonisihikoudai/Projects/Verantyx-Vera-alpha/.claude/vera-audit/review-impl/W5-d/review_r1_evidence/frozen
O=${1:?usage: measure.sh OUT}
mkdir -p "$O"
cd $W || exit 2
Q=tests/observe/question
D=tests/attack/w3c2/data
RQ=$W/artifacts/w5-d/scripts/run_questions_both.py

echo "== H2"
for m in place noplace; do
  $E $RQ $W $W/$Q/questions.jsonl $W/$Q/docs $W/$Q $m "$O/h2_185_${m}.jsonl" > "$O/h2_185_${m}.json" 2> "$O/h2_185_${m}.err"
  $EP $RQ $W $W/$Q/questions.jsonl $W/$Q/docs $W/$Q $m "$O/h2_185_${m}_r7.jsonl" > "$O/h2_185_${m}_r7.json" 2> "$O/h2_185_${m}_r7.err"
done
$EP $RQ $W $W/$D/questions.jsonl $W/$D/docs $W/$D place "$O/h2_attack120_r7.jsonl" > "$O/h2_attack120_r7.json" 2> "$O/h2_attack120_r7.err"
$E  $RQ $W $W/$D/questions.jsonl $W/$D/docs $W/$D place "$O/h2_attack120.jsonl" > "$O/h2_attack120.json" 2> "$O/h2_attack120.err"

echo "== H3"
for it in items items_mid; do
  $E tests/routing_from_text/run_bank.py --bank tests/routing_from_text/data --items tests/routing_from_text/data/$it.jsonl --explanations-dir explanations --out "$O/h3_np_$it" 2>&1 | grep misroutes
done
for it in items_reader_shaped items_mid_reader_shaped; do
  $E tests/routing_from_text/run_bank.py --bank tests/routing_from_text/data --items tests/routing_from_text/data/$it.jsonl --explanations-dir explanations_reader_shaped --out "$O/h3_np_$it" 2>&1 | grep misroutes
done
for it in items items_mid; do
  $EP tests/routing_from_text/run_bank.py --bank tests/routing_from_text/data --items tests/routing_from_text/data/$it.jsonl --explanations-dir explanations --out "$O/h3_r7_$it" 2>&1 | grep misroutes
done
$EP $FZ/r7_nouns.py $W > "$O/h3_r7_nouns.json" 2>&1
$E  $FZ/r7_nouns.py $W > "$O/h3_np_nouns.json" 2>&1

echo "== H4"
mkdir -p "$O/h4_work"
$E $FZ/b_check.py $W "$O/h4_work/run" 2>&1 | tail -1 > "$O/h4_b_check.txt"

echo "== H5"
$E $A/scripts/frame_enum.py $W "$O/h5_frames.jsonl" > "$O/h5_frames.log" 2>&1
$E tests/reading_soundness/w3b2_inputs.py --out "$O/h5_w3b2_inputs.txt" > /dev/null 2>&1
$E tests/reading_soundness/w3b2_entry_check.py --mode live --placement $R7 --data frame,multiple,determiner,no,B1_v2,B1_v2_r2,B1_v2_r3 --out "$O/h5_w3b2_check.json" > "$O/h5_w3b2_check.txt" 2>&1
$E tests/reading_soundness/w3b1_entry_dump.py --mode live --placement $R7 --inputs "$O/h5_w3b2_inputs.txt" --out "$O/h5_w3b2_entry.jsonl" > "$O/h5_w3b2_entry.log" 2>&1

echo "== H6"
$E tests/reading_soundness/harness.py --out "$O/h6_soundness.json" --quiet > "$O/h6_soundness.log" 2>&1
$E tests/reading_soundness/a3_check.py > "$O/h6_a3.txt" 2>&1; echo "a3 exit=$?" >> "$O/h6_a3.txt"
$E tests/reading_soundness/w3b3_inputs.py --out "$O/h6_entry_inputs.txt" > /dev/null 2>&1
$E tests/reading_soundness/w3b1_entry_dump.py --mode none --inputs "$O/h6_entry_inputs.txt" --out "$O/h6_entry_none.jsonl" > "$O/h6_entry_none.log" 2>&1
$E tests/reading_soundness/w3b1_entry_dump.py --mode live --placement $R7 --inputs "$O/h6_entry_inputs.txt" --out "$O/h6_entry_r7.jsonl" > "$O/h6_entry_r7.log" 2>&1
$E tests/reading_soundness/w3b3_entry_check.py --mode live --placement $R7 --data relative,connective,parallel,w1a4 --out "$O/h6_w3b3_check.json" > "$O/h6_w3b3_check.txt" 2>&1
echo "== done"
