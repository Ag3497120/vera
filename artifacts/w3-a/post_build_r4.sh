#!/bin/sh
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S
B=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a
PY=$W/artifacts/w3-a/py.sh
PL=$B/full/r4/run1
cd $W
for r in full/r4/run1 full/r4/run2; do $PY tools/build_coarse_placement.py verify --placement $B/$r > /dev/null; echo "verify $r exit=$?"; done
$PY -c "
import json
a=json.load(open('$B/full/r4/run1/manifest.json')); b=json.load(open('$B/full/r4/run2/manifest.json'))
print('sha equal', a['content_sha256']==b['content_sha256'], a['content_sha256'], a['duration_sec'], b['duration_sec'])
g=a['generated']; print({k:g[k] for k in ('path','sha256','lines','used','calls','batches_ok','batches_failed','model','effort','ledger_sha256')})
print([m for m in a['materials'] if 'generat' in json.dumps(m)])"
cp $B/full/r4/run1/manifest.json artifacts/w3-a/manifest_full_r4_run1.json
shasum -a 256 $B/generated/definitions.jsonl $B/generated/ledger.jsonl
sh artifacts/w3-a/run_eval.sh $PL
$PY artifacts/w3-a/independent_recompute_w3a2.py $PL > artifacts/w3-a/independent_recompute_r4.txt 2>&1; echo "independent exit=$?"
$PY artifacts/w3-a/audit_met_arms.py --placement $PL --out artifacts/w3-a/audit_met_arms_r4.json > /dev/null; echo "audit exit=$?"
$PY artifacts/w3-a/hub_spread.py --placement $PL --out artifacts/w3-a/hub_spread_full_r4.txt > /dev/null
$PY artifacts/w3-a/upper_bound.py --placement $PL --out artifacts/w3-a/upper_bound_r4.json > /dev/null
$PY artifacts/w3-a/p4_check.py $PL > artifacts/w3-a/p4_check_r4.txt 2>&1; echo "p4 exit=$?"
for t in 10メートル 2km 30パーセント 40キロメートル A1-23 ABC-123 潜水艦; do $PY -m verantyx.coarse_place --term "$t" --placement $PL | $PY -c "import json,sys;r=json.load(sys.stdin);print(r['term'],r['state'],r['origin'],r.get('estimate_basis'),r['top'])"; done > artifacts/w3-a/p1_cli_r4.txt
echo post_build_r4_done
