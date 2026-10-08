"""usage: frame_enum.py <tree> <out.jsonl>: every word of r7's generated_frames table, query() -> frame fields."""
import sys, json
sys.path.insert(0, sys.argv[1])
from verantyx import coarse_place as cp
assert cp.__file__.startswith(sys.argv[1]), cp.__file__
R7 = "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r7/run1"
pl, why = cp._open(R7); assert why is None
rows = []
for (w,) in pl.con.execute("SELECT word FROM generated_frames ORDER BY word"):
    a = cp.query(w, placement=R7)
    rows.append({"word": w, "state": a.get("state"), "origin": a.get("origin"), "top": a.get("top"),
                 "frame_status": a.get("frame_status"), "frame": a.get("frame"), "frame_unconfirmed": a.get("frame_unconfirmed")})
open(sys.argv[2], "w", encoding="utf-8").write("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
print(len(rows))
