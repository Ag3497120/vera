#!/usr/bin/env python3
"""Freeze the v2 claims for the preregistered 60-word N4 sample, before checks."""
from __future__ import annotations

import json
import sqlite3
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ART = ROOT / "artifacts/w3-a6"
CANDIDATE = Path(
    "/private/tmp/claude-501/-Users-motonisihikoudai-Projects-Verantyx-Vera-alpha/"
    "516c6003-3687-4f5e-a07a-ae6b080c15b8/scratchpad/codex-w3a6-r9/candidate"
)
RAW = ROOT / "build/coarse-W3a/full/r9/gen_role_v2/role_frames.jsonl"
SAMPLE = ART / "n4_claims_prefreeze.jsonl"
OUT = ART / "r9/n4_claims_run2_prefreeze.jsonl"


def rows(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


sample = rows(SAMPLE)
raw_by_word = {row["word"]: row for row in rows(RAW)}
con = sqlite3.connect(f"file:{CANDIDATE / 'placement.sqlite'}?mode=ro", uri=True)
out = []
status_counts = Counter()
claim_count = 0
for sample_row in sample:
    word = sample_row["word"]
    raw = raw_by_word.get(word)
    accepted = con.execute("SELECT frame FROM role_frames WHERE word=?", (word,)).fetchone()
    if raw is None:
        status = "NO_GENERATED_ROW"
        frame = None
    elif raw.get("frame") is None or raw.get("abstained") is True:
        status = "ABSTAINED"
        frame = None
    elif accepted is None:
        status = "REJECTED_BY_READER"
        frame = None
    else:
        status = "ACCEPTED"
        frame = json.loads(accepted[0])
    status_counts[status] += 1
    claims = [
        {"particle": particle, "role": claim["role"], "types": claim["types"]}
        for particle, role_claims in (frame or {}).items()
        for claim in role_claims
    ]
    claim_count += len(claims)
    out.append({"word": word, "source_status": status, "frame": frame, "claims": claims})
con.close()
OUT.write_text(
    "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in out),
    encoding="utf-8",
)
print(json.dumps({"sample_words": len(sample), "source_status": dict(sorted(status_counts.items())),
                  "claim_rows": claim_count, "output": str(OUT)}, ensure_ascii=False, indent=2))
