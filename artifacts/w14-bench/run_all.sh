#!/bin/bash
# 使い方: run_all.sh run1 | run2   （Ap, A, B, C, D を直列。Ollama を並行で叩かない）
set -u
RUN=${1:?run name}
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W14-bench-S
A=$W/artifacts/w14-bench
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/w14impl
R9=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
export PYTHONPATH=$W PYTHONDONTWRITEBYTECODE=1
cd $W
mkdir -p $A/$RUN $S/$RUN
for SYS in ${SYSTEMS:-Ap A B C D}; do
  for i in 1 2 3; do
    LOAD=$(uptime | sed 's/.*load averages*: *//' | awk '{print $1}' | tr -d ',')
    echo "$(date '+%F %T') $RUN $SYS uptime-load1=$LOAD (try $i)" >> $A/${RUN}_run_conditions.log
    if awk -v l="$LOAD" 'BEGIN{exit !(l>8)}'; then sleep 300; else break; fi
  done
  EXTRA=""
  if [ "$SYS" = C ] || [ "$SYS" = D ]; then EXTRA="--placement $R9 --scratch $S/$RUN/scratch_$SYS"; fi
  $PY -m benchmarks.public_v1.run --system $SYS --out $A/$RUN $EXTRA > $A/${RUN}_${SYS}.log 2>&1
  RC=$?
  echo "$(date '+%F %T') $RUN $SYS finished rc=$RC" >> $A/${RUN}_run_conditions.log
done
echo "$(date '+%F %T') $RUN ALL DONE" >> $A/${RUN}_run_conditions.log
