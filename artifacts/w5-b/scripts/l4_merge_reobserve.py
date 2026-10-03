"""L4 (W5-b): re-observability of the merged-path structures of tests/attack/test_w5b_observe_paths.py.

Builds the same structures as the test file (its module functions), observes each, and prints per structure: the number of elements, the
distribution of the number of coordinates per element, and how many elements reobserve() answers REOBSERVED for. Run from the tree root:
    PYTHONPATH=<tree> python artifacts/w5-b/scripts/l4_merge_reobserve.py
"""
import collections
import json
import os
import sys

TREE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(TREE, "tests", "attack"))
import test_w5b_observe_paths as T  # noqa: E402
from verantyx import observe as O  # noqa: E402

total = collections.Counter()
for build in T.BUILDERS:
    vp, st, _ = build()
    obs = O.observe(vp, st)
    dist = collections.Counter()
    status = collections.Counter()
    for e in obs.elements():
        dist[len(e.cell.coords)] += 1
        res = O.reobserve(e, vp, st)
        status[res["status"] + (":" + res["reason"] if res["reason"] else "")] += 1
    row = {"structure": build.__name__, "elements": sum(dist.values()),
           "coords_per_element": dict(sorted(dist.items())), "elements_with_2_or_more_coords": sum(n for k, n in dist.items() if k >= 2),
           "reobserve": dict(status)}
    print(json.dumps(row, ensure_ascii=False))
    total.update({"elements": row["elements"], "multi": row["elements_with_2_or_more_coords"],
                  "reobserved": status.get("REOBSERVED", 0)})
print(json.dumps({"total": dict(total), "rate": total["reobserved"] / total["elements"]}))
