#!/bin/sh
# py_base_r7.sh: base copy plus VERA_PLACEMENT=r7/run1 (W5-d2)
exec env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 VERA_PLACEMENT=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1 PYTHONPATH=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W5d2-impl/base /Users/motonisihikoudai/vera-wiring/env/bin/python "$@"
