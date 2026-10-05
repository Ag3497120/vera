#!/usr/bin/env python
"""N1: every headword of a placement (or the fixed words when the placement is 'none') through coarse_place.query;
write 'word<TAB>sha256(json.dumps(answer, ensure_ascii=False))' and print the overall sha256.
usage: n1_query_bytes.py <tree> <placement dir | none> <out.tsv> [<words file for none>]"""
import hashlib
import json
import os
import random
import sqlite3
import sys
import time

tree, plc, out = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, tree)
from verantyx import coarse_place as cp  # noqa: E402
assert os.path.realpath(cp.__file__).startswith(os.path.realpath(tree) + os.sep), cp.__file__
t0 = time.time()
if plc == "none":
    words = [l.rstrip("\n") for l in open(sys.argv[4], encoding="utf-8") if l.strip()]
    placement = None
else:
    con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % plc, uri=True)
    words = [r[0] for r in con.execute("SELECT word FROM headwords ORDER BY word")]
    con.close()
    placement = plc
h = hashlib.sha256()
n = 0
with open(out, "w", encoding="utf-8") as f:
    for w in words:
        ans = cp.query(w, placement=placement)
        s = hashlib.sha256(json.dumps(ans, ensure_ascii=False).encode("utf-8")).hexdigest()
        f.write("%s\t%s\n" % (w, s))
        h.update(("%s\t%s\n" % (w, s)).encode("utf-8"))
        n += 1
print("rows", n, "overall_sha256", h.hexdigest(), "sec", round(time.time() - t0, 1))
