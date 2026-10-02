source /Users/motonisihikoudai/Projects/vera-impl/wt/W1-g-S/artifacts/w1-g/scripts/env.sh
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W1-g
T=$S/committed_copy_$(date +%s)
mkdir -p $T
rsync -a --exclude .git --exclude __pycache__ $W/ $T/
git -C $T init -q && git -C $T add -A && git -C $T -c user.name=w1g -c user.email=w1g@local commit -qm snapshot
echo "untracked/modified under verantyx in copy: $(git -C $T status --porcelain -- verantyx | wc -l)"
cd $T
env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 PYTHONPATH="$T" "$PY" -m pytest -q -p no:cacheprovider -rfEs --continue-on-collection-errors $T/tests > $A/after/pytest_committed_copy.txt 2>&1
grep -E '^(FAILED|ERROR) ' $A/after/pytest_committed_copy.txt | sed -E 's/ - .*$//' | sort -u > $A/after/failures_committed_copy.txt
comm -13 $A/before/base_sorted.txt $A/after/failures_committed_copy.txt > $A/after/new_failures_committed_copy.txt
wc -l < $A/after/new_failures_committed_copy.txt
comm -23 $A/before/base_sorted.txt $A/after/failures_committed_copy.txt > $A/after/fixed_committed_copy.txt; wc -l < $A/after/fixed_committed_copy.txt
echo "$T" > $A/after/committed_copy_path.txt
tail -1 $A/after/pytest_committed_copy.txt
echo DONE
