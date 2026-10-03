"""p3_r7_r8.py <r7 dir> <r8 dir> <extract cache of r8 (read only)> <cover tsv of the chosen rule>
For every word with a generated frame in r7 (the r6 frames): decision (ns,state,origin,top,by) in r7 vs r8.
Classes of the words whose decision changed:  i = in the pre-build cover list (p3/cover_<rule>.tsv),
ii = also a sahen_verb word (its distribution rows may have changed), iii = neither.
Output TSV: word, class, before, after, arms that differ.  Then the words that left `direct` (expected 0)."""
import pickle, sqlite3, sys
import verantyx
assert verantyx.__file__.startswith('/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a4-S/')
r7, r8, cache, cover = sys.argv[1:5]
cover_words = {l.split("\t")[0] for l in open(cover, encoding="utf-8").read().splitlines()[1:]}
ex = pickle.load(open(cache, "rb"))
sahen = {w for c in ex["sahen_verb"].values() for w in c}
del ex
def opn(d):
    return sqlite3.connect("file:%s/placement.sqlite?mode=ro" % d, uri=True)
oc, nc = opn(r7), opn(r8)
words = [r[0] for r in oc.execute("select word from generated_frames order by word")]
def hw(con, w):
    return con.execute("select ns,state,origin,top,by from headwords where word=?", (w,)).fetchone()
def arms(con, w):
    out = {}
    for arm, src, typ, n in con.execute("select arm,src,type,n from evidence where word=?", (w,)):
        out.setdefault("%s@%s" % (arm, src), {})[typ] = n
    return out
rows, left = [], []
for w in words:
    o, n = hw(oc, w), hw(nc, w)
    if o != n:
        cls = "i" if w in cover_words else ("ii" if w in sahen else "iii")
        a, b = arms(oc, w), arms(nc, w)
        d = sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))
        rows.append((w, cls, o, n, d))
        if o[2] == "direct" and n[2] != "direct":
            left.append(w)
print("word\tclass\tbefore(ns,state,origin,top,by)\tafter\tarms_that_differ")
for w, cls, o, n, d in rows:
    print("%s\t%s\t%s\t%s\t%s" % (w, cls, o, n, d))
print("# r7 の generated_frames の語 %d、判定が変わった語 %d（i=%d ii=%d iii=%d）" % (
    len(words), len(rows), *[sum(1 for r in rows if r[1] == c) for c in ("i", "ii", "iii")]))
print("# direct から外れた語: %d %s" % (len(left), left))
cov_not_changed = sorted(cover_words - {r[0] for r in rows if r[1] == "i"})
print("# cover リストにあるのに i に入らなかった語: %d %s" % (len(cov_not_changed), cov_not_changed))
