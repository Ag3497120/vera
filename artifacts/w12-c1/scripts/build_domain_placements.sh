#!/bin/zsh
# S4 step 3: the builder for the law domain and its control (K408, K409): jawiki in full + the domain rows only; no --generated*, no --role-frames, no --frozen, no --compare-to.
# usage: build_domain_placements.sh   (run from anywhere; W is this tree)
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W12-c1-S
B=$W/build/initial-layers
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
JW=/Users/motonisihikoudai/vera-wiring/data/jawiki_leads.full.jsonl
cd $W
for d in law control; do
  [ -e $B/$d/placement ] && { echo "exists: $B/$d/placement" >&2; continue; }
  uptime > $B/$d/uptime_before.txt
  env -u VERA_PLACEMENT_LAYER -u VERA_PLACEMENT_LAYER_ROOT -u VERA_SOVEREIGN_ROOT -u VERA_SOVEREIGN_STORE PYTHONPATH=$W PYTHONDONTWRITEBYTECODE=1 \
    /usr/bin/time -l $PY tools/build_coarse_placement.py build --jawiki $JW --codex-dir $B/$d/codex --families general_qa \
    --out $B/$d/placement --holdout artifacts/w3-a/holdout_2000.jsonl --holdout artifacts/w3-a/dev_l1_1000.jsonl \
    --exclude-terms tests/coarse_place/data/unknown_words.jsonl --exclude-terms tests/coarse_place/data/dev_unknown.jsonl \
    --exclude-terms artifacts/w3-a3/exclude_coined.jsonl --config $B/r9_config.json --jobs 4 --stage-cache $B/$d/extract.pkl \
    > $B/$d/build.log 2>&1
  echo "$d done rc=$?" >> $B/build_done.txt
done
