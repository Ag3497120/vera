#!/usr/bin/env python3
"""Freeze the generated claims used for the preregistered W3-a6 visual checks."""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
ART = ROOT / "artifacts/w3-a6"
CURRENT = ART / "current-r1"
R9 = ROOT / "build/coarse-W3a/full/r9"
R8_MANIFEST = Path("/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2/manifest.json")


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


needs_role = read_jsonl(CURRENT / "needs_role.jsonl")
words = sorted({row["word"] for row in needs_role})
sample = random.Random(20261004).sample(words, 60)
frozen_sample = [row["word"] for row in read_jsonl(CURRENT / "role_sample_words.jsonl")]
if sample != frozen_sample:
    raise SystemExit("N4 frozen sample does not match the preregistered seed and population")

role_rows = {row["word"]: row for row in read_jsonl(R9 / "gen_role/role_frames.jsonl")}
role_sheet = []
for rank, word in enumerate(sample, 1):
    row = role_rows.get(word)
    frame = row.get("frame") if row is not None else None
    availability = "missing" if row is None else "abstained" if frame is None else "present"
    role_sheet.append({"rank": rank, "word": word, "availability": availability, "frame": frame})

ntype_rows = {row["word"]: row for row in read_jsonl(R9 / "gen_ntype/noun_types.jsonl")}
relpos_sheet = []
for word in sorted(ntype_rows):
    row = ntype_rows[word]
    if "RELATIVE_POSITION" in (row.get("types") or []):
        relpos_sheet.append({"word": word, "definition": row.get("definition"), "types": row.get("types")})

role_out = ART / "n4_claims_prefreeze.jsonl"
relpos_out = ART / "n3_relpos_claims_prefreeze.jsonl"
role_out.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in role_sheet), encoding="utf-8")
relpos_out.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in relpos_sheet), encoding="utf-8")

manifest = json.loads(R8_MANIFEST.read_text(encoding="utf-8"))
config = dict(manifest["config"])
config["role_frame_min_sources"] = 1
config_out = ART / "r9_config_eval_min1.json"
config_out.write_text(json.dumps(config, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

freeze_rows = []
for path in (role_out, relpos_out, config_out, CURRENT / "role_sample_words.jsonl"):
    freeze_rows.append(f"{sha256(path)}  {path.relative_to(ROOT)}")
(ART / "r7_prefreeze.sha256").write_text("\n".join(freeze_rows) + "\n", encoding="utf-8")
(ART / "r7_prefreeze.meta.json").write_text(json.dumps({
    "sample_seed": 20261004,
    "sample_population": len(words),
    "sample_words": len(sample),
    "sample_source_sha256": sha256(CURRENT / "role_sample_words.jsonl"),
    "n4_claim_rows": len(role_sheet),
    "n4_missing": sum(r["availability"] == "missing" for r in role_sheet),
    "n4_abstained": sum(r["availability"] == "abstained" for r in role_sheet),
    "n3_relative_position_claims": len(relpos_sheet),
    "r8_rd_min_sources": manifest["config"]["rd_min_sources"],
    "r9_role_frame_min_sources_candidate": config["role_frame_min_sources"],
}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print((ART / "r7_prefreeze.meta.json").read_text(encoding="utf-8"), end="")
print((ART / "r7_prefreeze.sha256").read_text(encoding="utf-8"), end="")
