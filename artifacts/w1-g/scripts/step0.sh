source /Users/motonisihikoudai/Projects/vera-impl/wt/W1-g-S/artifacts/w1-g/scripts/env.sh
cd $W
vpy -c "import sys, verantyx, verantyx.memory_frame, verantyx.memory_merge, verantyx.memory_revalidate, verantyx.conductor, verantyx.verifier_agents, verantyx.semantic_unknown, verantyx.semantic_unknown_choice; bad=[k for k,m in sys.modules.items() if k.startswith('verantyx') and getattr(m,'__file__',None) and not m.__file__.startswith('$W/')]; print('outside', bad)" | tee $A/provenance_before.txt
for q in "supersede 事件 merge 会計" "verification UNVERIFIED record" "witness 読み取り 1回" "作業予算 語 数える" "閉じた選択 プロンプト JSON エスケープ"; do
  echo "## $q"; vpy -m verantyx.cli index search "$q"; done > $A/index_search.txt 2>&1
git -C $W status --porcelain
mkdir -p $A/before
vpy -m pytest -q -p no:cacheprovider -rfEs --continue-on-collection-errors $W/tests > $A/before/pytest.txt 2>&1; echo $? > $A/before/pytest_exit.txt
grep -E '^(FAILED|ERROR) ' $A/before/pytest.txt | sed -E 's/ - .*$//' | sort -u > $A/before/failures.txt
wc -l < $A/before/failures.txt
sort -u $BASE > $A/before/base_sorted.txt
comm -3 $A/before/base_sorted.txt $A/before/failures.txt | wc -l
tail -1 $A/before/pytest.txt
