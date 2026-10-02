"""Q1/Q2 on the self-made fixtures, and a check that the fixtures have the promised shape."""
from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent / "conduct_ask"))
import ca_helpers as H  # noqa: E402
import run_bank  # noqa: E402

ITEMS = H.FIXTURES / "items.jsonl"


@pytest.fixture(scope="module")
def items():
    return H.jsonl_items()


def test_fixture_shape_matches_the_promise(items):
    frames = sorted(H.FRAMES.glob("*.md"))
    assert len(frames) >= 10 and len(items) >= 130
    english = [f for f in frames if "en" in {i["lang"] for i in items if i["frame_id"] == f.stem}]
    assert len(english) >= 3 and len(frames) - len(english) >= 4
    per_frame = collections.Counter(i["frame_id"] for i in items)
    assert set(per_frame) == {f.stem for f in frames} and min(per_frame.values()) >= 12
    cat = collections.Counter(i["w2c"]["category"] for i in items)
    for name in ("direct", "combined", "oov", "escalate"):
        assert abs(cat[name] / len(items) - 0.25) <= 0.03, (name, cat)
    oov = [i for i in items if i["w2c"]["category"] == "oov"]
    none = [i for i in oov if i["w2c"]["oov_none"]]
    assert abs(len(none) / len(oov) - 1 / 3) <= 0.05
    assert all(i["expect"]["decision"] == "escalate" for i in none)
    reasons = collections.Counter(i["w2c"]["escalate_reason"] for i in items if i["w2c"]["category"] == "escalate")
    for r in ("FRAME_SILENT", "FRAME_CONFLICT", "HUMAN_APPROVAL_REQUIRED", "OUT_OF_RANGE"):
        assert reasons[r] >= 5, reasons
    assert sum(1 for i in items if i["w2c"]["trap"]) >= 8
    perm = collections.Counter(i["w2c"]["permission"] for i in items if i["w2c"]["permission"])
    assert set(perm) == {"可", "不可", "上げる"} and max(perm.values()) - min(perm.values()) <= 3
    held = {ln.strip() for ln in (H.FIXTURES / "holdout.txt").read_text(encoding="utf-8").splitlines() if ln.strip()}
    assert 3 <= len(held) <= 4 and held <= set(per_frame)
    assert any("en" == next(i["lang"] for i in items if i["frame_id"] == h) for h in held)


def measure(tmp_path, mode):
    out = tmp_path / mode
    assert run_bank.main(["--items", str(ITEMS), "--frames", str(H.FRAMES), "--vocab-llm", mode, "--split", "all",
                          "--out", str(out)]) == 0
    assert run_bank.main(["--recount", str(out)]) == 0
    return json.loads((out / "summary.json").read_text(encoding="utf-8")), out


@pytest.mark.parametrize("mode", ["fake", "off"])
def test_q1_wrong_answers_are_at_most_two_percent_and_q2_ranges(tmp_path, mode, capsys):
    s, out = measure(tmp_path, mode)
    capsys.readouterr()
    assert s["total"] == len(H.jsonl_items())
    assert s["q1_rate"] <= 0.02, [json.loads(ln)["id"] for ln in (out / "results.jsonl").read_text().splitlines()
                                  if json.loads(ln)["verdict"] in ("false_answer", "wrong_answer")]
    assert s["escalate_correct_rate"] >= 0.90
    if mode == "fake":
        assert s["q2_answer_rate"] >= 0.70
        for cat in ("direct", "combined", "oov"):
            assert s["q2_by_category"][cat]["n"] > 0 and s["q2_by_category"][cat]["rate"] >= 0.70, cat
    else:
        for cat in ("direct", "combined"):
            assert s["q2_by_category"][cat]["rate"] >= 0.70, cat
        assert s["q2_by_category"]["oov"]["rate"] == 0.0     # off: every out-of-vocabulary question goes up
    assert set(s["by_split"]) == {"dev", "holdout"} and set(s["by_permission"]) == {"可", "不可", "上げる"}
