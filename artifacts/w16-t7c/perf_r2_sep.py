"""計算量（区切り字の多い長い 1 トークンなど）。使い方: perf_r2_sep.py <ツリー>。各行 名前 長さ 秒数 n=件数。"""
import random, sys, time
TREE = sys.argv[1]
sys.path.insert(0, TREE)
import verantyx.ledger_events as L
assert L.__file__.startswith(TREE)
ALPHA = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
rng = random.Random(20261006)
cases = [
    ("a- x50000 1トークン", "a-" * 50000),
    ("a/ x50000 1トークン", "a/" * 50000),
    ("AbCd_ x20000 1トークン", "AbCd_" * 20000),
    ("base64 文字集合(+/含む) 無作為 100000 字 1トークン", "".join(rng.choice(ALPHA) for _ in range(100000))),
    ("AAA+/ x200000 1トークン", "AAA+/" * 200000),
    ("Ab-_ x250000 1トークン", "Ab-_" * 250000),
    ("a-b/ x250000 1トークン", "a-b/" * 250000),
    ("空白区切り 64 字の base64 文字集合トークン 5000 個", " ".join("".join(rng.choice(ALPHA) for _ in range(64)) for _ in range(5000))),
]
for name, t in cases:
    t0 = time.time()
    out, n = L.redact(t)
    print(f"{name} {len(t)} {time.time() - t0:.2f}s n={n}")
