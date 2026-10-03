"""compare_hw.py <old placement dir> <new placement dir> seeds|nouns   (both read only)
seeds : every word of SEEDS_PRED: (ns, state, origin, top, by) before and after; n_seen differences apart.
nouns : headwords with N in ns: those whose state/origin/top changed (count, top 20 by n_seen with the arms that differ)
        and those whose only `by` changed; the five sahen nouns' rows."""
import json, sqlite3, sys
import verantyx
from verantyx import coarse_types as ct
assert verantyx.__file__.startswith('/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a4-S/')
old_dir, new_dir, mode = sys.argv[1:4]
def opn(d):
    return sqlite3.connect("file:%s/placement.sqlite?mode=ro" % d, uri=True)
oc, nc = opn(old_dir), opn(new_dir)
def hw(con, w):
    r = con.execute("select ns,state,origin,top,n_seen,by from headwords where word=?", (w,)).fetchone()
    return r
def arms(con, w):
    """significant evidence summary per (arm, src): total n over types (arms only, not generated)"""
    out = {}
    for arm, src, typ, n in con.execute("select arm,src,type,n from evidence where word=?", (w,)):
        out.setdefault("%s@%s" % (arm, src), {})[typ] = n
    return out
def arm_diff(a, b):
    d = []
    for k in sorted(set(a) | set(b)):
        if a.get(k) != b.get(k):
            d.append((k, "removed" if k not in b else "added" if k not in a else "changed"))
    return d
if mode == "seeds":
    words = [w for v in ct.SEEDS_PRED.values() for w in v]
    diff, nseen = [], []
    for w in words:
        o, n = hw(oc, w), hw(nc, w)
        if o is None or n is None:
            diff.append((w, o, n)); continue
        if o[:4] + o[5:] != n[:4] + n[5:]:
            diff.append((w, o, n))
        if o[4] != n[4]:
            nseen.append((w, o[4], n[4]))
    print("SEEDS_PRED %d 語。判定 (ns, state, origin, top, by) が違う語: %d" % (len(words), len(diff)))
    for w, o, n in diff:
        print("DIFF\t%s\t%s\t%s" % (w, o, n))
    print("n_seen だけが違う語（判定ではない）: %d" % len(nseen))
    for w, a, b in nseen:
        print("NSEEN\t%s\t%d\t%d\t(+%d)" % (w, a, b, b - a))
elif mode == "nouns":
    rows = oc.execute("select word,ns,state,origin,top,n_seen,by from headwords where ns like '%N%'").fetchall()
    dec, by_only = [], []
    for w, ns, st, og, top, ns_, by in rows:
        n = hw(nc, w)
        if n is None:
            dec.append((ns_, w, (ns, st, og, top, by), None)); continue
        if (ns, st, og, top) != tuple(n[:4]):
            dec.append((n[4], w, (ns, st, og, top, by), tuple(n[:4]) + (n[5],)))
        elif by != n[5]:
            by_only.append((n[4], w, (ns, st, og, top, by), tuple(n[:4]) + (n[5],)))
    print("名詞（ns に N を含む）の見出し語 %d のうち state/origin/top/ns が変わった語: %d、by だけ変わった語: %d" % (len(rows), len(dec), len(by_only)))
    for label, lst in (("DECISION", dec), ("BY_ONLY", by_only)):
        lst.sort(key=lambda t: (-t[0], t[1]))
        print("== %s 上位 20（n_seen 降順）" % label)
        for ns_, w, o, n in lst[:20]:
            ad = arm_diff(arms(oc, w), arms(nc, w)) if n is not None else []
            print("%s\t%s\tn_seen=%d\tbefore=%s\tafter=%s\tarms_diff=%s" % (label, w, ns_, o, n, ad))
    print("== サ変の名詞 5 語（r7 と r8 の行）")
    for w in ["確認", "連絡", "報告", "提出", "参加"]:
        o, n = hw(oc, w), hw(nc, w)
        print("ROW\t%s\tsame_decision=%s\tbefore=%s\tafter=%s\tarms_diff=%s" % (
            w, (o[:4] + o[5:]) == (n[:4] + n[5:]), o, n, arm_diff(arms(oc, w), arms(nc, w))))
else:
    raise SystemExit("mode: seeds|nouns")
