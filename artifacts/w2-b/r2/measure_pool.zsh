#!/bin/zsh
# Compare the pooled scripted runs of round 1 (127 test items) and of the final state (98 items) on the same machine,
# alternating r1, final, r1, final.  serial = each run alone (wall, CPU of this process and its children);
# pool = all runs in the 8-thread pool the tests use.  Usage: measure_pool.zsh <clones dir>
D=$1
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W2-b/impl-r2
R=/Users/motonisihikoudai/Projects/vera-impl/wt/W2-b-S/artifacts/w2-b/r2
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
export SCR=$S PYTHONDONTWRITEBYTECODE=1
export PATH=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W2-b/guardbin:$PATH
for round in 1 2; do
  for t in r1state cand; do
    export W=$D/$t PYTHONPATH=$D/$t
    echo "== $t round $round $(date +%H:%M:%S) $(uptime | sed 's/.*load/load/')"
    $PY $R/pool_serial_cpu.py 2>&1 | tail -1 | sed 's/^/serial: /'
    $PY $R/pool_timing.py mine 2>&1 | tail -1 | sed 's/^/pool:   /'
  done
done
