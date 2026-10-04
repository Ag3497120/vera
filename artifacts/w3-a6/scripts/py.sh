#!/bin/sh
exec env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONIOENCODING=utf-8 LANG=en_US.UTF-8 \
  PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S /Users/motonisihikoudai/vera-wiring/env/bin/python "$@"
