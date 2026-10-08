"""The ids re-run for review round 2 (must-fix 1): the rows of the second data set's codex-codex run that went through the order
route (mapping.order_status is not null) united with the rows whose normalized question matches an order cue of the rules
(conduct_map.has_order_cue).  Written BEFORE the re-run; the rest of the 64 questions keep the earlier run's result."""
import json, sys
from pathlib import Path
from verantyx import conduct_ask as ca, conduct_map as cm

W = Path(__file__).resolve().parents[2]
run = W / "artifacts/w2-g/live/w2g2/codex_codex/results.jsonl"
items = [json.loads(l) for l in (W / "tests/conduct_ask/w2g2/items.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
rows = {r["id"]: r for r in (json.loads(l) for l in run.read_text(encoding="utf-8").splitlines() if l.strip())}
by_route, by_cue = set(), set()
for it in items:
    r = rows[it["id"]]
    if (r.get("mapping") or {}).get("order_status") is not None:
        by_route.add(it["id"])
    if cm.has_order_cue(ca.nz(it["question"])):
        by_cue.add(it["id"])
ids = [it["id"] for it in items if it["id"] in by_route | by_cue]
out = W / "artifacts/w2-g/live/w2g2_r3_subset.txt"
out.write_text("\n".join(ids) + "\n", encoding="utf-8")
print("order_status not null:", len(by_route), "| order cue:", len(by_cue), "| union:", len(ids), "| only by cue:", sorted(by_cue - by_route), "| only by route:", sorted(by_route - by_cue))
