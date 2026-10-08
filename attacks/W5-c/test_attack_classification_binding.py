"""Probes for origin labels, same-root confirmation routing, record order, and source order."""
from __future__ import annotations

import json
from itertools import permutations

import pytest

from verantyx import basis_policy as bp
from verantyx import sovereign as sov


QUERY = "窓は？"
CLAIM = "窓が光った。"


@pytest.fixture(autouse=True)
def _clear_sovereign_environment(monkeypatch):
    monkeypatch.delenv("VERA_SOVEREIGN_ROOT", raising=False)
    monkeypatch.delenv("VERA_SOVEREIGN_STORE", raising=False)
    monkeypatch.delenv("VERA_P4_INDEX", raising=False)


def _generated():
    return {"family": "local", "source": "local:new:1", "source_file": "new.jsonl", "line": 1,
            "sha": "new", "origin": "generated", "text": CLAIM}


def _answer(sources):
    return {"kind": "answer", "verdict": "ANSWER", "text": CLAIM,
            "sources": sources, "evidence": [s["text"] for s in sources], "door": "attack"}


@pytest.mark.parametrize("family", ["Document", "documents", "user", None, "MISSING"])
def test_attack_a_family_spelling_or_omission_does_not_create_human_evidence(family):
    source = {"text": CLAIM}
    if family != "MISSING":
        source["family"] = family
    sc = bp.classify_sources([source])
    assert sc.counts["human"] == 0, sc.to_dict()
    if family == "user":
        assert sc.counts["request_text"] == 1 and sc.cited == 0 and sc.policy_basis == "NONE"
    else:
        assert sc.unknown_origin == 1 and sc.policy_basis == "UNKNOWN_ORIGIN"


@pytest.mark.parametrize("origin", ["human", "Human", "user_confirmed"])
def test_attack_b_unrecognized_human_looking_origin_does_not_create_human_evidence(origin):
    sc = bp.classify_sources([{"family": "local", "origin": origin, "text": CLAIM}])
    assert sc.counts["human"] == 0 and sc.policy_basis == "UNKNOWN_ORIGIN", sc.to_dict()


def test_attack_b_a_document_label_without_a_document_argument_is_not_human():
    source = {"family": "document", "source": "invented.txt", "text": "invented claim"}
    sc = bp.classify_sources([source])
    assert sc.counts["human"] == 0 and sc.policy_basis == "UNKNOWN_ORIGIN", sc.to_dict()


def test_attack_a_document_family_and_nonempty_documents_do_not_prove_the_source_text_is_user_supplied():
    fabricated = {"family": "document", "source": "fabricated.txt", "text": "渡された文書に無い文。"}
    out, rc = bp.apply_to_ask(
        _answer([fabricated]), bp.AskPolicy(), query=QUERY, mode="round5", documents=["memo.txt"],
    )
    assert rc == 0
    if out["basis_policy"]["outcome"] != "ABSTAIN":
        pytest.fail(json.dumps({
            "documents": ["memo.txt"], "source": fabricated,
            "outcome": out["basis_policy"]["outcome"], "basis": out["basis_policy"]["basis_original"],
            "actual_verdict": out["verdict"], "actual_text": out["text"],
        }, ensure_ascii=False, sort_keys=True))


def test_attack_c_a_confirmation_id_from_another_store_in_the_same_root_cannot_be_replayed(
    tmp_path, monkeypatch
):
    root = str(tmp_path / "sovereign")
    for sid in ("store-a", "store-b"):
        assert sov.create(root, sid, sid, consent_promote=True)["verdict"] == "CREATED"
    source = _generated()
    monkeypatch.setenv("VERA_SOVEREIGN_ROOT", root)
    monkeypatch.setenv("VERA_SOVEREIGN_STORE", "store-a")
    issued, _ = bp.apply_to_ask(_answer([source]), bp.AskPolicy(human_present=True),
                                query=QUERY, mode="legacy", documents=[])
    confirm_id = issued["confirm"]["id"]

    monkeypatch.setenv("VERA_SOVEREIGN_STORE", "store-b")
    replay, rc = bp.apply_to_ask(_answer([source]), bp.AskPolicy(confirm=(confirm_id, "yes")),
                                 query=QUERY, mode="legacy", documents=[])
    written = {sid: sov.open_ledger(root, sid).events() for sid in ("store-a", "store-b")}
    assert rc == 1 and replay["verdict"] == "CONFIRM_TARGET_MISMATCH" and replay["wrote"] == 0, replay
    assert all(not events for events in written.values()), written


