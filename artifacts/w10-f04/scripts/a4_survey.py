"""r3: for every hole of every sentence in the frozen data (and extra sentences given as arguments): the placement types of the hole word (own), the role each type reads (role_by_type; None = not readable / not determined) and the (a4) class: UNPLACED / SAME / UNDET (some type not read, at most one role) / SPLIT (two or more roles). Last line: the Counter."""
import json, sys, itertools, collections
from verantyx import semantic_read as S, event_cross as EC
T = "/Users/motonisihikoudai/Projects/vera-impl/wt/W10-f04-S/tests/fusion/w10f04/"
sents = collections.OrderedDict()
for fn, key in (("holes.jsonl","text"),("real_holes.jsonl","text"),("fake_scripts.jsonl","sentence")):
    for l in open(T+fn):
        r = json.loads(l); sents.setdefault(r[key], []).append(r["id"])
for extra in sys.argv[1:]: sents.setdefault(extra, ["X"])
q = S._placement_query(S._UNSET)
cnt = collections.Counter()
for text, ids in sents.items():
    try: ho = S.read_with_holes(text)
    except Exception as e: continue
    if ho["holes_status"] != "HOLES_FOUND": continue
    for hi, h in enumerate(ho["holes"]):
        others = [o for j,o in enumerate(ho["holes"]) if j != hi]
        own = EC.PlaceResult.from_coarse_query(q.query(h["head"])).types
        roles = {}
        for t in own:
            rs = set()
            for combo in itertools.product(*[o["expected_types"] for o in others]):
                f = {o["head"]: c for o, c in zip(others, combo)}; f[h["head"]] = t
                out = S.read(text, "ja", placement=S._HoleProbe(q, f, {}))
                rs.add(S._hole_arm(out["clauses"][0], h["head"], t) if S._hole_probe_ok(out) else None)
            roles[t] = sorted(map(str, rs))
        if h["placement_state"] in ("UNPLACED","UNKNOWN"): v = "UNPLACED"
        else:
            allr = set(x for v_ in roles.values() for x in v_)
            v = "SAME" if len(allr)==1 and "None" not in allr else ("UNDET" if "None" in allr and len(allr - {"None"})<=1 else "SPLIT")
        cnt[v] += 1
        print(v, ids[0], text, h["particle"], h["head"], h["placement_state"], "exp=", h["expected_types"], "roles=", roles)
print(cnt)
