source /Users/motonisihikoudai/Projects/vera-impl/wt/W1-g-S/artifacts/w1-g/scripts/env.sh
mkdir -p $A/after
cd $W
vpy -m pytest -q -p no:cacheprovider -rfEs --continue-on-collection-errors $W/tests > $A/after/pytest.txt 2>&1; echo $? > $A/after/pytest_exit.txt
grep -E '^(FAILED|ERROR) ' $A/after/pytest.txt | sed -E 's/ - .*$//' | sort -u > $A/after/failures.txt
comm -13 $A/before/base_sorted.txt $A/after/failures.txt > $A/after/new_failures.txt
comm -23 $A/before/base_sorted.txt $A/after/failures.txt > $A/after/fixed.txt
wc -l < $A/after/new_failures.txt; wc -l < $A/after/fixed.txt; cat $A/after/fixed.txt; tail -1 $A/after/pytest.txt
echo DONE
