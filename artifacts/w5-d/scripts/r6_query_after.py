"""W5-d: query every r6 word placed direct by gen_frame through the public query() and count frame_status; compare with the
independent 'disjoint' computation of scripts/frame_defs.py (a copy of the intermediary's). Usage: r6_query_after.py <placement dir>"""
import json, sys
from collections import Counter
from verantyx import coarse_place as cp, coarse_types as ct
P = sys.argv[1]
pl, why = cp._open(P)
words = [r[0] for r in pl.con.execute("SELECT word FROM headwords WHERE origin='direct' AND by LIKE '%gen_frame%' ORDER BY word")]
st = Counter(); dis = []; conf_with_disagreement_key = 0
for w in words:
    r = cp.query(w, placement=P)
    st[r['frame_status']] += 1
    if r['frame_status'] == 'NOT_CONFIRMED':
        assert r['frame'] is None and 'frame_disagreement' in r and 'frame_unconfirmed' not in r, w
        dis.append(w)
    else:
        assert 'frame_disagreement' not in r, w
print('words placed direct by gen_frame:', len(words), dict(st))
print('NOT_CONFIRMED words:', json.dumps(dis, ensure_ascii=False))
r = cp.query('命じる', placement=P)
print('命じる:', json.dumps({k: r[k] for k in ('state', 'origin', 'top', 'generated_frame', 'frame_status', 'frame', 'frame_disagreement')}, ensure_ascii=False))
print('tail keys:', list(r)[-5:])
# independent check: the disjoint rule computed straight from the evidence (frame_defs.py's way)
ind = []
for w in words:
    ev = pl.evidence(w); dec = ct.decide_word(list(ev), pl.cfg)
    gen = {}
    for a, s, t, n, b in ev:
        if a == 'gen_frame_slot':
            p, _, ty = t.partition('|'); gen.setdefault(p, set()).add(ty)
    bad = False
    for k in dec['by']:
        if dec['arms'][k]['arm'] != 'role_distribution': continue
        rows = [x for x in ev if x[0] == 'role_distribution' and k.endswith('@' + x[1])]
        an = ct.rd_analyze({x[2]: x[3] for x in rows}, pl.cfg, rows[0][4] if rows else None)
        for p, dt in an['types'].items():
            if dt and p in gen and not (gen[p] & set(dt)): bad = True
    if bad: ind.append(w)
print('independent disjoint set equals the NOT_CONFIRMED set:', sorted(ind) == sorted(dis), len(ind))
