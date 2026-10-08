#!/bin/bash
# W4-m: CLI demo for S2 / S3 through the default entrance. Output goes to cli_demo.txt (see the runner line below).
# Usage: cli_demo.sh <scratch-dir>   (the two roots are made under it and are left in place)
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W4-m-S
A=$W/artifacts/w4-m
PY=$A/py.sh
BASE=$1
R=$BASE/demo-root
R2=$BASE/demo-root2
mkdir -p "$R2"
set -x
$PY -m verantyx.cli sovereign create --root $R --store-id s1 --owner owner-a; echo rc=$?
$PY -m verantyx.cli sovereign append --root $R --store-id s1 --kind utterance --payload '{"phrase":"p1"}'; echo rc=$?
$PY -m verantyx.cli sovereign promote --root $R --store-id s1; echo rc=$?
$PY -m verantyx.cli sovereign events --root $R --store-id s1 > $A/s2_before.jsonl
$PY -m verantyx.cli sovereign detach --root $R --store-id s1; echo rc=$?
$PY -m verantyx.cli sovereign events --root $R --store-id s1; echo rc=$?
$PY -m verantyx.cli sovereign attach --root $R --store-id s1; echo rc=$?
$PY -m verantyx.cli sovereign events --root $R --store-id s1 > $A/s2_after.jsonl
$PY -m verantyx.cli sovereign export --root $R --store-id s1 --to $R2/s1.sqlite; echo rc=$?
$PY -m verantyx.cli sovereign attach --root $R2 --file $R2/s1.sqlite; echo rc=$?
$PY -m verantyx.cli sovereign events --root $R2 --store-id s1 > $A/s2_attached.jsonl
shasum -a 256 $R/stores/s1.sqlite $R2/s1.sqlite
$PY -m verantyx.cli sovereign release --root $R --store-id s1 --confirm wrong; echo rc=$?
$PY -m verantyx.cli sovereign release --root $R --store-id s1 --confirm s1; echo rc=$?
shasum -a 256 $R/stores/s1.sqlite; test -f $R/stores/s1.sqlite && echo FILE_LEFT_IN_PLACE
$PY -m verantyx.cli sovereign status --root $R --store-id s1; echo rc=$?
$PY -m verantyx.cli sovereign events --root $R --store-id s1; echo rc=$?
# round 2 (review r1, must 2): "0 promotions" / "no such store" / "no ledger in this root" are different answers
$PY -m verantyx.cli sovereign promotions --root $R --store-id s1; echo rc=$?
$PY -m verantyx.cli sovereign promotions --root $R --store-id typo; echo rc=$?
$PY -m verantyx.cli sovereign promotions --root $BASE/nowhere; echo rc=$?
test -e $BASE/nowhere && echo NOWHERE_WAS_CREATED || echo NOWHERE_NOT_CREATED
