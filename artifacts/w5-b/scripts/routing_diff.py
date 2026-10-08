"""Compare two run_bank outputs of the frozen routing data (before / after): every question whose (decision, agent) or abstention type changed."""
import json, sys
A = sys.argv[1]
names = ("items", "items_mid", "items_reader_shaped", "items_mid_reader_shaped")
total = changed = 0
for name in names:
    def load(kind):
        return {r["id"]: r for r in (json.loads(l) for l in open(f"{A}/routing_{kind}/{name}/runs.jsonl", encoding="utf-8"))}
    b, a = load("before"), load("after")
    assert b.keys() == a.keys(), name
    sb, sa = json.load(open(f"{A}/routing_before/{name}/summary.json")), json.load(open(f"{A}/routing_after/{name}/summary.json"))
    print(f"## {name}: questions {len(a)}; summary equal: {sb == sa}; misroutes before {sb.get('misroutes')} after {sa.get('misroutes')}")
    for i in b:
        total += 1
        def key(r):
            o = r.get("output") or {}
            ab = o.get("abstention") or {}
            return (r.get("exit_code"), o.get("decision"), o.get("agent"), ab.get("type"), json.dumps(o.get("relations"), sort_keys=True, ensure_ascii=False))
        kb, ka = key(b[i]), key(a[i])
        if kb != ka:
            changed += 1
            print("CHANGED", i, "expect", a[i]["expect"].get("decision"), a[i]["expect"].get("agent"), "before", kb[:4], "after", ka[:4])
print(f"questions compared {total}; changed (decision, agent, abstention type or relations): {changed}")
