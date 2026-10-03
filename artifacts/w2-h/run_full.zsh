#!/bin/zsh
# Whole-suite run for R5/R8.  Waits (up to 3 times 5 minutes) while the 1-minute load average is above 8.
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W2-h-S; PY=/Users/motonisihikoudai/vera-wiring/env/bin/python; A=$W/artifacts/w2-h
cd $W
for i in 1 2 3; do
  L=$(uptime | sed -E 's/.*load averages?: ([0-9.]+).*/\1/')
  echo "check $i: load1=$L at $(date -u +%H:%M:%SZ)" >> $A/full_wait_log.txt
  if [ "$(echo "$L <= 8" | bc)" = "1" ]; then break; fi
  sleep 300
done
echo "starting at $(date -u +%H:%M:%SZ), load1=$(uptime | sed -E 's/.*load averages?: ([0-9.]+).*/\1/')" >> $A/full_wait_log.txt
env PYTHONPATH=$W PYTHONDONTWRITEBYTECODE=1 $PY -m pytest -q -p no:cacheprovider -rf --tb=no tests > $A/after_pytest.txt 2>&1; echo $? > $A/after_exit.txt
echo "finished at $(date -u +%H:%M:%SZ)" >> $A/full_wait_log.txt
grep -E '^(FAILED|ERROR) ' $A/after_pytest.txt | sed 's/ - .*//' | sort -u > $A/after_failures.txt
sort -u /Users/motonisihikoudai/Projects/vera-impl/baselines/dev_b471f5a_failures.txt > $A/baseline_failures.txt
comm -13 $A/baseline_failures.txt $A/after_failures.txt > $A/new_failures.txt
comm -23 $A/baseline_failures.txt $A/after_failures.txt > $A/fixed_failures.txt
echo done > $A/after_done.txt
