#!/bin/sh
# py_r7.sh: py.sh plus VERA_PLACEMENT=r7/run1
exec env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 VERA_PLACEMENT=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1 PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/W5-d-S /Users/motonisihikoudai/vera-wiring/env/bin/python "$@"
