#!/usr/bin/env python
"""Compare the base and current N1 byte streams without loading them into memory."""
import hashlib
from pathlib import Path


base = Path("/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/W3-a6-impl/n1")
pairs = [
    ("r7 全見出し語", base / "r7_before.tsv", base / "r7_after.tsv"),
    ("r8 全見出し語", base / "r8_before.tsv", base / "r8_after.tsv"),
    ("配置なし200語", base / "none_before.tsv", base / "none_after.tsv"),
    ("読解入口 配置なし", base / "entry_none_before.jsonl", base / "entry_none_after.jsonl"),
    ("読解入口 r8", base / "entry_r8_before.jsonl", base / "entry_r8_after.jsonl"),
]


def digest(path):
    h = hashlib.sha256()
    rows = 0
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
            rows += block.count(b"\n")
    return h.hexdigest(), rows


bad = []
for label, before, after in pairs:
    a, na = digest(before)
    b, nb = digest(after)
    state = "same" if a == b and na == nb else "DIFF"
    print(label, state, "rows", nb, "sha256", b)
    if state != "same":
        bad.append(label)
if bad:
    raise SystemExit("DIFF: " + ", ".join(bad))
