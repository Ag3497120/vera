#!/bin/sh
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S
PL=${W3A_PL:-/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r2b/run1}
PY=$W/artifacts/w3-a/py.sh
cd $W
show() { echo "\$ $*"; "$@" > /tmp/w3a_cli_out.$$ 2>&1; rc=$?; python3 -c "
import json,sys
t=open('/tmp/w3a_cli_out.$$').read()
try:
    r=json.loads(t); print(json.dumps({k:r.get(k) for k in ('term','state','origin','constructed','top','seen_in_material','context','placement') if k in r}, ensure_ascii=False))
    print('neighbors:', [(n['word'],n['via']) for n in r.get('neighbors',[])][:4], 'axes:', list(r.get('axes',{}).keys()))
except Exception: print(t[:400])
"; echo "exit=$rc"; rm -f /tmp/w3a_cli_out.$$; }
show $PY -m verantyx.coarse_place --term 土手
show $PY -m verantyx.coarse_place --term 土手 --placement /nonexistent
show $PY -m verantyx.coarse_place --term 土手 --placement $PL
show $PY -m verantyx.coarse_place --term ポルメリス --context-role が --context-predicate ある --placement $PL
show $PY -m verantyx.coarse_place --term 土手 --context-role ほげ --placement $PL
show $PY -m verantyx.coarse_place --term ミドリヒメトカゲ --context-role が --context-predicate 走る --placement $PL
