"""W5-d2 G1-d: run every function of k_ids.txt (the id up to '[': a parametrized function runs with all its parameters). Run from the tree root."""
import sys
import pytest
A2 = '/Users/motonisihikoudai/Projects/vera-impl/wt/W5-d-S/artifacts/w5-d/r2'
S = '/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W5d2-impl'
ids = []
for line in open(A2 + '/k_ids.txt', encoding='utf-8'):
    i = line.strip().split('[')[0]
    if i and i not in ids: ids.append(i)
print(len(ids), 'functions')
sys.exit(pytest.main(['-q', '-p', 'no:cacheprovider', '--basetemp=' + S + '/bt_k', '-rf', '--tb=short', *ids]))
