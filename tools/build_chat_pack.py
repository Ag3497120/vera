"""Build the chat pack: say.py results for the most frequent role nouns, so the chat answers
without scanning the store. python3.11 tools/build_chat_pack.py N"""
import json, sqlite3, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verantyx.say import GENERAL, say  # noqa: E402
N = int(sys.argv[1]) if len(sys.argv) > 1 else 2000
out = GENERAL.with_name("chat_pack.json")
pack = json.loads(out.read_text()) if out.exists() else {}
con = sqlite3.connect(f"file:{GENERAL}?mode=ro", uri=True)
nouns = [r[0] for r in con.execute("SELECT dep, count(*) c FROM tedges WHERE rel IN ('が','を') AND length(dep) BETWEEN 1 AND 6 "
                                   "GROUP BY dep ORDER BY c DESC LIMIT ?", (N,))]
t = time.time()
for i, w in enumerate(nouns):
    if w in pack:
        continue
    r = say(w, k=3, scan=600, via_index=True)
    pack[w] = {"text": r.get("text", ""), "evidence": [l["witnesses"][0]["text"] for l in r.get("lines", []) if l["witnesses"]],
               "sources": [l["sources"] for l in r.get("lines", [])]}
    if i % 100 == 0:
        out.write_text(json.dumps(pack, ensure_ascii=False)); print(i, w, "%.0fs" % (time.time() - t), flush=True)
out.write_text(json.dumps(pack, ensure_ascii=False))
print("done", len(pack), "topics", out.stat().st_size // 1024, "KB")
