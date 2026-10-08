"""W5-d2 round 2b: run the K2 test files of the tree against a copy whose routing_from_text.py lacks ONLY the D2-2 call (the tree's own verantyx otherwise), to show which K2 tests need D2-2. Prints the loaded module path and the failures."""
import sys, os
sys.path.insert(0, sys.argv[1])
os.chdir('/Users/motonisihikoudai/Projects/vera-impl/wt/W5-d-S')
sys.path.insert(1, '/Users/motonisihikoudai/Projects/vera-impl/wt/W5-d-S/tests')
import pytest
rc = pytest.main(['-q', '-p', 'no:cacheprovider', '--basetemp=' + sys.argv[2], '-rf', '--tb=no'] + sys.argv[3:])
import verantyx.routing_from_text as r
print('LOADED', r.__file__)
