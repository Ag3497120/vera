#!/bin/zsh
# W2-b2: B8 timing by the audit addendum (2026-10-03 07:10).  Pre-registered rules (never changed after a result):
#  - pair 1 = base -> cand, pair 2 = cand -> base, each run back to back.
#  - before each run, wait until the 1-minute load average is below 7 (checked every 15 s).
#  - a pair with any run whose start or end 1-minute load is above 8 is INVALID and is run again (at most 3 attempts per pair).
#  - validity is decided only by the load, never by the result.  Total waiting budget 90 minutes, then UNMEASURED.
# usage: measure_pairs.zsh <clones dir with base/ and cand/> <output dir>.  Never deletes anything.
PY=${PY_OVERRIDE:-/Users/motonisihikoudai/vera-wiring/env/bin/python}
D=$1; O=$2
P=$O/pair_progress.txt
load1() { sysctl -n vm.loadavg | awk '{print $2}'; }
budget=5400; waited_total=0
run_one() {
  local w=0
  while (( $(load1) >= 7.0 )); do
    if (( waited_total >= budget )); then echo "BUDGET_EXHAUSTED $1 $2 $(date +%H:%M:%S) | $(uptime)" >> $P; return 3; fi
    sleep 15; w=$((w+15)); waited_total=$((waited_total+15))
  done
  START_LOAD=$(load1)
  echo "== $1 $2 start $(date +%H:%M:%S) waited=${w}s load1=$START_LOAD | $(uptime)" >> $P
  ( cd $D/$2 && env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$D/$2 \
      $PY -m pytest -q -p no:cacheprovider -rfE --continue-on-collection-errors \
      --junitxml=$O/$1_$2_junit.xml tests > $O/$1_$2_pytest.txt 2>&1 )
  END_LOAD=$(load1)
  echo "   $1 $2 end $(date +%H:%M:%S) load1=$END_LOAD | $(uptime) | $(tail -n1 $O/$1_$2_pytest.txt)" >> $P
  return 0
}
for pair in 1 2; do
  if (( pair == 1 )); then order=(base cand); else order=(cand base); fi
  ok=0
  for a in 1 2 3; do
    L=p${pair}a${a}; bad=0
    for t in $order; do
      run_one $L $t || { echo "UNMEASURED (budget)" >> $P; exit 3; }
      if (( START_LOAD > 8.0 || END_LOAD > 8.0 )); then bad=1; fi
    done
    if (( bad )); then echo "INVALID $L (a start or end 1-minute load above 8)" >> $P
    else echo "VALID pair$pair = $L" >> $P; ok=1; break; fi
  done
  (( ok )) || { echo "UNMEASURED pair$pair (3 invalid attempts)" >> $P; exit 4; }
done
echo ALLDONE >> $P
