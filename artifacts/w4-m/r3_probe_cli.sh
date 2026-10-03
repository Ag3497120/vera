#!/bin/bash
# W4-m r3: the same file attached in two new roots with two CLI calls in a row (real clock); the two
# structure_ref values must differ. Usage: r3_probe_cli.sh <scratch-dir>
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W4-m-S
PY=$W/artifacts/w4-m/py.sh
BASE=$1
mkdir -p "$BASE/out"
$PY -m verantyx.cli sovereign create --root $BASE/A --store-id s1 --owner o >/dev/null; echo create rc=$?
$PY -m verantyx.cli sovereign export --root $BASE/A --store-id s1 --to $BASE/out/s1.sqlite >/dev/null; echo export rc=$?
$PY -m verantyx.cli sovereign attach --root $BASE/B --file $BASE/out/s1.sqlite >/dev/null; echo attach-B rc=$?
$PY -m verantyx.cli sovereign attach --root $BASE/C --file $BASE/out/s1.sqlite >/dev/null; echo attach-C rc=$?
$PY - <<PYEOF
import sqlite3
from verantyx import sovereign as sov
rows = {}
for n in "BC":
    c = sov._sov_struct_open("$BASE/" + n)
    rows[n] = (sov._sov_struct_ref(c), c.execute("SELECT ts, op, path FROM registry_log WHERE seq=1").fetchone())
    c.close()
    print(n, rows[n][0][:12], rows[n][1])
print("same first-row ts/op/path:", rows["B"][1] == rows["C"][1], " ref B == ref C:", rows["B"][0] == rows["C"][0])
PYEOF
