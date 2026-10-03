#!/bin/bash
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W1-a-S
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W1-a3-impl
A=$W/artifacts/w1-a
PYB=/Users/motonisihikoudai/vera-wiring/env/bin/python
cd $W
run() {  # <fixture dir> <out dir name> <artifact dir name>
  $S/py.sh $W -m tools.bank_score --profile v2 --bank B1 --items tests/bank_score/fixtures/$1/items.jsonl --entry mod-semantic-read --tree $W --out $S/$2 --python $PYB > $S/$2.log 2>&1
  echo "$1 exit=$?"; tail -2 $S/$2.log
  mkdir -p $A/$3; cp $S/$2/summary.json $S/$2/summary.md $S/$2/results.jsonl $S/$2/run_meta.json $A/$3/
}
run B1_v2 bs_b1 bank_score_b1_selfmade
run B1_v2_r2 bs_b1_r2 bank_score_b1_selfmade_r2
run B1_v2_r3 bs_b1_r3 bank_score_b1_selfmade_r3
$S/py.sh $W -m tools.bank_score --profile w1s --bank B1 --items tests/bank_score/fixtures/B1/items.jsonl --entry mod-semantic-read --tree $W --out $S/bs_b1_w1s --python $PYB > $S/bs_b1_w1s.log 2>&1
echo "w1s exit=$?" > $A/bank_score_b1_w1s_run.txt
tail -3 $S/bs_b1_w1s.log >> $A/bank_score_b1_w1s_run.txt
python3 - >> $A/bank_score_b1_w1s_run.txt <<PYEOF
import json
s=json.load(open('$S/bs_b1_w1s/summary.json'))
print({k:v['count'] for k,v in s['classes'].items()})
PYEOF
cat $A/bank_score_b1_w1s_run.txt
