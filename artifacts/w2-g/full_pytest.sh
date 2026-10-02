#!/bin/sh
cd /Users/motonisihikoudai/Projects/vera-impl/wt/W2-g-S || exit 1
sh artifacts/w2-g/py.sh -m pytest -p no:cacheprovider -q -rfE --continue-on-collection-errors tests > artifacts/w2-g/after_pytest.txt 2>&1
grep '^FAILED' artifacts/w2-g/after_pytest.txt | sed 's/ - .*//' | sort > artifacts/w2-g/after_failures.txt
echo done
