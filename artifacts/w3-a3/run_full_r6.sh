#!/bin/sh
# W3-a3 step 9: the two full builds of r6 (NO --stage-cache: the extraction runs again each time), same arguments.
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a3-S
B=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r6
G="--generated-frames $B/gen_pred/frames.jsonl --generated-frames-ledger $B/gen_pred/ledger.jsonl"
cd "$W" || exit 1
"$W/artifacts/w3-a3/py.sh" "$W/artifacts/w3-a3/freeze.py" --check || exit 1
date '+%F %T %z' > "$W/artifacts/w3-a3/build_r6_run1.started"
"$W/artifacts/w3-a3/run_build_w3a3.sh" run1 build_full_r6_run1.log $G
date '+%F %T %z' > "$W/artifacts/w3-a3/build_r6_run1.finished"
date '+%F %T %z' > "$W/artifacts/w3-a3/build_r6_run2.started"
"$W/artifacts/w3-a3/run_build_w3a3.sh" run2 build_full_r6_run2.log $G
date '+%F %T %z' > "$W/artifacts/w3-a3/build_r6_run2.finished"
