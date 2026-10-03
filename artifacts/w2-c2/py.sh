#!/bin/bash
T=/Users/motonisihikoudai/Projects/vera-impl/wt/W2-c2-S
cd "$T" && exec env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$T" TMPDIR=/tmp \
  /Users/motonisihikoudai/vera-wiring/env/bin/python "$@"
