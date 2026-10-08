"""Build a few S300 crosses and print one sha256 per tier: run on two machines and compare."""
import hashlib, json, sys
from verantyx.line3 import space as sp, placement as pl
rows = [json.loads(l) for l in open('experiments/line3/data/S300.jsonl', encoding='utf-8')][:60]
full = sp.build_space(rows)
for tier in ("RUN", "WORD", "CHAR"):
    ts = full.tiers[tier]
    units = sorted(ts.postings)[:3]
    h = hashlib.sha256()
    for u in units:
        p = pl.build_cross(ts, u, budget=pl.budget_level("mid"), quotient=False)
        h.update(json.dumps(p.to_json_obj(), sort_keys=True, ensure_ascii=False).encode())
    print(tier, units, h.hexdigest()[:16])
