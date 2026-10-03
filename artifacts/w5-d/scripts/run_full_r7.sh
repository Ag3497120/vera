#!/bin/sh
# W5-d: the two full builds of r7 (NO --stage-cache: the extraction runs again each time), same arguments as r6.
# Never writes under full/r6.  Stops when r7 already exists.
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W5-d-S
B6=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r6
R7=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7
G="--generated-frames $B6/gen_pred/frames.jsonl --generated-frames-ledger $B6/gen_pred/ledger.jsonl"
cd "$W" || exit 1
[ -e "$R7" ] && { echo "r7 already exists: stop"; exit 1; }
date '+%F %T %z' > "$W/artifacts/w5-d/build_r7_run1.started"
"$W/artifacts/w5-d/scripts/run_build_w5d.sh" run1 build_full_r7_run1.log $G
date '+%F %T %z' > "$W/artifacts/w5-d/build_r7_run1.finished"
date '+%F %T %z' > "$W/artifacts/w5-d/build_r7_run2.started"
"$W/artifacts/w5-d/scripts/run_build_w5d.sh" run2 build_full_r7_run2.log $G
date '+%F %T %z' > "$W/artifacts/w5-d/build_r7_run2.finished"
