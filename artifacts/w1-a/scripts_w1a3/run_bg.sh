#!/bin/bash
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W1-a-S
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W1-a3-impl
A=$W/artifacts/w1-a
PYB=/Users/motonisihikoudai/vera-wiring/env/bin/python
$S/run_cov.sh
cd $W && $S/py.sh $W -m pytest -q -p no:cacheprovider -rfEs --continue-on-collection-errors --junitxml=$A/w1a2r3_after_junit.xml tests > $A/w1a2r3_after_pytest.txt 2>&1
for seed in 7 101; do
  cd $W && env -i HOME=$HOME PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$W VERA_CORPUS_ROOT=$S/emptycorpus $PYB tests/reading_soundness/qa_probe.py $seed $A/qa_probe_after_seed$seed.json > $S/qa_$seed.out 2>&1
done
cd $W && $S/py.sh $W tests/reading_soundness/qa_summary.py > $A/qa_probe_summary.txt 2>&1
echo done > $S/bg.done
