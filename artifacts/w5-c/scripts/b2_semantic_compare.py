"""Compare two bank_score output directories after dropping (a) wall-clock keys and (b) the keys W5-c added to the
policy note (classify_version, confirm_id_version, counts.unknown_origin*, withheld.unknown_origin_source_count).
Anything else that differs is printed. Usage: b2_semantic_compare.py BEFORE AFTER"""
import json, sys
from pathlib import Path

CLOCK = {"elapsed_ms", "ingest_ms"}
NEW_NOTE = {"classify_version", "confirm_id_version"}
NEW_COUNTS = {"unknown_origin", "unknown_origin_by_family", "unknown_origin_values"}


def strip(o, path=()):
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            if k in CLOCK:
                continue
            if k in NEW_NOTE and path and path[-1] == "basis_policy":
                continue
            if k in NEW_COUNTS and path and path[-1] == "counts":
                continue
            if k == "unknown_origin_source_count" and path and path[-1] == "withheld":
                continue
            out[k] = strip(v, path + (k,))
        return out
    if isinstance(o, list):
        return [strip(v, path) for v in o]
    return o


b, a = Path(sys.argv[1]), Path(sys.argv[2])
bad = 0
raws = sorted(p.name for p in (b / "raw").iterdir())
assert raws == sorted(p.name for p in (a / "raw").iterdir())
for name in raws:
    x = strip(json.loads((b / "raw" / name).read_text()))
    y = strip(json.loads((a / "raw" / name).read_text()))
    if x != y:
        bad += 1
        print("DIFF", name)
rb = [json.loads(l) for l in (b / "results.jsonl").read_text().splitlines() if l.strip()]
ra = [json.loads(l) for l in (a / "results.jsonl").read_text().splitlines() if l.strip()]
rb, ra = [strip(r) for r in rb], [strip(r) for r in ra]
if rb != ra:
    bad += 1
    for i, (p, q) in enumerate(zip(rb, ra)):
        if p != q:
            print("RESULTS DIFF row", i, {k: (p.get(k), q.get(k)) for k in set(p) | set(q) if p.get(k) != q.get(k)})
sb, sa = json.loads((b / "summary.json").read_text()), json.loads((a / "summary.json").read_text())
print("raw files compared:", len(raws), "results rows:", len(rb), len(ra))
print("summary equal (after stripping clocks):", strip(sb) == strip(sa))
print("differences:", bad)
