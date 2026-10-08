"""Measure centre-edge speech on the built federation.

Bank (fixed before running): the 200 heaviest cores by core_count that are
vocabulary words, hold >= 20 facets and sit under the generic cut. For each:
walk with carry, 4 hops. Report how many speak across >= 1 centre edge, the
stop types, and an INDEPENDENT recheck of every joint (both directions
present in the raw crosses, content words present as arm-edge partners) —
the recheck does not call hub_edges.seats.
"""
import json
import sys
from collections import Counter
from pathlib import Path

from verantyx.hub_edges import generic_cut, open_on, walk
from verantyx.paths import corpus_root
from verantyx.writer import Writer

store, edges_of, writer = open_on()
writer = writer or Writer.load(corpus_root() / "build" / "writer.json")
cut = generic_cut(store)
labels = store.source_labels
bank = [c for c, _ in sorted(store.core_count.items(), key=lambda kv: (-kv[1], kv[0]))
        if c in writer.vocab and cut[1].get(c, 0) <= cut[0]
        and len([f for f in store.crosses.get(c, {}) if f not in labels]) >= 20][:200]

stops, hopsn, bad, rows = Counter(), Counter(), [], []
for c in bank:
    w = walk(store, c, edges_of, writer, hops=4, generic=cut)
    stops[w["stopped"]] += 1
    joints = [h["seat"] for h in w["hops"] if "seat" in h]
    hopsn[len(joints)] += 1
    for h in w["hops"]:
        if "seat" not in h:
            continue
        a, b = h["seat"]["from"], h["seat"]["to"]
        ok = b in store.crosses.get(a, {}) or any(b in p for p in edges_of(a))
        ok = ok and a in store.crosses.get(b, {})
        arm = {x for p in edges_of(a) if b in p for x in p}
        ok = ok and all(x in arm for x in h["content"][1:])
        if not ok:
            bad.append({"from": a, "to": b, "content": h["content"]})
    rows.append({"subject": c, "path": w["path"], "stopped": w["stopped"], "text": w["text"]})

spoke = sum(n for k, n in hopsn.items() if k >= 1)
multi = sum(n for k, n in hopsn.items() if k >= 2)
rep = {"bank": len(bank), "generic_cut": cut[0],
       "spoke_across_centre_edge": spoke, "crossed_two_or_more_cores": multi,
       "hops_hist": dict(sorted(hopsn.items())), "stops": dict(stops),
       "joints_failing_independent_recheck": len(bad), "bad": bad[:10]}
print(json.dumps(rep, ensure_ascii=False, indent=1))
Path(sys.argv[1] if len(sys.argv) > 1 else "hub_sample.jsonl").write_text(
    "\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
