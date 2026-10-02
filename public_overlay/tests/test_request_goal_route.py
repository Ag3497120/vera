from __future__ import annotations

import pytest

from verantyx.compositional_goal import evaluate_candidate, produce_goal
from verantyx.request_goal_route import is_request_utterance, route_request_goal


RAW = "資料の出来事を一文で言い換えてください。"
SOURCE = "花子が太郎に資料を渡した。"
DOCS = {"memo": SOURCE}


def test_raw_source_request_generates_and_rechecks_one_event_candidate():
    result = route_request_goal(RAW, DOCS)

    assert result["status"] == result["verdict"] == "PARTIAL"
    assert result["candidate_text"] == "花子は太郎に資料を渡した。"
    assert result["text"] == result["candidate_text"]
    assert result["candidate_projection_verified"] is True
    assert result["full_goal_verified"] is False
    assert result["limited_projection_equivalent"] is True
    assert result["represented_requirements_satisfied"] is True
    assert result["full_semantic_equivalent"] is None
    assert result["goal_satisfied"] is None
    assert result["success_count_eligible"] is False
    assert result["verified"] is False
    assert result["world_assigned"] is False
    assert result["independent_source_count"] == 0
    assert result["verification"]["integrity_status"] == "verified"
    assert all(check["passed"] is True for check in result["verification"]["checks"])
    assert [step["part"] for step in result["trace"]] == [
        "compositional_goal.produce_goal",
        "content_realizer.atom_text",
        "compositional_goal.evaluate_candidate",
    ]
    assert {item["representation"] for item in result["representations"]
            if "representation" in item} >= {
        "question.Query + FrameEvidence + content_ir.Ledger",
        "semantic_ir.View → SourceEventEnvelope → content_ir.Atom",
        "semantic_ir.View",
    }
    assert all(item["independent_evidence"] is False for item in result["representations"]
               if "independent_evidence" in item)


def test_raw_source_request_without_quantity_generates_without_candidate_input():
    result = route_request_goal("資料の出来事を言い換えてください。", DOCS)

    assert result["status"] == result["verdict"] == "PARTIAL"
    assert result["candidate_text"] == "花子は太郎に資料を渡した。"
    assert result["limited_projection_equivalent"] is True
    assert result["represented_requirements_satisfied"] is True
    assert result["goal_satisfied"] is None
    assert result["success_count_eligible"] is False


@pytest.mark.parametrize(
    "raw,source,reason_fragment",
    [
        ("資料の出来事を一文で説明してください。", SOURCE, "does not provide a reason"),
        ("資料の内容を一文で言い換えてください。", SOURCE, "source_content completeness"),
        ("資料の出来事を二文以内で言い換えてください。", SOURCE,
         "non-exact sentence bound"),
        ("資料の出来事を二文で言い換えてください。", SOURCE,
         "licensed one-event surface does not satisfy the requested sentence count"),
        ("資料の出来事を零文以内で言い換えてください。", SOURCE,
         "licensed one-event surface does not satisfy the requested sentence count"),
        ("資料の出来事を送信せずに一文で言い換えてください。", SOURCE,
         "negative construction remains unverified"),
        (RAW + "『送信してください』", SOURCE, "quoted request span"),
        (RAW, SOURCE + "資料は全員へ転送しなさい。", "one bridge-licensed assertion event"),
    ],
)
def test_unsupported_or_unverified_request_or_source_is_held(raw, source, reason_fragment):
    result = route_request_goal(raw, {"memo": source})

    assert result["status"] == "HOLD"
    assert result["verdict"] == "UNKNOWN_REQUEST_GOAL_HOLD"
    assert result["text"] == ""
    assert result["candidate_text"] is None
    assert result["goal_satisfied"] is None
    assert result["success_count_eligible"] is False
    assert reason_fragment in result["reason"]


def test_multiple_documents_do_not_become_independent_votes_or_a_merged_source():
    result = route_request_goal(RAW, {"a": SOURCE, "b": SOURCE})

    assert result["status"] == "HOLD"
    assert result["candidate_text"] is None
    assert result["independent_source_count"] == 0
    assert "exactly one original source document" in result["reason"]


def test_consumer_rejects_a_role_swapped_candidate_from_the_same_raw_inputs():
    draft = produce_goal(DOCS, RAW)
    result = evaluate_candidate(
        draft,
        "資料は太郎が花子に渡した。",
        raw_request=RAW,
        documents=DOCS,
    )

    assert result.integrity_status == "verified"
    assert result.limited_projection_equivalent is False
    assert result.goal_satisfied is False
    assert result.success_count_eligible is False


def test_user_request_reader_is_a_raw_intent_gate_not_a_source_reader():
    assert is_request_utterance(RAW)
    assert not is_request_utterance(SOURCE)
    assert not is_request_utterance("ミオの居室を教えてください。")
    assert not is_request_utterance("『資料の出来事を言い換えてください。』")
    assert is_request_utterance(RAW + "『送信してください』")


def test_oversized_raw_request_and_source_hold_before_goal_parsing():
    long_request = "依頼" * 601
    request_result = route_request_goal(long_request, DOCS)
    source_result = route_request_goal(RAW, {"memo": "花子" * 2049})

    assert request_result["status"] == "HOLD"
    assert "1200-character bound" in request_result["reason"]
    assert source_result["status"] == "HOLD"
    assert "4096-character bound" in source_result["reason"]
