W=/Users/motonisihikoudai/Projects/vera-impl/wt/W1-g-S
PY=/Users/motonisihikoudai/vera-wiring/env/bin/python
A=$W/artifacts/w1-g
BASE=/Users/motonisihikoudai/Projects/vera-impl/baselines/dev_315a798_failures.txt
P=/Users/motonisihikoudai/Projects/Verantyx-Vera-alpha/.claude/vera-audit/review-impl/W1-g/prelim
vpy() { env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 PYTHONPATH="$W" "$PY" "$@"; }
vtest() { (cd "$W" && vpy -m pytest -q -p no:cacheprovider "$@"); }
