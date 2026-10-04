"""Replay the independent review's already-frozen F-1 cases through public entry modes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import runpy
import sys


TREE = Path(__file__).resolve().parents[3]
INPUT = Path("/private/tmp/w5f_review_r1/holdout.r1.jsonl")
EXPECTED_SHA256 = "aea0fb3f6b8158dc8884851e019bd538ee7f2c0305f4e2808c40c26dc6732617"
R8 = Path("/Users/motonisihikoudai/Projects/vera-impl/build/coarse-W3a/full/r8/run2")
sys.path.insert(0, str(TREE))

from verantyx import semantic_read as SR


def reasons(out):
    values = list((out.get("abstain") or {}).get("reasons") or ())
    for item in out.get("unsupported") or ():
        if isinstance(item, dict):
            values.extend(item.get("reasons") or ())
    return values


raw = INPUT.read_bytes()
digest = hashlib.sha256(raw).hexdigest()
if digest != EXPECTED_SHA256:
    raise SystemExit(f"HOLDOUT_HASH_MISMATCH {digest}")
rows = [json.loads(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
targets = [row for row in rows if row["id"] in {
    "F1_A01", "F1_A02", "F1_A03", "F1_A04", "F1_A07", "F1_A09",
    "F1_A11", "F1_A12", "F1_A13", "F1_A14", "F1_A20",
}]
fake = runpy.run_path(str(TREE / "tests/reading_soundness/w3b1_fakes.py"))
failures = []
for mode in ("none", "fake", "r8"):
    if mode == "r8" and not R8.is_dir():
        raise SystemExit(f"ENV_MISSING[r8_placement]: {R8}")
    for row in targets:
        placement = None if mode == "none" else fake["FixtureQuery"]() if mode == "fake" else str(R8)
        out = SR.read(row["text"], "ja", placement=placement)
        observed = reasons(out)
        ok = (not out["readable"] and any(
            reason.startswith("PLACEMENT_QUOTED_PARTICLE_AFTER_CASE") for reason in observed))
        print(mode, row["id"], "ABSTAIN" if not out["readable"] else "READ",
              "REASON_OK" if ok else "REASON_MISSING")
        if not ok:
            failures.append((mode, row["id"], out))
print("SUMMARY", {"input_sha256": digest, "cases": len(targets),
                  "modes": 3, "failures": len(failures)})
if failures:
    raise SystemExit(1)
