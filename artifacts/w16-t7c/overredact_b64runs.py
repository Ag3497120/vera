"""base64 文字集合の列での過剰な伏せの測り（任意）。使い方: overredact_b64runs.py <ツリー> <seed> <件数>。
種類: 無作為(長さ16〜300)・sha256 の 16 進・`/` 区切りのパス・英数字だけ(16〜64) を等分。修正前の件数 0 のうち新が 1 以上の件数と例。"""
import hashlib, os, random, sys
T, seed, count = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
sys.path.insert(0, T)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verantyx
assert verantyx.__file__.startswith(T)
from verantyx import ledger_events as New
from _old import load_old
Old = load_old(T)
rng = random.Random(seed)
B = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
AN = B[:-2]
def gen(i):
    k = i % 4
    if k == 0: return "".join(rng.choice(B) for _ in range(rng.randint(16, 300)))
    if k == 1: return hashlib.sha256(str(rng.random()).encode()).hexdigest()
    if k == 2: return "/".join("".join(rng.choice(AN) for _ in range(rng.randint(1, 12))) for _ in range(rng.randint(2, 12)))
    return "".join(rng.choice(AN) for _ in range(rng.randint(16, 64)))
M = K = 0; ex = []
for i in range(count):
    t = gen(i)
    if Old.redact(t)[1] == 0:
        M += 1
        if New.redact(t)[1] >= 1:
            K += 1
            if len(ex) < 10: ex.append(t)
print(f"seed {seed} generated {count} M(旧で件数0) {M} K(新で件数>=1) {K}")
for t in ex: print("例", t[:80])
