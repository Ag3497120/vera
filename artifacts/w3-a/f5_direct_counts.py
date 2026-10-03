"""F5: the (origin, class) counts of one L2 run's items.jsonl, straight from the measurement output.

    f5_direct_counts.py <eval_runs dir number> [...]
"""
import json
import sys
from collections import Counter

A = "/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a-S/artifacts/w3-a/eval_runs/"
for n in sys.argv[1:]:
    c = Counter((r["origin"], r["cls"]) for r in map(json.loads, open(A + n + "/items.jsonl", encoding="utf-8")))
    d = sum(v for (o, _), v in c.items() if o == "direct")
    print(n, dict(c)); print(n, "direct", d, "correct", c[("direct", "correct")],
                              "precision", round(c[("direct", "correct")] / d, 3))
