"""P4: the origin of generated evidence stays on the answers, and a word placed by it alone is marked.

    p4_check.py <placement>
"""
import json
import random
import sqlite3
import sys

W = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S"
sys.path.insert(0, W)
from verantyx.coarse_place import query  # noqa: E402

PL = sys.argv[1]
con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % PL, uri=True)
print(con.execute("select origin,state,count(*) from headwords where by like '%gen_definition%' group by origin,state").fetchall())
print(con.execute("select count(*), count(distinct batch_id) from generated").fetchone())
ws = [r[0] for r in con.execute("select word from headwords where by like '%gen_definition%' order by word")]
random.Random(0).shuffle(ws)
bad = []
for w in ws[:300]:
    r = query(w, placement=PL)
    if r["origin"] == "estimated":
        ok = (r["constructed"] and r.get("estimate_basis") == "generated" and r["neighbors"]
              and r["neighbors"][0]["via"].startswith("generated:")
              and r["axes"]["gen_definition"].get("provenance", {}).get("model") == "gpt-6-luna"
              and r["axes"]["gen_definition"]["provenance"].get("effort") == "low"
              and r["axes"]["gen_definition"]["provenance"].get("batch_id"))
    else:
        ok = (r["origin"] == "direct" and r.get("estimate_basis") is None
              and "gen_definition" in r.get("decided_by", []) and len(r.get("decided_by", [])) >= 2)
    if not ok:
        bad.append(w)
print("checked", min(300, len(ws)), "bad", bad[:10])
# a decided/multiple word with a generated row but WITHOUT gen_definition in `by` kept its own decision
n_ign = 0
for w, in con.execute("select h.word from headwords h join evidence e on e.word=h.word "
                      "where e.arm='gen_definition' and h.by not like '%gen_definition%' and h.state in ('DECIDED','MULTIPLE') limit 2000"):
    r = query(w, placement=PL)
    assert r["origin"] == "direct" and r["axes"]["gen_definition"]["why"] == "GENERATED_NOT_DECIDING" and not r["axes"]["gen_definition"]["met"], w
    n_ign += 1
print("decided without the generated arm (checked, GENERATED_NOT_DECIDING):", n_ign)
assert not bad
