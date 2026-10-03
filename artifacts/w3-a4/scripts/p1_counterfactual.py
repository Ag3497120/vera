"""Counterfactual: if the DEFAULT of frame_cover_rule were k62_he_by_ni_place, which answers of r7/run1 would change?
The opened placement's cfg gets the key in memory; nothing on disk is changed."""
import hashlib, json
import verantyx.coarse_place as cp
R7 = "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1"
A = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a4-S/artifacts/w3-a4/"
pl, err = cp._open(R7)
assert err is None
pl.cfg["frame_cover_rule"] = "k62_he_by_ni_place"
before = {}
for l in open(A + "p1/r7_before.tsv", encoding="utf-8"):
    w, h, fs = l.rstrip("\n").split("\t")
    before[w] = (h, fs)
changed = []
for w, (h, fs) in before.items():
    a = cp.query(w, placement=R7)
    if hashlib.sha256(json.dumps(a, ensure_ascii=False).encode("utf-8")).hexdigest() != h:
        changed.append((w, fs, a.get("frame_status"), a.get("origin"), a.get("decided_by")))
print("反実仮想（既定を k62_he_by_ni_place にした場合に r7 の答えが変わる語）: %d 語（比べた語 %d）" % (len(changed), len(before)))
for c in changed:
    print("%s\tframe_status %s -> %s\torigin(after)=%s\tdecided_by=%s" % c)
