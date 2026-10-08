#!/bin/sh
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S
PY=$W/artifacts/w3-a/py.sh
PL=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r3b/run1
cd $W
$PY tools/build_coarse_placement.py verify --placement $PL | cut -c1-200; echo "verify exit=$?"
sh artifacts/w3-a/run_eval.sh $PL
$PY artifacts/w3-a/hub_spread.py --placement $PL --out artifacts/w3-a/hub_spread_full_r3b.txt
for t in 10メートル 2km 30パーセント 40キロメートル A1-23 ABC-123 潜水艦; do $PY -m verantyx.coarse_place --term "$t" --placement $PL | $PY -c "import json,sys;r=json.load(sys.stdin);print(r['term'],r['state'],r['origin'],r.get('estimate_basis'),r['top'])"; done > artifacts/w3-a/f2_f3_check_r3b.txt
cat artifacts/w3-a/f2_f3_check_r3b.txt
$PY tools/gen_coarse_evidence.py needs --placement $PL --n 60000 --out artifacts/w3-a/needs_evidence.jsonl --meta artifacts/w3-a/needs_evidence.meta.json
$PY artifacts/w3-a/needs_overlap.py | cut -c1-600
