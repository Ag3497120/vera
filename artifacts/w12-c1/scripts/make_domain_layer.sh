#!/bin/zsh
# S4 step 4: the domain layer (K408) from a domain placement. usage: make_domain_layer.sh <law|control> <scene label> <report name>
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W12-c1-S
B=$W/build/initial-layers; A=$W/artifacts/w12-c1
R9=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2
D=$1; SCENE=$2; REP=$3
cd $W
env -u VERA_PLACEMENT_LAYER -u VERA_PLACEMENT_LAYER_ROOT PYTHONPATH=$W PYTHONDONTWRITEBYTECODE=1 /usr/bin/time -l /Users/motonisihikoudai/vera-wiring/env/bin/python tools/build_initial_layers.py domain-layer \
  --domain-placement $B/$D/placement --base $R9 --layer $B/$D/$D.sqlite --ledger $B/$D/ledger.jsonl --domain $D --scene "$SCENE" --rows-db $B/${D%_k2}/codex/general_qa.db --plan-cache $B/$D/plan.json --reuse-written --report $A/$REP
