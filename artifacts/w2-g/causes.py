"""Groups the questions that should have been answered and were handed up (over_escalate) by the cause, for each run."""
import json, sys
def cause(r):
    m = r["mapping"]; o = r["observed"]
    if m is None: return "mapping off"
    out = str(m["outcome"])
    if out.startswith("NOT_ASKED"): return f"rule escalation not retried: {m['rule']['reason']}/{m['rule']['detail']}"
    if out.startswith("ESCALATED:"):
        body = out[len("ESCALATED:"):]
        if body.startswith("MAPPING_UNSETTLED/STEP1_DISAGREE"): return "step 1 readings disagree"
        if body.startswith("MAPPING_UNSETTLED/STEP2"): return "step 2 readings disagree/invalid/failed"
        if body.startswith("MAPPING_UNSETTLED/RULE"): return "rule answer not corroborated: " + body.split("/")[1][:40]
        if body.startswith("MAPPING_UNSETTLED"): return "mapping unsettled: " + body.split("/")[1][:40]
        return "decided by rule from the mapping: " + body
    return out
tot = {}
for d in sys.argv[1:]:
    rows = [json.loads(l) for l in open(f"{d}/results.jsonl", encoding="utf-8")]
    c = {}
    for r in rows:
        if r["verdict"] == "over_escalate":
            k = cause(r); c[k] = c.get(k, 0) + 1
    print(f"## {d}: over_escalate {sum(c.values())}")
    for k, v in sorted(c.items(), key=lambda kv: (-kv[1], kv[0])): print(f"   {v:3d}  {k}")
