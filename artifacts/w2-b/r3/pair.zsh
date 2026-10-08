#!/bin/zsh
# usage: pair.zsh <clones dir> <tag> <order...>   e.g. pair.zsh $D v2 base cand cand base
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
D=$1; TAG=$2; shift 2
S=${D:h}
for t in "$@"; do
  echo "== $t $(date +%H:%M:%S)" >> $S/${TAG}_progress.txt
  uptime >> $S/${TAG}_progress.txt
  N=$(date +%s)
  ( cd $D/$t && env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=$D/$t \
      $PY -m pytest -q -p no:cacheprovider -rfE --continue-on-collection-errors \
      --junitxml=$S/${TAG}_${t}_${N}.xml tests > $S/${TAG}_${t}_${N}.txt 2>&1 )
  echo "done $t $(date +%H:%M:%S)" >> $S/${TAG}_progress.txt
done
echo ALLDONE >> $S/${TAG}_progress.txt
