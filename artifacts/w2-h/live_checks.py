"""Print what the live ledger shows about routing (R7).  usage: live_checks.py LEDGER_JSONL"""
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1])]
keys = ("role", "task_kind", "size", "agent_id", "stage", "decided_by", "matched_rules", "candidates", "excluded",
        "independence", "undecided_reason", "values", "job_id")
for r in rows:
    t = r["type"]
    if t == "ROUTING_DECISION":
        print(t, json.dumps({k: r.get(k) for k in keys}, ensure_ascii=False, sort_keys=True))
        print("   agent_basis:", json.dumps(r.get("agent_basis"), ensure_ascii=False))
    elif t == "ROUTING_MEASURED":
        print(t, json.dumps({k: r.get(k) for k in ("values", "job_id", "outcome", "rounds", "elapsed_seconds")}, sort_keys=True))
    elif t == "FRAME_COMPILED":
        print(t, "routing =", r.get("routing"))
    elif t in ("LAUNCH_PLANNED", "VERIFIER_LAUNCH_PLANNED"):
        print(t, "adapter =", r.get("adapter"), "argv[0] =", r["argv"][0], "model =", json.dumps(r.get("model")), "effort =", json.dumps(r.get("effort")))
    elif t == "RUN_LIMITS":
        v = r.get("verification", {})
        print(t, "verification.adapter =", json.dumps(v.get("adapter")), "same_adapter =", v.get("same_adapter_as_implementer"),
              "same_lineage =", v.get("same_lineage_as_implementer"))
    elif t in ("RUN_FINISHED", "REFUSED"):
        print(t, json.dumps({k: r.get(k) for k in ("outcome", "reason", "code", "complete", "verification")}, sort_keys=True))
    elif t in ("AGENT_START_CALLED", "VERIFIER_START_CALLED"):
        print(t, "adapter =", r.get("adapter"))
print("rows:", len(rows), "ROUTING_DECISION rows:", sum(r["type"] == "ROUTING_DECISION" for r in rows))
