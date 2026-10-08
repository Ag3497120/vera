#!/bin/sh
# W5-d2: the doc checks of round 1's doc_checks.txt, in the same order. Run from the tree root. (the exit code is the check's own, not tail's)
E=artifacts/w5-d/scripts/py.sh
T=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W5d2-impl/r2b/doc_check.tmp
echo "# doc checks $(date '+%F %T %z')"
for c in tests/observe/question/recompute_q.py tests/routing_from_text/recompute.py tests/event_cross/recompute.py tests/observe/recompute.py tests/reading_soundness/recompute.py artifacts/w3-a3/render_w3a3.py; do
  echo "== $c --check"
  $E $c --check > $T 2>&1; rc=$?
  tail -3 $T
  echo "exit $rc"
done
