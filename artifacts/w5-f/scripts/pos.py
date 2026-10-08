import sys
from verantyx import semantic_reader as R
print(R.__file__)
words = sys.argv[1:]
for s in words:
    toks = R._tokens(s)
    print(s, ' | '.join('%s/%s-%s-%s-%s' % (w.surface, w.feature.pos1, w.feature.pos2, w.feature.pos3, w.feature.pos4) for w,a,b in toks))
