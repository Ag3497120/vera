#!/usr/bin/env python3
"""Freeze the unique predicate-seed words before querying r8 or r9."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from verantyx import coarse_types as ct

ROOT = Path(__file__).resolve().parents[3]
ART = ROOT / "artifacts/w3-a6"
words = sorted({word for values in ct.SEEDS_PRED.values() for word in values})
out = ART / "n5_seed_words_prefreeze.jsonl"
out.write_text("".join(json.dumps({"word": word}, ensure_ascii=False, separators=(",", ":")) + "\n" for word in words), encoding="utf-8")
meta = {"source": "verantyx/coarse_types.py:SEEDS_PRED", "words": len(words),
        "sha256": hashlib.sha256(out.read_bytes()).hexdigest()}
(ART / "n5_seed_words_prefreeze.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(meta, ensure_ascii=False, indent=2))
