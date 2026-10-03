#!/bin/sh
# round 2: wait 5 min (load was above 8), then one full run; outputs r2_* (nothing existing is overwritten)
cd /Users/motonisihikoudai/Projects/vera-impl/wt/W2-g-S || exit 1
sleep 300
uptime > artifacts/w2-g/g2/r2_uptime.txt
sh artifacts/w2-g/py.sh -m pytest -p no:cacheprovider -q -rfE --continue-on-collection-errors tests > artifacts/w2-g/g2/r2_pytest.txt 2>&1
grep '^FAILED' artifacts/w2-g/g2/r2_pytest.txt | sed 's/ - .*//' | sort > artifacts/w2-g/g2/r2_failures.txt
echo done > artifacts/w2-g/g2/r2_done.txt
