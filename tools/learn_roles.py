"""Learn apposition role nouns from the corpus: X in 「Xの<人名>」.

The closed ROLES list missed 受付係, 整備士, 研修生, 牧場主 … on held-out 2.
A list written by hand is always one domain short; the corpus writes the
pattern itself. X counts when it precedes の + a token unidic tags 人名,
at least MIN times, and X is not itself a name.
"""
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from verantyx.typed_edges import _tagger  # noqa: E402

GEN = Path.home() / "Projects" / "vera-corpus" / "build" / "general.db"
OUT = Path(__file__).resolve().parent.parent / "verantyx" / "lang_data" / "roles_learned.json"
N, MIN = int(sys.argv[1]) if len(sys.argv) > 1 else 800000, 3

con = sqlite3.connect(f"file:{GEN}?mode=ro", uri=True)
c = Counter()
for (t,) in con.execute("SELECT text FROM tsent WHERE text LIKE '%の%' LIMIT ?", (N,)):
    toks = list(_tagger()(t))
    for i in range(1, len(toks) - 1):
        if toks[i].surface != "の" or toks[i + 1].feature.pos3 != "人名":
            continue
        j, parts = i - 1, []
        while j >= 0 and toks[j].feature.pos1 in ("名詞", "接尾辞"):
            parts.insert(0, toks[j]); j -= 1
        if parts and all(p.feature.pos3 != "人名" for p in parts):
            c["".join(p.surface for p in parts)] += 1
roles = sorted(w for w, n in c.items() if n >= MIN and len(w) <= 8)
OUT.write_text(json.dumps({"min": MIN, "scanned": N, "roles": roles}, ensure_ascii=False, indent=0))
print(len(roles), roles[:80])
