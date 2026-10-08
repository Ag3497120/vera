import json, sys
new = {json.loads(l)["id"]: json.loads(l) for l in open("artifacts/w2-g/live/w2g2/codex_codex_r3b_order/results.jsonl", encoding="utf-8")}
old = {json.loads(l)["id"]: json.loads(l) for l in open("artifacts/w2-g/live/w2g2/codex_codex/results.jsonl", encoding="utf-8")}
for i, n in new.items():
    o = old[i]
    f = lambda r: (r["verdict"], r["observed"]["decision"], r["observed"].get("reason"), r["observed"].get("detail"), (r.get("mapping") or {}).get("order_picked"))
    print(i, "\n   old", f(o), "\n   new", f(n), "\n   Q:", n["question"][:100])
