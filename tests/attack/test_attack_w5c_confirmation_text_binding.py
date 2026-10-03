# W5-d: copied from attacks/W5-c/test_attack_confirmation_text_binding.py; unchanged
"""Executable probes for W5-c. Expected failures are attack hits; synthetic data only."""
from __future__ import annotations

import json

import pytest

from verantyx import basis_policy as bp
from verantyx import sovereign as sov


QUERY = "内容は何ですか？"
CASES = [
    pytest.param("窓が光った。", "窓が 光った。", "whitespace", id="whitespace"),
    pytest.param("窓が光った。", "窓が光った!", "punctuation", id="punctuation"),
    pytest.param("コードはＡＢＣです。", "コードはABCです。", "NFKC", id="nfkc"),
]


@pytest.fixture(autouse=True)
def _clear_sovereign_environment(monkeypatch):
    monkeypatch.delenv("VERA_SOVEREIGN_ROOT", raising=False)
    monkeypatch.delenv("VERA_SOVEREIGN_STORE", raising=False)


@pytest.mark.parametrize("confirmed_claim,current_claim,variant", CASES)
def test_attack_a_confirmed_sentence_must_equal_the_current_generated_claim(
    tmp_path, monkeypatch, confirmed_claim, current_claim, variant
):
    root = str(tmp_path / "sovereign")
    assert sov.create(root, "store-a", "owner", consent_promote=True)["verdict"] == "CREATED"
    monkeypatch.setenv("VERA_SOVEREIGN_ROOT", root)
    monkeypatch.setenv("VERA_SOVEREIGN_STORE", "store-a")

    confirmed_source = {**{
        "family": "local", "source": "local:old:1", "source_file": "old.jsonl", "line": 1,
        "sha": "old", "origin": "generated",
    }, "text": confirmed_claim}
    confirmed_result = {"kind": "answer", "verdict": "ANSWER", "text": confirmed_claim,
                        "sources": [confirmed_source], "evidence": [confirmed_claim], "door": "attack"}
    question, question_rc = bp.apply_to_ask(
        confirmed_result, bp.AskPolicy(human_present=True), query=QUERY, mode="legacy", documents=[],
    )
    assert question_rc == 0 and question["verdict"] == "CONFIRM_REQUEST"
    accepted, accepted_rc = bp.apply_to_ask(
        confirmed_result, bp.AskPolicy(confirm=(question["confirm"]["id"], "yes")),
        query=QUERY, mode="legacy", documents=[],
    )
    assert accepted_rc == 0 and accepted["verdict"] == "CONFIRMED_HUMAN_RECORD" and accepted["wrote"] == 1

    generated = {
        "family": "local", "source": "local:new:1", "source_file": "new.jsonl", "line": 1,
        "sha": "new", "origin": "generated", "text": current_claim,
    }
    result, rc = bp.apply_to_ask(
        {"kind": "answer", "verdict": "ANSWER", "text": current_claim,
         "sources": [generated], "evidence": [current_claim], "door": "attack"},
        bp.AskPolicy(), query=QUERY, mode="legacy", documents=[],
    )

    assert rc == 0
    if result["basis_policy"]["outcome"] != "ABSTAIN":
        pytest.fail(json.dumps({
            "variant": variant,
            "confirmed_claim": confirmed_claim,
            "generated_claim": current_claim,
            "actual_outcome": result["basis_policy"]["outcome"],
            "actual_verdict": result["verdict"],
            "actual_text": result["text"],
            "record_use": result["basis_policy"]["sovereign"],
        }, ensure_ascii=False, sort_keys=True))
