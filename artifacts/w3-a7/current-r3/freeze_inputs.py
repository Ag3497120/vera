#!/usr/bin/env python3
"""Freeze the registered W3-a7 r10 build, sample, and rule inputs (no generator ledger)."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
A6_BUILD = Path("/Users/motonisihikoudai/Projects/vera-impl/wt/W3-a6-S/build/coarse-W3a/full/r9")
SHARED = Path("/Users/motonisihikoudai/Projects/vera-impl/build")
WIRING = Path("/Users/motonisihikoudai/vera-wiring")
R10_GEN = ROOT / "build/coarse-W3a/full/r10/gen_role_v3"

FILES = [
    ROOT / "docs/COARSE_PLACEMENT.md",
    ROOT / "tools/build_coarse_placement.py",
    ROOT / "tools/gen_coarse_evidence.py",
    ROOT / "verantyx/coarse_types.py",
    ROOT / "verantyx/coarse_place.py",
    ROOT / "tests/test_gen_coarse_evidence.py",
    ROOT / "tests/test_gen_coarse_evidence_trial_gate.py",
    ROOT / "tests/coarse_place/data/w3a6_expect.json",
    ROOT / "tests/coarse_place/data/unknown_words.jsonl",
    ROOT / "tests/coarse_place/data/dev_unknown.jsonl",
    ROOT / "artifacts/w3-a3/exclude_coined.jsonl",
    ROOT / "artifacts/w3-a/FROZEN.json",
    ROOT / "artifacts/w3-a/holdout_2000.jsonl",
    ROOT / "artifacts/w3-a/dev_l1_1000.jsonl",
    ROOT / "artifacts/w3-a6/r9/r9_config_run2.json",
    ROOT / "artifacts/w3-a6/r9/manifest.json",
    ROOT / "artifacts/w3-a6/r9/n4_claims_run2_prefreeze.jsonl",
    ROOT / "artifacts/w3-a6/r9/n4_visual_labels_run2.jsonl",
    ROOT / "artifacts/w3-a6/n5_seed_words_prefreeze.jsonl",
    ROOT / "artifacts/w3-a7/current-r1/needs_role_v3.jsonl",
    ROOT / "artifacts/w3-a7/current-r1/prompt_role_v2.txt",
    ROOT / "artifacts/w3-a7/current-r1/trial_results/4f6b0bb9-22e7-40a5-96dd-361a2f3d6297.json",
    ROOT / "artifacts/w3-a7/current-r2/trial_judge.py",
    ROOT / "artifacts/w3-a7/current-r2/trial_test_cases.json",
    ROOT / "artifacts/w3-a7/current-r2/trial_test_freeze.r2.sha256",
    ROOT / "artifacts/w3-a7/current-r3/build_run1.sh",
    ROOT / "artifacts/w3-a7/current-r3/freeze_inputs.py",
    A6_BUILD / "run2/manifest.json",
    A6_BUILD / "run2/placement.sqlite",
    A6_BUILD / "gen_ntype/noun_types.jsonl",
    R10_GEN / "role_frames.jsonl",
    R10_GEN / "summary.json",
    R10_GEN / "batches.json",
    R10_GEN / "schema.json",
    WIRING / "data/jawiki_leads.full.jsonl",
    SHARED / "coarse-W3a/generated/definitions.jsonl",
    SHARED / "coarse-W3a/full/r6/gen_pred/frames.jsonl",
    SHARED / "coarse-W3a/full/r8/gen_pred/frames.jsonl",
]

OUT = ROOT / "artifacts/w3-a7/current-r3/input_freeze.sha256"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    missing = [str(path) for path in FILES if not path.is_file()]
    if missing:
        raise SystemExit("missing registered input(s): " + ", ".join(missing))
    lines = [f"{sha256(path)}  {path}" for path in FILES]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"files={len(FILES)}")
    print(f"freeze={OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
