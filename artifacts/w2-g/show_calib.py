import json, sys
for l in open(sys.argv[1] + "/results.jsonl", encoding="utf-8"):
    r = json.loads(l); o = r["observed"]
    print(r["id"], r["verdict"], o["decision"], o.get("reason"), o.get("detail"), (r.get("mapping") or {}).get("order_picked"))
