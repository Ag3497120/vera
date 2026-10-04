"""W5-f F-4: only well-shaped sovereign identifiers classify as human."""
import importlib.util
import json
import os
from pathlib import Path
import sys

import pytest

from verantyx import basis_policy as bp
from verantyx import sovereign as sov


TREE = Path(__file__).resolve().parents[1]
INPUTS = json.loads((TREE / "artifacts" / "w5-f" / "h4_w5f_inputs.json").read_text(encoding="utf-8"))
CLAIM = ""
QUERY = "W5F frozen policy probe"
VALID_CONFIRM_ID = "0123456789abcdef01234567"


@pytest.fixture(autouse=True)
def _clean_sovereign_environment(monkeypatch):
    for name in ("VERA_SOVEREIGN_ROOT", "VERA_SOVEREIGN_STORE", "VERA_P4_INDEX"):
        monkeypatch.delenv(name, raising=False)


def _answer(source):
    return {"kind": "answer", "verdict": "ANSWER", "text": CLAIM,
            "sources": [source], "evidence": [CLAIM], "door": "w5f"}


def _load_w5e_test_helpers():
    path = TREE / "tests" / "test_basis_policy_w5e.py"
    spec = importlib.util.spec_from_file_location("w5f_prior_basis_tests", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_frozen_self_claim_shapes_abstain_without_answering():
    assert INPUTS
    for case in INPUTS:
        source = {"source": "caller-claim", "text": CLAIM, **case["source"]}
        assert bp._class_of(source) == case["expect"], case["id"]
        out, _ = bp.apply_to_ask(_answer(source), bp.AskPolicy(), query=QUERY, mode="legacy", documents=[])
        assert out["basis_policy"]["basis_original"] == bp.UNKNOWN_ORIGIN, (case["id"], out)
        assert out["basis_policy"]["counts"]["unknown_origin"] == 1, (case["id"], out)
        assert not out["basis_policy"]["outcome"].startswith("ANSWER"), (case["id"], out)
        assert out["verdict"] != "ANSWER", (case["id"], out)


def test_a_well_shaped_self_claim_is_human_but_generated_still_wins():
    source = {"family": "memory_sovereign", "origin": "human_confirmed",
              "store_id": "store-r1", "confirm_id": VALID_CONFIRM_ID, "source": "caller-claim", "text": CLAIM}
    assert bp._class_of(source) == "human"
    classification = bp.classify_sources([source])
    assert classification.policy_basis == "HUMAN"
    out, _ = bp.apply_to_ask(_answer(source), bp.AskPolicy(), query=QUERY, mode="legacy", documents=[])
    assert out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS"
    generated = {**source, "origin": "generated"}
    assert bp._class_of(generated) == "generated"


def test_real_sovereign_confirmation_record_remains_human_and_answers(tmp_path, monkeypatch):
    prior = _load_w5e_test_helpers()
    prior._store(tmp_path, monkeypatch)
    generated = prior._generated(prior.CONFIRMED)
    request, rc = bp.apply_to_ask(generated, bp.AskPolicy(human_present=True),
                                  query=prior.QUERY, mode="legacy", documents=[])
    assert rc == 0 and request["verdict"] == "CONFIRM_REQUEST"
    recorded, rc = bp.apply_to_ask(generated, bp.AskPolicy(confirm=(request["confirm"]["id"], "yes")),
                                   query=prior.QUERY, mode="legacy", documents=[])
    assert rc == 0 and recorded["verdict"] == "CONFIRMED_HUMAN_RECORD"
    out, rc = bp.apply_to_ask(generated, bp.AskPolicy(), query=prior.QUERY, mode="legacy", documents=[])
    assert rc == 0 and out["verdict"] == "ANSWER" and out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS"
    source = out["sources"][0]
    assert source["store_id"] and len(source["confirm_id"]) == 24
    assert bp._class_of(source) == "human"
    assert bp.classify_sources([source]).policy_basis == "HUMAN"
    copied, rc = bp.apply_to_ask(_answer(source), bp.AskPolicy(), query=QUERY, mode="legacy", documents=[])
    assert rc == 0 and copied["verdict"] == "ANSWER"
    assert copied["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS"


def test_classification_version_moves_only_to_five():
    assert bp.CLASSIFY_VERSION == 5
    assert bp.TABLE_VERSION == 1 and bp.CONFIRM_ID_VERSION == 2
    source = {"family": "memory_sovereign", "origin": "human_confirmed",
              "store_id": "store-r1", "confirm_id": VALID_CONFIRM_ID, "source": "caller-claim", "text": CLAIM}
    out, _ = bp.apply_to_ask(_answer(source), bp.AskPolicy(), query=QUERY, mode="legacy", documents=[])
    assert out["basis_policy"]["classify_version"] == 5
