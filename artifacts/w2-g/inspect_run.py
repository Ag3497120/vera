"""Lists, for one run directory, every question whose mapping did not settle, with the two readings of each step (diagnosis only)."""
import json, sys
d = sys.argv[1]
rows = {json.loads(l)["id"]: json.loads(l) for l in open(f"{d}/results.jsonl", encoding="utf-8")}
led = [json.loads(l) for l in open(f"{d}/ledger.jsonl", encoding="utf-8")]
asks = [r for r in led if r["type"] == "map_ask"]
dec = {r["decision_id"]: r for r in led if r["type"] == "map_decision"}
by_q = {}
for a in asks:
    by_q.setdefault((a["question"], tuple(a["options"] or ())), []).append(a)
for i, r in rows.items():
    m = r["mapping"]
    if not m or not str(m["outcome"]).startswith("ESCALATED:MAPPING") and r["verdict"] not in ("over_escalate",): continue
    if r["expect"]["decision"] != "answer": continue
    print("==", i, r["verdict"], m["outcome"], "| expected records", r["records_expected"], "| ans idx", r["expect"]["answer_option_index"])
    print("   Q:", r["question"], r["options"])
    for a in by_q.get((r["question"], tuple(r["options"] or ())), []):
        p = a["parsed"]
        print("   ", a["step"], a["record_id"] or "", a["ask_index"], a["verdict"], a["invalid_reason"] or "", json.dumps(p, ensure_ascii=False) if p else (a["raw_reply"] or "")[:120])
