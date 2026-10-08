"""R3: of the declarations that were put in the fake table ON PURPOSE as wrong (`_intended_wrong`), how many became direct in the layer (must be 0), how many only estimated, how many were not written (and why not,
from the grow report). usage: check_wrong.py <fake table json> <layer sqlite> <grow report json>"""
import json
import sys

table, layer, report = (json.load(open(sys.argv[1], encoding="utf-8")), sys.argv[2], json.load(open(sys.argv[3], encoding="utf-8")))
from verantyx import placement_layer as PL  # noqa: E402
lay = PL.open_layer(layer)[0]
rows = {}
for e in lay.all_entries():
    rows.setdefault(e["word"], []).append(e)
wrong = table["_intended_wrong"]
out = {"intended_wrong": wrong, "declared_type": {w: table[w]["type"] for w in wrong}, "in_layer": {}}
direct = estimated = absent = 0
for w in wrong:
    es = rows.get(w, [])
    origins = sorted({e["origin"] for e in es})
    out["in_layer"][w] = origins
    if any(o in PL.DIRECT_ORIGINS for o in origins):
        direct += 1
    elif origins:
        estimated += 1
    else:
        absent += 1
out.update({"became_direct": direct, "only_estimated": estimated, "not_written": absent, "grow_not_written_reasons": report.get("not_written")})
print(json.dumps(out, ensure_ascii=False, indent=1))
print("RESULT intended-wrong words that became direct: %d (must be 0); estimated only: %d; not written: %d" % (direct, estimated, absent))
sys.exit(0 if direct == 0 else 1)
