"""W5-b round 3 (M-A): the effect of the attribute check on the wider-phrase answers the frozen items can make.
usage: py.sh <tree> wider_answer_effect.py   (run from <tree>; scripts follow the item's own truth.records, as tests/test_conduct_ask_w2c2.py does)"""
import json
import sys
from pathlib import Path

sys.path.insert(0, "tests/conduct_ask")
import map_helpers as M  # noqa: E402
import verantyx  # noqa: E402

DATA = Path("tests/conduct_ask/w2c2")
print("verantyx from", verantyx.__file__)
items = [json.loads(ln) for ln in (DATA / "items.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
n = 0
for it in items:
    if not (it["trap"] == "WIDER" and it["group"] == "route" and it["options"] is not None and not it["truth"]["records"][0].startswith("P")):
        continue
    rid = it["truth"]["records"][0]
    rel = ["一致" if k == it["truth"]["answer_option_index"] else "矛盾" for k in range(len(it["options"]))]
    res, _ = M.ask_map(str(DATA / "frames" / f"{it['frame_id']}.md"), it["question"], it["options"],
                       {"records": [rid], "decides": "決まる", "relations": {rid: rel}})
    n += 1
    print(it["id"], res["decision"], res["answer"], res["escalate_reason"], res["escalate_detail"], "|", it["question"])
print("items", n)
