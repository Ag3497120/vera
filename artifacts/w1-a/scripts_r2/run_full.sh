#!/bin/bash
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W1-a-S
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W1-a2-impl2
A=$W/artifacts/w1-a
cd $W && $S/py.sh $W -m pytest -q -p no:cacheprovider -rfEs --continue-on-collection-errors --junitxml=$A/w1a2r2_after_junit.xml tests > $A/w1a2r2_after_pytest.txt 2>&1
tail -1 $A/w1a2r2_after_pytest.txt > $S/full_done.txt
