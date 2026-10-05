#!/bin/zsh
# X1 (K404): the default entrances are byte-identical to the base 5e7df09: (1) the 4,149-sentence entrance with no placement and with r9, (2) `serve` (fusion_turn) 310 lines, (3) every r9 headword through coarse_place.query.
# usage: x1_bytes.sh entry|serve|query   (the base tree is `git archive 5e7df09` in $SC/base)
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W12-c1-S
A=$W/artifacts/w12-c1
SC=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W12-c1-impl
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
R9=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9/run2
CLEAN() { env -u VERA_PLACEMENT_LAYER -u VERA_PLACEMENT_LAYER_ROOT -u VERA_SOVEREIGN_ROOT -u VERA_SOVEREIGN_STORE -u VERA_PLACEMENT PYTHONDONTWRITEBYTECODE=1 "$@"; }
mkdir -p $SC/x1
case $1 in
entry)
  for plc in none $R9; do
    tag=$([ $plc = none ] && echo none || echo r9)
    (cd $SC/base && CLEAN PYTHONPATH=$SC/base $PY $A/scripts/entry_dump.py $plc $SC/x1/entry_base_$tag.jsonl)
    (cd $W && CLEAN PYTHONPATH=$W $PY $A/scripts/entry_dump.py $plc $SC/x1/entry_new_$tag.jsonl)
    if cmp $SC/x1/entry_base_$tag.jsonl $SC/x1/entry_new_$tag.jsonl; then echo "entry $tag SAME ($(wc -l < $SC/x1/entry_new_$tag.jsonl) lines, sha256 $(shasum -a 256 < $SC/x1/entry_new_$tag.jsonl | cut -c1-16))"; else echo "entry $tag DIFFERENT"; fi
  done > $A/x1_entry.txt 2>&1 ;;
serve)
  DOCS=$SC/b7docs
  (cd $SC/base && CLEAN PYTHONPATH=$SC/base VERA_PLACEMENT=$R9 $PY $A/scripts/k287_serve.py --docs-dir $DOCS --out $SC/x1/serve_base.jsonl)
  (cd $W && CLEAN PYTHONPATH=$W VERA_PLACEMENT=$R9 $PY $A/scripts/k287_serve.py --docs-dir $DOCS --out $SC/x1/serve_new.jsonl)
  { wc -l $SC/x1/serve_base.jsonl $SC/x1/serve_new.jsonl; if cmp $SC/x1/serve_base.jsonl $SC/x1/serve_new.jsonl; then echo "SERVE SAME"; else echo "SERVE DIFFERENT"; fi; } > $A/x1_serve.txt 2>&1 ;;
query)
  (cd $SC/base && CLEAN PYTHONPATH=$SC/base $PY $A/scripts/n1_query_bytes.py $SC/base $R9 $SC/x1/query_base.tsv > $SC/x1/query_base.sha)
  (cd $W && CLEAN PYTHONPATH=$W $PY $A/scripts/n1_query_bytes.py $W $R9 $SC/x1/query_new.tsv > $SC/x1/query_new.sha)
  { cat $SC/x1/query_base.sha $SC/x1/query_new.sha; if cmp $SC/x1/query_base.tsv $SC/x1/query_new.tsv; then echo "r9 SAME"; else echo "r9 DIFFERENT"; fi; } > $A/x1_query.txt 2>&1 ;;
esac
