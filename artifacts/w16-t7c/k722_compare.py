"""K722: fuzz_r4.py と同じ生成規則（seed 0/1/2 × 30,000）で、新旧の redact の出力・件数の不一致を数える。使い方: k722_compare.py <ツリー>"""
import os
import random
import re
import sys

T = sys.argv[1]
sys.path.insert(0, T)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import verantyx
assert verantyx.__file__.startswith(T), verantyx.__file__
from verantyx import ledger_events as New
from _old import load_old
Old = load_old(T)
src = open(T + "/artifacts/w16-t7/fuzz_r4.py", encoding="utf-8").read()
ns = {}
exec(src[src.index("KEYS = {"):src.index("names = list(KEYS)")], ns)   # KEYS・SEPS・PRES を同じ定義で得る
KEYS, SEPS, PRES = ns["KEYS"], ns["SEPS"], ns["PRES"]
names = list(KEYS)
secret_bodies = [v[1] for v in KEYS.values()]
for seed in (0, 1, 2):
    rng = random.Random(seed)
    dout = dn = 0
    ex = []
    for _ in range(30000):
        k = rng.randint(1, 4)
        parts = [rng.choice(PRES)]
        for i in range(k):
            parts.append(KEYS[rng.choice(names)][0])
            if i < k - 1:
                parts.append(rng.choice(SEPS))
        s = "".join(parts)
        a, b = Old.redact(s), New.redact(s)
        if a[0] != b[0]:
            dout += 1
            if len(ex) < 5:
                ex.append(a[0][:60] + " => " + b[0][:60])
        if a[1] != b[1]:
            dn += 1
    print(f"seed {seed} count 30000 diff_out {dout} diff_n {dn}")
    for e in ex:
        for body in secret_bodies:
            e = e.replace(body, "<body>")
        print("  例:", e)
