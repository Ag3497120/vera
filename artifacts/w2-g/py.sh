#!/bin/sh
exec env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 \
  PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/W2-g-S PYTHONIOENCODING=utf-8 LANG=en_US.UTF-8 \
  /Users/motonisihikoudai/vera-wiring/env/bin/python "$@"
