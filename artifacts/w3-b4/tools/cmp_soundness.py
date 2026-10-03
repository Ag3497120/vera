#!/usr/bin/env python3
"""W3-b4: compare two outputs of tests/reading_soundness/harness.py (--out json): the sentences classified the same, no misread, the whole file equal apart from the header.
Usage: python cmp_soundness.py BASE.json AFTER.json"""
import json, sys
a = json.load(open(sys.argv[1])); b = json.load(open(sys.argv[2]))
sa, sb = a['sentences'], b['sentences']
changed = [x['id'] for x, y in zip(sa, sb) if x != y]
mis = [y['id'] for y in sb if y.get('result') == 'misread']
print('sentences %d changed %d misread %d' % (len(sb), len(changed), len(mis)))
print('whole file equal apart from header (tree path):', {k: v for k, v in a.items() if k != 'header'} == {k: v for k, v in b.items() if k != 'header'})
from collections import Counter
print('results of the sentences (after):', dict(Counter(y.get('result') for y in sb)), 'summary equal:', a['summary'] == b['summary'])
