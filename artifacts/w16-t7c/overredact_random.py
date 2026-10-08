"""過剰な伏せの計数。使い方: overredact_random.py <ツリー> <seed> <件数>。事前登録（docs §15.1）の生成規則。"""
import os
import random
import sys

T, seed, count = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
sys.path.insert(0, T)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verantyx
assert verantyx.__file__.startswith(T), verantyx.__file__
from verantyx import ledger_events as New
from _old import load_old
Old = load_old(T)
rng = random.Random(seed)
ASCII = [chr(c) for c in range(0x20, 0x7F) if chr(c) not in " "]
FW = [chr(c) for c in range(0xFF01, 0xFF5F)]
JP = list("あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんの日本語秘密鍵確認設定表示")
B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/-_"


def piece():
    k = rng.randint(0, 5)
    if k == 0:
        return rng.choice(ASCII)
    if k == 1:
        return rng.choice(FW)
    if k == 2:
        return rng.choice(JP)
    if k == 3:
        return " "
    if k == 4:
        return "%%%02X" % rng.randint(0, 255)
    return "".join(rng.choice(B64) for _ in range(rng.randint(16, 40)))


M = K = 0
ex = []
for _ in range(count):
    n = rng.randint(1, 120)
    s = ""
    while len(s) < n:
        s += piece()
    s = s[:n]
    if Old.redact(s)[1] != 0:
        continue
    M += 1
    out, c = New.redact(s)
    if c >= 1:
        K += 1
        if len(ex) < 20:
            ex.append((s, out))
print(f"seed {seed} generated {count} M(旧で件数0) {M} K(新で件数>=1) {K}")
for s, out in ex:
    print("  例:", repr(s[:70]), "=>", repr(out[:70]))
