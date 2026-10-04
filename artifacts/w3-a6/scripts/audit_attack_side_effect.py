#!/usr/bin/env python
"""Describe the existing r6 fixture file rewritten by test_attack_w3a3_r6."""
import json
import subprocess
from pathlib import Path


name = "tests/attack/w3a3/r6_48_queries.jsonl"
old = subprocess.run(["git", "show", "HEAD:" + name], check=True, capture_output=True, text=True).stdout
new = Path(name).read_text(encoding="utf-8")
before = [json.loads(line) for line in old.splitlines() if line.strip()]
after = [json.loads(line) for line in new.splitlines() if line.strip()]
print("rows", len(before), len(after))
for a, b in zip(before, after):
    changed = [k for k in sorted(set(a) | set(b)) if a.get(k) != b.get(k)]
    if changed:
        scalar = {k: (a.get(k), b.get(k)) for k in changed if k in
                  ("state", "origin", "top", "decided_by", "generated", "generated_frame", "frame_status")}
        print(a.get("term"), "changed_keys", ",".join(changed), "scalar", json.dumps(scalar, ensure_ascii=False))
