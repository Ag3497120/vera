import json, sys
from verantyx import coarse_place as cp, coarse_types as ct
P = "/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r6/run1"
pl, why = cp._open(P)
words = [r[0] for r in pl.con.execute("SELECT word FROM headwords WHERE origin='direct' AND by LIKE '%gen_frame%' ORDER BY word")]
res = {"disjoint": [], "not_subset": [], "not_equal": []}
for w in words:
    ev = pl.evidence(w)
    dec = ct.decide_word(list(ev), pl.cfg)
    gen = {}
    for a, s, t, n, b in ev:
        if a == "gen_frame_slot":
            p, _, ty = t.partition("|"); gen.setdefault(p, set()).add(ty)
    bad = {k: False for k in res}
    for k in dec["by"]:
        if dec["arms"][k]["arm"] != "role_distribution": continue
        rows = [r for r in ev if r[0] == "role_distribution" and k.endswith("@" + r[1])]
        an = ct.rd_analyze({r[2]: r[3] for r in rows}, pl.cfg, rows[0][4] if rows else None)
        for p, dt in an["types"].items():
            if not dt or p not in gen: continue
            g, d = gen[p], set(dt)
            if not (g & d): bad["disjoint"] = True
            if not (g <= d): bad["not_subset"] = True
            if g != d: bad["not_equal"] = True
    for k in res:
        if bad[k]: res[k].append(w)
print(len(words), {k: len(v) for k, v in res.items()})
print(json.dumps(res, ensure_ascii=False))
