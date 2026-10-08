#!/bin/bash
# Decision A (producer side), measured on a throwaway copy outside the tree. The tree is not modified.
source /Users/motonisihikoudai/Projects/vera-impl/wt/W1-g-S/artifacts/w1-g/scripts/env.sh
D=$A/decision_a
S=/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W1-g
T=$S/decision_a_copy
mkdir -p $S
if [ -e $T ]; then echo "copy exists: $T (using a fresh numbered one)"; T=$S/decision_a_copy_$(date +%s); fi
mkdir -p $T
rsync -a --exclude .git --exclude __pycache__ $W/ $T/
vpy $D/make_diffs.py $T            # patches $T and writes the two .diff files
TESTS="tests/test_verifier_agents.py tests/attack/test_verifier_agents_*.py tests/test_conductor.py tests/attack/test_conductor_*.py tests/test_w1g_decision_a_unverified.py"
# before (tree as it is) and after (copy with the two diffs applied); same command
(cd $W && vpy -m pytest -q -p no:cacheprovider -rf $TESTS) > $D/before.txt 2>&1
(cd $T && env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 PYTHONPATH="$T" "$PY" -m pytest -q -p no:cacheprovider -rf $TESTS) > $D/after.txt 2>&1
grep -E '^(FAILED|ERROR) ' $D/before.txt | sed -E 's/ - .*$//' | sort -u > $D/before_failures.txt
grep -E '^(FAILED|ERROR) ' $D/after.txt | sed -E 's/ - .*$//' | sort -u > $D/after_failures.txt
comm -13 $D/before_failures.txt $D/after_failures.txt > $D/new_failures.txt
comm -23 $D/before_failures.txt $D/after_failures.txt > $D/fixed_failures.txt
# n=106 alone, in the copy: line 188 passes, 190 is where it stops
(cd $T && env -i HOME="$HOME" PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 PYTHONHASHSEED=0 PYTHONPATH="$T" "$PY" -m pytest -q -p no:cacheprovider "tests/attack/test_verifier_agents_fabrication.py::test_run_verifiers_records_references_with_their_verifier_identities") > $D/n106_after_diffs.txt 2>&1
(cd $W && vpy -m pytest -q -p no:cacheprovider "tests/attack/test_verifier_agents_fabrication.py::test_run_verifiers_records_references_with_their_verifier_identities") > $D/n106_tree.txt 2>&1
echo "copy: $T" > $D/copy_path.txt
tail -1 $D/before.txt; tail -1 $D/after.txt; echo "new failures: $(wc -l < $D/new_failures.txt)"; cat $D/new_failures.txt
