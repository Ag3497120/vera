"""P1: byte-compare coarse_place.query answers on r7/run1.
usage: p1_r7_bytes.py <tree> <out.tsv> [words_out]
Words: (a) every word with a gen_frame or role_distribution evidence row, (b) 10000 random other headwords
(random.Random(20261004).sample(sorted(rest), 10000)), (c) five nouns.  Each line: word TAB sha256 of
json.dumps(answer, ensure_ascii=False) (no sort_keys: key order is compared too), then TAB frame_status."""
import hashlib, json, random, sqlite3, sys, time
tree, out = sys.argv[1], sys.argv[2]
words_out = sys.argv[3] if len(sys.argv) > 3 else None
import verantyx.coarse_place as cp
assert cp.__file__.startswith(tree.rstrip("/") + "/"), (cp.__file__, tree)
R7 = "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1"
t0 = time.time()
con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % R7, uri=True)
a = sorted(r[0] for r in con.execute(
    "select distinct word from evidence where arm in ('gen_frame','role_distribution')"))
heads = set(r[0] for r in con.execute("select word from headwords"))
rest = sorted(heads - set(a))
b = random.Random(20261004).sample(rest, 10000)
c = ["確認", "連絡", "報告", "提出", "参加"]
con.close()
words = [("a", w) for w in a] + [("b", w) for w in b] + [("c", w) for w in c]
if words_out:
    with open(words_out, "w", encoding="utf-8") as f:
        for s, w in words:
            f.write("%s\t%s\n" % (s, w))
with open(out, "w", encoding="utf-8") as f:
    for s, w in words:
        ans = cp.query(w, placement=R7)
        h = hashlib.sha256(json.dumps(ans, ensure_ascii=False).encode("utf-8")).hexdigest()
        f.write("%s\t%s\t%s\n" % (w, h, ans.get("frame_status")))
print("a=%d b=%d c=%d total=%d sec=%.1f" % (len(a), len(b), len(c), len(words), time.time() - t0))
