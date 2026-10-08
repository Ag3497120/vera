#!/bin/bash
# P1(2): 既存の vera ask / chat / observe / route の出力が 1 バイトも変わらない（W10-f04）。基点 338809e の木（git archive）と今の木で同じ 8 通りを 2 回ずつ流し cmp する。
set -u
W=/Users/motonisihikoudai/Projects/vera-impl/wt/W10-f04-S
A=$W/artifacts/w10-f04
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W10-f04-impl
PYBIN=/Users/motonisihikoudai/vera-wiring/env/bin/python
R8=/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2
mkdir -p $S/base $S/z1
if [ ! -f $S/base/verantyx/cli.py ]; then git -C $W archive 338809e | tar -x -C $S/base; fi
printf '%s\n' '太郎が地図を渡した。' '花子は本を読んだ。' '先生が生徒に本を貸した。' > $S/z1/d1.txt
printf '%s\n' '{"id":"s1","text":"太郎が地図を渡した。"}' '{"id":"s2","text":"花子は本を読んだ。"}' > $S/z1/recs.jsonl
printf '%s\n' '太郎が地図を渡した。' '花子は本を読んだ。' > $S/z1/expl.txt
run_one() {  # tree n out_prefix
  local T=$1 N=$2 OUT=$3
  local V="env -i HOME=$HOME PATH=/usr/bin:/bin PYTHONPATH=$T PYTHONDONTWRITEBYTECODE=1 VERA_PLACEMENT=$R8 $PYBIN -m verantyx.cli"
  cd $T
  case $N in
    1) $V --store $S/z1/none.json ask 誰が地図を渡した？ ;;
    2) $V ask --mode round5 --document $S/z1/d1.txt -- 誰が地図を渡した？ ;;
    3) $V ask --mode round5 --document $S/z1/d1.txt -- 太郎は何を買った？ ;;
    4) $V ask --mode round5 --document $S/z1/d1.txt --request-kind creative -- 地図の話を書いて ;;
    5) $V observe --anchor-kind question --anchor-text 誰が地図を渡した？ --structure $S/z1/recs.jsonl --no-index ;;
    6) $V observe --anchor-text 太郎が地図を渡した。 --structure $S/z1/recs.jsonl --no-index ;;
    7) $V route --explanation $S/z1/expl.txt --task '{"role":"reviewer","kind":"review","size":"small"}' ;;
    9) $V route --explanation $S/z1/expl.txt --task '{"role":"review","kind":"review","size":"small"}' ;;      # r2: a valid role (case 7 has an invalid role and compares two error outputs)
    8) printf '誰が地図を渡した？\n' | $V chat --mode round5 --document $S/z1/d1.txt ;;
    10) if [ $T = $S/base ]; then env -i HOME=$HOME PATH=/usr/bin:/bin PYTHONPATH=$T PYTHONDONTWRITEBYTECODE=1 $PYBIN -m verantyx.semantic_read --text=母が部屋で手紙を読んだ。 --placement $R8; else $V read --text 母が部屋で手紙を読んだ。 --placement $R8; fi ;;
    11) if [ $T = $S/base ]; then env -i HOME=$HOME PATH=/usr/bin:/bin PYTHONPATH=$T PYTHONDONTWRITEBYTECODE=1 $PYBIN -m verantyx.semantic_read --text=母が図書館へ歩いた。 --placement $R8; else $V read --text 母が図書館へ歩いた。 --placement $R8; fi ;;
    12) if [ $T = $S/base ]; then env -i HOME=$HOME PATH=/usr/bin:/bin PYTHONPATH=$T PYTHONDONTWRITEBYTECODE=1 VERA_PLACEMENT=$R8 $PYBIN -m verantyx.semantic_read --text=誰が地図を渡した？ --events; else $V read-events --text 誰が地図を渡した？; fi ;;
  esac > $OUT 2>$OUT.err
  echo "rc=$?" >> $OUT
}
for n in 1 2 3 4 5 6 7 8 9 10 11 12; do
  for rep in a b; do
    run_one $S/base $n $S/z1/base_${n}_$rep.out
    run_one $W $n $S/z1/new_${n}_$rep.out
  done
done
mask() { sed -E 's/("(ingest_ms|elapsed_ms)": )[0-9.eE+-]+/\1MASK/' "$1"; }
: > $A/z1_nondeterministic.txt
: > $A/z1_cmp.txt
for n in 1 2 3 4 5 6 7 8 9 10 11 12; do
  if ! cmp -s $S/z1/base_${n}_a.out $S/z1/base_${n}_b.out; then
    echo "== case $n: base run a vs b differ (only these lines; masked below as ingest_ms / elapsed_ms)" >> $A/z1_nondeterministic.txt
    diff $S/z1/base_${n}_a.out $S/z1/base_${n}_b.out | grep '^[<>]' >> $A/z1_nondeterministic.txt
    if ! cmp -s <(mask $S/z1/base_${n}_a.out) <(mask $S/z1/base_${n}_b.out); then echo "case $n: base differs between its own two runs outside ingest_ms/elapsed_ms: DIFFERENT" >> $A/z1_cmp.txt; continue; fi
    if cmp -s <(mask $S/z1/base_${n}_a.out) <(mask $S/z1/new_${n}_a.out) && cmp -s <(mask $S/z1/base_${n}_b.out) <(mask $S/z1/new_${n}_b.out); then
      echo "case $n: same (byte-identical after masking ingest_ms and elapsed_ms, the only lines that differ between two runs of the base)" >> $A/z1_cmp.txt
    else
      echo "case $n: DIFFERENT" >> $A/z1_cmp.txt
    fi
  elif cmp -s $S/z1/base_${n}_a.out $S/z1/new_${n}_a.out && cmp -s $S/z1/base_${n}_b.out $S/z1/new_${n}_b.out; then
    echo "case $n: same (byte-identical, both runs)" >> $A/z1_cmp.txt
  else
    echo "case $n: DIFFERENT" >> $A/z1_cmp.txt
  fi
done
# r2: stderr too (the base and the new tree must also print the same bytes on stderr)
for n in 1 2 3 4 5 6 7 8 9 10 11 12; do
  for rep in a b; do
    if cmp -s $S/z1/base_${n}_$rep.out.err $S/z1/new_${n}_$rep.out.err; then :; else echo "case $n run $rep: STDERR DIFFERENT" >> $A/z1_cmp.txt; fi
  done
done
echo "stderr: every case/run not listed as STDERR DIFFERENT above is byte-identical" >> $A/z1_cmp.txt
cat $A/z1_cmp.txt
