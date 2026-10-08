import sys, json, collections
from verantyx import coarse_place as cp, coarse_types as ct
import verantyx; assert verantyx.__file__.startswith(sys.argv[2]), verantyx.__file__
R = sys.argv[1]
pl, why = cp._open(R); assert why is None
cov = []; ign = []; waived = []
for (w,) in pl.con.execute("select word from generated_frames order by word"):
    a = cp.query(w, placement=R)
    if a.get("frame_status") != "CONFIRMED": continue
    dec = ct.decide_word(list(pl.evidence(w)), pl.cfg)
    c = (dec["arms"].get(ct.GEN_FRAME_ARM) or {}).get("cover")
    if c is not None: cov.append(w)
    if c and c.get("he_by_ni_place"): waived.append(w)
    if c and c.get("ignored"): ign.append((w, c["ignored"]))
print("r8 CONFIRMED words:", sum(1 for _ in [0]) and "")
print("with a cover record:", len(cov)); print("he_by_ni_place non-empty:", len(waived), waived)
print("cover.ignored non-empty:", len(ign)); [print(" ", w, json.dumps(i, ensure_ascii=False, sort_keys=True)) for w, i in ign]
