#!/bin/sh
# py_build.sh: the tree's python for the placement builder (the environment of W3-a3's py.sh, pointing at THIS tree)
exec env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/W5-d-S PYTHONIOENCODING=utf-8 LANG=en_US.UTF-8 \
  /Users/motonisihikoudai/vera-wiring/env/bin/python "$@"
