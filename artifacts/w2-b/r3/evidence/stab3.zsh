#!/bin/zsh
# 3 concurrent runs of the new tests, twice in a row; each output saved.
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W2-b-S
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W2-b/impl-r3
export PATH=$S/guardbin:$PATH PYTHONPATH=$W PYTHONDONTWRITEBYTECODE=1
cd $W
for round in 1 2; do
  uptime > $S/stab_r${round}_uptime.txt
  for k in 1 2 3; do
    /Users/motonisihikoudai/vera-wiring/env/bin/python -m pytest -q -p no:cacheprovider tests/test_conduct_verify*.py > $S/stab_r${round}_k${k}.txt 2>&1 &
  done
  wait
done
tail -qn1 $S/stab_r?_k?.txt
cat $S/stab_r?_uptime.txt