@pytest.mark.parametrize("order,last", [("yes no", "no"), ("no yes", "yes")])
def test_attack_e_the_last_yes_or_no_for_one_confirmation_id_wins(tmp_path, monkeypatch, order, last):
    root = str(tmp_path / "sovereign")
    sid = "store-a"
    assert sov.create(root, sid, "owner", consent_promote=True)["verdict"] == "CREATED"
    monkeypatch.setenv("VERA_SOVEREIGN_ROOT", root)
    monkeypatch.setenv("VERA_SOVEREIGN_STORE", sid)
    source = _generated()
    destination = sov.basis_confirmation_destination(root, sid)
    confirm_id = bp._confirm_id(QUERY, CLAIM, [source], destination)
    for answer in order.split():
        status = "HUMAN_CONFIRMED" if answer == "yes" else "REJECTED_GENERATED"
        payload = {"record": "basis_confirmation", "status": status, "witness": "user_confirmation",
                   "confirm_id": confirm_id, "query": QUERY, "claim": CLAIM,
                   "generated_sources": [{"family": "local", "source_id": "local:new.jsonl:1", "sha": "new"}],
                   "table_version": 1, "destination": destination}
        if answer == "yes":
            payload["origin"] = "human_confirmed"
        assert sov.append_basis_confirmation(root, sid, payload)["verdict"] == "APPENDED"

    out, rc = bp.apply_to_ask(_answer([source]), bp.AskPolicy(), query=QUERY, mode="legacy", documents=[])
    assert rc == 0
    if last == "no":
        assert out["basis_policy"]["outcome"] == "ABSTAIN"
        assert out["verdict"] == "UNKNOWN_GENERATED_REJECTED_BY_USER"
    else:
        assert out["basis_policy"]["outcome"] == "ANSWER_HUMAN_BASIS"
        assert out["text"] == CLAIM


def test_attack_f_source_order_does_not_change_unknown_origin_class_or_outcome():
    generated = _generated()
    human = {"family": "memory_sovereign", "origin": "human_confirmed", "text": CLAIM}
    unknown = {"family": "local", "text": CLAIM}
    observed = set()
    for ordered in permutations([generated, human, unknown]):
        out, _ = bp.apply_to_ask(_answer(list(ordered)), bp.AskPolicy(human_present=True),
                                 query=QUERY, mode="legacy", documents=[])
        observed.add((out["basis_policy"]["basis_original"], out["basis_policy"]["outcome"], out["verdict"]))
    assert observed == {("UNKNOWN_ORIGIN", "ABSTAIN", "UNKNOWN_ORIGIN_SOURCE")}, observed


def test_attack_f_duplicate_sources_change_counts_but_not_the_policy_class():
    generated = _generated()
    unknown = {"family": "local", "text": CLAIM}
    outputs = []
    for sources in ([generated, unknown], [unknown, generated, unknown], [unknown, unknown, generated]):
        out, _ = bp.apply_to_ask(_answer(list(sources)), bp.AskPolicy(human_present=True),
                                 query=QUERY, mode="legacy", documents=[])
        outputs.append((out["basis_policy"]["basis_original"], out["basis_policy"]["outcome"], out["verdict"]))
    assert set(outputs) == {("UNKNOWN_ORIGIN", "ABSTAIN", "UNKNOWN_ORIGIN_SOURCE")}, outputs
