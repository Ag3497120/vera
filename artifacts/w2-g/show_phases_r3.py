import json, sys
rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
for r in rows:
    if r.get("type") == "map_ask" and r["step"] == "phases":
        print(r["question"][:60], "| ask", r["ask_index"], r["provider"], "|", r["raw_reply"], "|", r["verdict"], r["parsed"] and (r["parsed"]["phases"], r["parsed"]["decides"]))
