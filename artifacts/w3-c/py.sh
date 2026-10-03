#!/bin/sh
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W3-c-S
cd "$W" && exec env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$W" /Users/motonisihikoudai/vera-wiring/env/bin/python "$@"
