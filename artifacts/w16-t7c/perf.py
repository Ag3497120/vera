"""計算量の計測。使い方: perf.py <ツリー>。旧（ecde332）と新の秒数・件数を並べる。"""
import os
import random
import subprocess
import sys
import time

T = sys.argv[1]
sys.path.insert(0, T)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verantyx
assert verantyx.__file__.startswith(T)
from verantyx import ledger_events as New
from _old import load_old
Old = load_old(T)
print("uptime:", subprocess.run(["uptime"], capture_output=True, text=True).stdout.strip())
rng = random.Random(0)
B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
CASES = [
    ("password=×11000", "pass" + "word=" * 1 and ("pass" + "word=") * 11000),
    ("sk-×33000+a×20", ("s" + "k-") * 33000 + "a" * 20),
    ("日本語と英字 200000 字", ("日本語abc" * 40000)[:200000]),
    ("Bearer ×7000+z×30", ("Bear" + "er ") * 7000 + "z" * 30),
    ("AKIA×25000", ("AK" + "IA") * 25000),
    ("全角 password＝×11000", "ｐａｓｓｗｏｒｄ＝" * 11000),
    ("全角の文 200000 字", ("ＡＢＣ全角の文　" * 30000)[:200000]),
    ("%41×30000", "%41" * 30000),
    ("base64 文字集合 100000 字 1 トークン", "".join(rng.choice(B64) for _ in range(100000))),
    ("全角の鍵 ×20000（空白区切り）", ("ｓｋ－" + "qrstuvwxyzABCDEF ") * 20000),
    ("全角の鍵 ×40000（空白区切り）", ("ｓｋ－" + "qrstuvwxyzABCDEF ") * 40000),
    ("空白区切りの短い語 50000 個", " ".join("w%d" % i for i in range(50000))),
]
for name, s in CASES:
    row = [name, len(s)]
    for tag, M in (("旧", Old), ("新", New)):
        t = time.time()
        out, n = M.redact(s)
        row.append(f"{tag} {time.time() - t:.2f}s n={n} out={len(out)}")
    print(" | ".join(map(str, row)), flush=True)
