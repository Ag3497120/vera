"""DESIGN_2026-09-28_vera_base_chat — run the sealed chat bench and write a judging sheet."""
import json, statistics, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verantyx.chat import Chat  # noqa: E402
B = Path.home() / "Projects" / "vera-corpus" / "benches"
d = json.loads((B / (sys.argv[1] if len(sys.argv) > 1 else "chat_heldout_raw.json")).read_text())
c = Chat(d["site_docs"]); c.reply("こんにちは")
rows, ms = [], []
for i, x in enumerate(d["inputs"]):
    t = time.perf_counter(); r = c.reply(x["ja"]); ms.append(1000 * (time.perf_counter() - t))
    rows.append({"i": i, "category": x["category"], "input": x["ja"], "expected": x["expected"],
                 "kind": r.get("kind"), "reply": r["text"], "ms": round(ms[-1], 1)})
(B / "chat_answers.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
print("median ms", round(statistics.median(ms), 1), "p90", round(sorted(ms)[int(len(ms) * .9)], 1))
