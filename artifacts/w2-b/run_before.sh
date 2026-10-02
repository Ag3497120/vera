#!/bin/zsh
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W2-b-S; PY=/Users/motonisihikoudai/vera-wiring/env/bin/python; A=/Users/motonisihikoudai/Projects/vera-impl/wt/W2-b-S/artifacts/w2-b
for i in 1 2; do
  ( cd $W && env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$W $PY -m pytest -q -p no:cacheprovider -rfE --continue-on-collection-errors --junitxml=$A/before${i}_junit.xml tests > $A/before${i}_pytest.txt 2>&1 ); echo "exit=$?" > $A/before${i}_exit.txt
  $PY $A/junit_failures.py $A/before${i}_junit.xml > $A/before${i}_failures.txt
done
echo done > $A/before_done.txt
