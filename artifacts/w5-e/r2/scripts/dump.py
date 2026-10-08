import sys, json, sqlite3
from verantyx import coarse_place as cp
import verantyx; assert verantyx.__file__.startswith(sys.argv[3]), verantyx.__file__
R = sys.argv[1]; out = open(sys.argv[2], "w", encoding="utf-8")
con = sqlite3.connect("file:%s/placement.sqlite?mode=ro" % R, uri=True)
for w in sorted({r[0] for r in con.execute("select word from generated_frames")}):
    a = cp.query(w, placement=R); a.pop("placement", None)
    out.write(json.dumps([w, a], ensure_ascii=False, sort_keys=True) + "\n")
