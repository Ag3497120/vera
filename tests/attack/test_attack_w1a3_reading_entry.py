# W5-a: copied from attacks/W1-a3/test_attack_reading_entry.py; unchanged
"""Counterexamples against the W1-a3 reading-entry contract.

Run with the specified wiring Python and this tree on PYTHONPATH. These tests
are intentionally expected to fail on the current entry.
"""
import json
import os
import subprocess
import sys

import pytest


TREE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PYTHON = sys.executable  # integration: the test must run on any host (the Air gate has no Pro venv)


def entry(text):
    env = os.environ.copy()
    env.update({"PYTHONPATH": TREE, "PYTHONDONTWRITEBYTECODE": "1"})
    result = subprocess.run(
        [PYTHON, "-m", "verantyx.semantic_read", "--text=" + text],
        cwd=TREE, env=env, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    return json.loads(result.stdout)


@pytest.mark.parametrize("text", ["昔の海岸が思い返された。", "昔の庭が思い起こされた。"])
def test_unlisted_spontaneous_recollection_is_not_returned_as_passive(text):
    # These recollection predicates allow a spontaneous reading here; the
    # surface れる does not decide between spontaneous and passive.
    out = entry(text)
    assert out["readable"] is False, out
    assert any(reason.startswith("UNDETERMINED_VOICE") for reason in out["abstain"]["reasons"]), out


def test_readable_true_does_not_coexist_with_an_unsupported_clause():
    out = entry("ふと昔の海岸が思い返された。")
    assert out["readable"] is False, out
    assert out["clauses"] == [] and out["relations"] == [], out


def test_a_motion_path_is_not_returned_as_an_object_or_agent():
    out = entry("自転車が細道を駆け抜けた。")
    assert out["readable"] is False, out


def test_an_english_past_participle_keeps_the_dictionary_predicate():
    out = entry("The chair was repaired by them.")
    assert out["readable"] is True, out
    assert out["clauses"][0]["predicate"] == "repair", out
