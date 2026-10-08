#!/bin/bash
# Decision B structural-check variant, measured on a throwaway copy outside the tree (the tree is not modified).
source /Users/motonisihikoudai/Projects/vera-impl/wt/W1-g-S/artifacts/w1-g/scripts/env.sh
D=$A/decision_b
cd $W
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W1-g
T=$S/variant_copy_$(date +%s)
mkdir -p $T
rsync -a --exclude .git --exclude __pycache__ $W/ $T/
vpy $D/make_variant.py $T
run() { (cd $1 && env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 PYTHONPATH="$1" "$PY" -m pytest -q -p no:cacheprovider -rf --continue-on-collection-errors "${@:2}"); }
ALL="tests/test_memory_merge.py tests/attack/test_memory_merge_*.py tests/test_memory_frame.py tests/attack/test_memory_frame_*.py tests/test_conductor.py tests/attack/test_conductor_*.py tests/test_memory_revalidate.py tests/attack/test_memory_revalidate_*.py tests/test_w1g_decision_bc_supersede.py"
run $W $ALL > $D/structural_variant_before.txt 2>&1
run $T $ALL > $D/structural_variant_after.txt 2>&1
for f in before after; do grep -E '^(FAILED|ERROR) ' $D/structural_variant_$f.txt | sed -E 's/ - .*$//' | sort -u > $D/structural_variant_${f}_failures.txt; done
comm -13 $D/structural_variant_before_failures.txt $D/structural_variant_after_failures.txt > $D/structural_variant_new_failures.txt
comm -23 $D/structural_variant_before_failures.txt $D/structural_variant_after_failures.txt > $D/structural_variant_fixed.txt
{
echo "# 決定 B の構造検査の変種（ツリーに入れない）の測定。複写: $T"
echo "## 対象 4 件（n=50〜52 と、n=106 は決定 A）の結果（変種を当てた複写）"
for t in tests/attack/test_memory_merge_injection.py::test_instruction_payload_cannot_hide_a_dangling_supersession \
         tests/attack/test_memory_merge_injection.py::test_instruction_text_does_not_make_a_supersession_cycle_valid \
         tests/attack/test_memory_merge_limits.py::test_active_records_reject_dangling_supersession_reference; do
  echo "- $t"; echo "  ツリー: $(run $W $t 2>&1 | tail -1)"; echo "  変種:   $(run $T $t 2>&1 | tail -1)"; done
echo "## 関連テスト群の前後（同じコマンド）"
echo "ツリー: $(tail -1 $D/structural_variant_before.txt)"
echo "変種:   $(tail -1 $D/structural_variant_after.txt)"
echo "## 変種で新しく落ちるテスト（$(wc -l < $D/structural_variant_new_failures.txt) 件）"; cat $D/structural_variant_new_failures.txt
echo "## 変種で通るようになったテスト（$(wc -l < $D/structural_variant_fixed.txt) 件）"; cat $D/structural_variant_fixed.txt
} > $D/structural_variant.txt
cat $D/structural_variant.txt
