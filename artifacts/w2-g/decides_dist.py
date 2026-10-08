"""How the two wordings of the phases prompt split the `decides` value: per run, per variant (ask_index = variant), count of 決まる / 決まらない
among the valid PICK replies of the phases step (from the saved ledgers' raw replies)."""
import json, sys
for path in sys.argv[1:]:
    dist = {}
    for l in open(path, encoding="utf-8"):
        r = json.loads(l)
        if r.get("type") == "map_ask" and r["step"] == "phases" and r["verdict"] == "PICK":
            k = (r["variant"], r["parsed"]["decides"])
            dist[k] = dist.get(k, 0) + 1
    print(path, {f"variant{v}:{d}": n for (v, d), n in sorted(dist.items())})
