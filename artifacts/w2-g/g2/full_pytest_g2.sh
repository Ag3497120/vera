#!/bin/sh
# usage: full_pytest_g2.sh baseline|after
cd /Users/motonisihikoudai/Projects/vera-impl/wt/W2-g-S || exit 1
M=$1
sh artifacts/w2-g/py.sh -m pytest -p no:cacheprovider -q -rfE --continue-on-collection-errors tests > artifacts/w2-g/g2/${M}_pytest.txt 2>&1
grep '^FAILED' artifacts/w2-g/g2/${M}_pytest.txt | sed 's/ - .*//' | sort > artifacts/w2-g/g2/${M}_failures.txt
echo done
