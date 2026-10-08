#!/bin/sh
# py_r8.sh: py.sh plus VERA_PLACEMENT (the r8 placement)
exec env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 VERA_PLACEMENT=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2 PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/W5-f-S /Users/motonisihikoudai/vera-wiring/env/bin/python "$@"
