#!/bin/zsh
# X3 repair (thresholds up only, docs/INITIAL_LAYERS.md section J): the same builder runs as build_domain_placements.sh with def_min = alias_min = paren_alias_min = 2 (r9's config has 1).
# The extraction of the first run is reused (--stage-cache: the thresholds act after the extraction). usage: build_domain_placements_k2.sh <law|control>
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W12-c1-S
B=$W/build/initial-layers
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
JW=/Users/motonisihikoudai/vera-wiring/data/jawiki_leads.full.jsonl
d=$1
cd $W
mkdir -p $B/${d}_k2
[ -e $B/${d}_k2/placement ] && { echo "exists: $B/${d}_k2/placement" >&2; exit 1; }
uptime > $B/${d}_k2/uptime_before.txt
env -u VERA_PLACEMENT_LAYER -u VERA_PLACEMENT_LAYER_ROOT -u VERA_SOVEREIGN_ROOT -u VERA_SOVEREIGN_STORE PYTHONPATH=$W PYTHONDONTWRITEBYTECODE=1 \
  /usr/bin/time -l $PY tools/build_coarse_placement.py build --jawiki $JW --codex-dir $B/$d/codex --families general_qa \
  --out $B/${d}_k2/placement --holdout artifacts/w3-a/holdout_2000.jsonl --holdout artifacts/w3-a/dev_l1_1000.jsonl \
  --exclude-terms tests/coarse_place/data/unknown_words.jsonl --exclude-terms tests/coarse_place/data/dev_unknown.jsonl \
  --exclude-terms artifacts/w3-a3/exclude_coined.jsonl --config $B/r9_config_k2.json --jobs 4 --stage-cache $B/$d/extract.pkl \
  > $B/${d}_k2/build.log 2>&1
echo "${d}_k2 done rc=$?" >> $B/build_done.txt
