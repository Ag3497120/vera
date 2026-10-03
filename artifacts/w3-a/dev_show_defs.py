import pickle, sys
ex = pickle.load(open('/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/dev/stage_full5.pkl','rb'))
want = set(sys.argv[1:])
for d in ex['defs']:
    if d[0] in want: print(d)
for a in ex['aliases']:
    if a[0] in want: print('alias', a)
for a in ex['paren_aliases']:
    if a[0] in want: print('paren', a)
print(len(ex['defs']), len(ex['aliases']), len(ex['paren_aliases']))
