#!/bin/bash
# round-3 measurements in order (every output goes to artifacts/w1-a)
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W1-a-S
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W1-a2-impl3
A=$W/artifacts/w1-a
DEV=$S/dev191
P=$S/py.sh
T=tests/reading_soundness
cd $W
$P $W $T/harness.py --out $A/soundness_after.json > $A/soundness_after.txt 2>&1
(cd $DEV && $P $DEV $W/$T/harness.py --out $A/soundness_dev.json > $A/soundness_dev.txt 2>&1)
for pair in "a3_check a3" "r3_review_check r4_review_check" "w1a2_review_r1_check r2_review_check" "w1a2_review_r2_check r3_review_check"; do
  set -- $pair
  $P $W $T/$1.py > $A/$2_after.txt 2>&1; echo "exit=$?" >> $A/$2_after.txt
  (cd $DEV && $P $DEV $W/$T/$1.py > $A/$2_dev.txt 2>&1; echo "exit=$?" >> $A/$2_dev.txt)
done
mv $A/a3_after.txt $A/a3_after.txt.tmp 2>/dev/null; mv $A/a3_after.txt.tmp $A/a3_after.txt
for f in bank_freeze bank_freeze_r2 bank_freeze_r3 bank_freeze_r4 bank_freeze_r5 bank_freeze_r6 b1v2_fixture_freeze b1v2_r2_fixture_freeze b1v2_r3_fixture_freeze; do shasum -a 256 -c $A/$f.sha256; done > $A/freeze_check.txt 2>&1
$P $W $T/check_hardcode.py --base 191db17 > $A/a6_hardcode.txt 2>&1; echo "exit=$?" >> $A/a6_hardcode.txt
{ git -C $W diff HEAD -U0 -- verantyx/ tools/ | grep '^+'; cat $W/verantyx/semantic_read.py; } | grep -n -E '土手|裏手|芝生|分母|酵母|空母|体長|全長|身長|器官|民家|空き家|隠れ家|個人|園児|児童|末っ子|新入り|花嫁|町内会|自治会|賑やか|都会|便利|素人|新顔|留学生|受講者|田中家|鈴木家|London|Paris|Tokyo|Rome|ミロ|グラウンド|甥' > $A/a6_review_words.txt
echo done > $S/meas.done
