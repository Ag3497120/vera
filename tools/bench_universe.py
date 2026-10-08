"""DESIGN_2026-09-28_vera_base_chat (capability survey): run every item through the chat, write a judging sheet."""
import json, statistics, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verantyx.chat import Chat  # noqa: E402
B = Path.home() / "Projects" / "vera-corpus" / "benches"
d = json.loads((B / "universe_heldout_raw.json").read_text())
base = Chat([]); base.reply("こんにちは")
rows, ms = [], []
for a in d["abilities"]:
    for k, it in enumerate(a["items"]):
        c = Chat([{"title": "文章", "ja": it["context"]}], tree=True) if it["context"].strip() else base
        t = time.perf_counter(); r = c.reply(it["input"]); ms.append(1000 * (time.perf_counter() - t))
        rows.append({"ability": a["id"], "name": a["name_ja"], "group": a["group"], "k": k,
                     "context": it["context"], "input": it["input"], "expected": it["expected"],
                     "kind": r.get("kind"), "reply": r["text"]})
(B / "universe_answers.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
print(len(rows), "items; median ms", round(statistics.median(ms), 1))
