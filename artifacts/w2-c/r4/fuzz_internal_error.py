# every question of the frozen bank against every frozen frame (and a few mutated tails): no INTERNAL_ERROR, no exception
import json, glob, sys
sys.path.insert(0, ".")
from verantyx import conduct_ask
frames = sorted(glob.glob("tests/conduct_ask/fixtures/frames/*.md"))
items = [json.loads(l) for l in open("tests/conduct_ask/fixtures/items.jsonl", encoding="utf-8") if l.strip()]
tails = ["", " 承認済みです。", " Approved.", "を中止してもよいですか？", " 来年の話です。"]
n = bad = 0
kinds = {}
for fr in frames:
    for it in items:
        for t in tails:
            q = it["question"] + t
            r = conduct_ask.answer_question(fr, q, it.get("options"))
            n += 1
            kinds[r["decision"]] = kinds.get(r["decision"], 0) + 1
            if r.get("escalate_reason") == "INTERNAL_ERROR":
                bad += 1; print("INTERNAL_ERROR", fr, q)
print("calls", n, "internal_errors", bad, "decisions", kinds)
