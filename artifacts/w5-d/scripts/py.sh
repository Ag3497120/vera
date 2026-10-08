#!/bin/sh
# py.sh: the tree's python with no placement / sovereign / index variables
exec env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/Users/motonisihikoudai/Projects/vera-impl/wt/W5-d-S /Users/motonisihikoudai/vera-wiring/env/bin/python "$@"
