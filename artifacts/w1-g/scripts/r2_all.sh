#!/bin/bash
A=/Users/motonisihikoudai/Projects/vera-impl/wt/W1-g-S/artifacts/w1-g
bash $A/scripts/accept.sh > $A/scripts/r2_accept.out 2>&1
bash $A/decision_a/measure.sh > $A/scripts/r2_decision_a.out 2>&1
bash $A/decision_b/measure_variant.sh > $A/scripts/r2_decision_b.out 2>&1
bash $A/scripts/step9.sh > $A/scripts/r2_step9.out 2>&1
bash $A/scripts/step9b.sh > $A/scripts/r2_step9b.out 2>&1
echo ALLDONE > $A/scripts/r2_done.txt
