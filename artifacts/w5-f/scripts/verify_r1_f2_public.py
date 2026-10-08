"""Replay the independent review's already-frozen F-2 cases through public entry modes."""
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
directions = [row for row in rows if row["id"].startswith("F2_A")]
controls = [row for row in rows if row["id"].startswith("F2_R")]
fake = runpy.run_path(str(TREE / "tests/reading_soundness/w3b1_fakes.py"))
for mode in ("none", "fake", "r8"):
    if mode == "r8" and not R8.is_dir():
        raise SystemExit(f"ENV_MISSING[r8_placement]: {R8}")
    counts = {"direction_read": 0, "direction_target_reason": 0,
              "direction_other_abstain": 0, "control_read": 0,
              "control_abstain": 0}
    for group, items in (("direction", directions), ("control", controls)):
        for row in items:
            placement = None if mode == "none" else fake["FixtureQuery"]() if mode == "fake" else str(R8)
            out = SR.read(row["text"], "ja", placement=placement)
            why = reasons(out)
            if group == "direction":
                if out["readable"]:
                    counts["direction_read"] += 1
                elif any(reason.startswith("RELATIONAL_NOUN_FILLER") for reason in why):
                    counts["direction_target_reason"] += 1
                else:
                    counts["direction_other_abstain"] += 1
            else:
                counts["control_read" if out["readable"] else "control_abstain"] += 1
    print(mode, json.dumps(counts, ensure_ascii=False, sort_keys=True))
print("SUMMARY", {"input_sha256": digest, "direction_cases": len(directions),
                  "place_controls": len(controls)})
