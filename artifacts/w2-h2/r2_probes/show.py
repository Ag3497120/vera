import json, sys
d = json.loads(sys.stdin.read())
ab = d["abstention"] or {}
print(d["decision"], d["agent"], d["undecided_reason"], ab.get("type"), {k: v for k, v in (ab.get("by_status") or {}).items() if v}, "aliases", d["records"]["aliases"], "agents", [a["id"] for a in d["records"]["agents"]])
