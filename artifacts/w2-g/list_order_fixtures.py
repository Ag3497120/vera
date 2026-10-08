import json
from verantyx import conduct_ask as ca, conduct_map as cm
for l in open("tests/conduct_ask/fixtures/items.jsonl", encoding="utf-8"):
    it = json.loads(l)
    if cm.has_order_cue(ca.nz(it["question"])):
        e = it["expect"]
        print(it["id"], it["frame_id"], "|", it["question"][:90], "|", it.get("options"), "|", e["decision"], e.get("answer_option_index"), (it.get("w2c") or {}).get("category"), (it.get("w2c") or {}).get("trap"))
