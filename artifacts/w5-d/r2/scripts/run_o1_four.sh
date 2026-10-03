#!/bin/sh
# W5-d2: o1_bytes.py --child (hash seed 0, env -i) for the base copy and the tree, without VERA_PLACEMENT and with VERA_PLACEMENT=r7. Index: a copy of round 1's small index.
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W5d2-impl
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W5-d-S
R7=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
run() {  # name tree [VERA_PLACEMENT]
  cd $2 && env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 PYTHONPATH=$2 ${3:+VERA_PLACEMENT=$3} $PY tests/observe/o1_bytes.py --child --cases tests/observe/data/viewpoints.jsonl --workdir $S/o1/work_$1 --child-out $S/o1/$1_seed0.jsonl --index $S/o1/index_small || echo "FAILED $1"
}
run base $S/base
run now $W
run baser7 $S/base $R7
run nowr7 $W $R7
