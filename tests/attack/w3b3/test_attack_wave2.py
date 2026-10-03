"""Assertions for the wave-2 expectations, frozen before their first run."""
import json
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent


@pytest.fixture(scope="module")
def rows():
    p = HERE / "results" / "wave2_observations.jsonl"
    assert p.is_file(), "run the wave-2 corpus first: python attacks/W3-b3/run_wave2.py"
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()]


def test_wave2_refusal_shapes_and_placement_free_parity(rows):
    bad = []
    for row in rows:
        case = row["case"]
        if not row["absent_byte_equal"]:
            bad.append(case["id"] + ": placement-free byte mismatch")
        out = row["configured"]
        if out.get("readable") is True or out.get("relations"):
            bad.append("%s: expected typed abstention, got readable=%r relations=%r" %
                       (case["id"], out.get("readable"), out.get("relations")))
    assert not bad, repr(bad)
