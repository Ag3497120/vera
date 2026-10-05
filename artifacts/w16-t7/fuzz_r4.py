"""第 4 ラウンドのファズ。使い方: fuzz_r4.py <ツリー> <seed> <件数>。鍵は連結で作る（完成形を置かない）。
出力: leak N nonidempotent N unbounded N"""
import random
import sys

T, seed, count = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
sys.path.insert(0, T)
import verantyx
assert verantyx.__file__.startswith(T), verantyx.__file__
from verantyx import ledger_events as L

KEYS = {
    "sk_ant": ("sk-" + "ant-api03-" + "Q7R8" * 6, "Q7R8" * 6),
    "github_pat": ("github" + "_pat_" + "W3X4" * 6, "W3X4" * 6),
    "gh_token": ("gh" + "p_" + "M5N6" * 6, "M5N6" * 6),
    "aws_akia": ("AK" + "IA" + "ZZZZYYYYXXXXWWWW", "ZZZZYYYYXXXXWWWW"),
    "google_api_key": ("AI" + "za" + "G1h2" * 8 + "G1h", "G1h2" * 8),
    "slack_token": ("xo" + "xb-" + "1234567890-" + "S9t8" * 4, "S9t8" * 4),
    "sk": ("s" + "k-" + "proj-" + "P4q5" * 5, "P4q5" * 5),
    "bearer": ("Bear" + "er " + "B7c6" * 8, "B7c6" * 8),
    "kv_secret": ("pass" + "word=" + "V2w3" * 3, "V2w3" * 3),
}
SEPS = ["", " ", "\n", "\t", "\\n", "\\t", "\\r", "%0A", "%20", "=", ":", "'", '"', "/", "?q=", ",", "日本語"]
PRES = ["", "x", "1", "abc", "K=1", "\\n", "%0A", "日本語", "ヘッダは"]
names = list(KEYS)
rng = random.Random(seed)
leak = nonid = unb = 0
for _ in range(count):
    k = rng.randint(1, 4)
    parts = [rng.choice(PRES)]
    used = []
    for i in range(k):
        n = rng.choice(names)
        used.append(n)
        parts.append(KEYS[n][0])
        if i < k - 1:
            parts.append(rng.choice(SEPS))
    out, _n = L.redact("".join(parts))
    if any(KEYS[n][1] in out for n in names):
        leak += 1
    if L.redact(out)[1] != 0:
        nonid += 1
    if out == "[REDACTED:unbounded]":
        unb += 1
print(f"seed {seed} count {count} leak {leak} nonidempotent {nonid} unbounded {unb}")
