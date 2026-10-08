"""replay_before と replay_after_r2 の results.jsonl / labels.tsv を比べる。違う行を数え、違いが全て 64 桁 sha256 の値だけか（sha を伏せると同一か）を確かめる。"""
import re, sys
d = sys.argv[1:3]
sha = re.compile(r"[0-9a-f]{64}")
for f in ("results.jsonl", "labels.tsv"):
    a = open(f"{d[0]}/{f}", encoding="utf-8").read().splitlines(); b = open(f"{d[1]}/{f}", encoding="utf-8").read().splitlines()
    diff = [i + 1 for i, (x, y) in enumerate(zip(a, b)) if x != y]
    norm = [i + 1 for i, (x, y) in enumerate(zip(a, b)) if sha.sub("H", x) != sha.sub("H", y)]
    print(f, "lines", len(a), len(b), "differing lines", diff, "differing after masking sha256:", norm)
