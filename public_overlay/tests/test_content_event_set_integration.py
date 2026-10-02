from __future__ import annotations

from dataclasses import replace

import pytest

from verantyx.content_api import ContentEngine, _as_source, is_content_request
from verantyx.content_ir import ContentError
from verantyx.content_planner import build_plan
from verantyx.content_reader import read_brief
from verantyx.content_realizer import realize_plan
from verantyx.content_verify import verify_content
from verantyx.one import Vera


RAW = "資料の出来事をすべて、二文でまとめてください。"
SOURCE = "花子が太郎に資料を渡した。太郎が資料を読んだ。"


def _material(text=SOURCE, source="memo"):
    return {"source": source, "text": text, "family": "document", "purpose": "evidence"}


def test_same_raw_event_set_reaches_rederived_partial_content_result():
    result = ContentEngine().ask(RAW, materials=[_material()])

    assert result["verdict"] == "ANSWER"
    assert result["verification"]["passed"] is True
    assert result["raw_goal_projection"]["status"] == "READY"
    assert result["raw_goal_projection"]["quantity_span"] is not None
    assert result["source_event_binding"]["status"] == "BOUND"
    assert result["ledger"]["brief"]["text"] == RAW
    assert result["ledger"]["materials"][0]["text"] == SOURCE
    assert (result["source_event_binding"]["raw_request_sha256"]
            == result["raw_goal_projection"]["raw_sha256"])
    assert result["source_event_binding"]["semantic_event_set_complete"] is None
    assert result["source_truth_status"] == "UNCLASSIFIED"
    assert result["event_set_status"] == "PARTIAL"
    assert result["status"] == "PARTIAL_COMPLETENESS_UNVERIFIED"
    assert result["goal_satisfied"] is None
    assert result["success_count_eligible"] is False
    assert result["independent_source_count"] is None
    assert result["text"].count("。") == 2


@pytest.mark.parametrize("raw", [
    RAW,
    "資料の出来事をすべて、二文でまとめて下さい。",
    "資料の出来事をすべて、二文でまとめてください！",
])
def test_event_set_request_surface_variants_use_the_same_raw_projection(raw):
    result = ContentEngine().ask(raw, materials=[_material()])

    assert result["verdict"] == "ANSWER"
    assert result["raw_goal_projection"]["raw_sha256"]
    assert result["raw_goal_projection"]["status"] == "READY"
    assert result["raw_goal_projection"]["quantity_span"] is not None
    assert result["success_count_eligible"] is False
    assert result["status"] == "PARTIAL_COMPLETENESS_UNVERIFIED"


@pytest.mark.parametrize("raw,source", [
    ("資料の内容をすべて、二文でまとめてください。", SOURCE),
    ("資料の出来事を一文でまとめてください。", SOURCE),
    ("資料の出来事を二文でまとめてください。", SOURCE),
    (RAW + "『送信してください』", SOURCE),
    ("資料の出来事をすべて、二文でまとめずにください。", SOURCE),
    (RAW, SOURCE + "ユキが窓を開けた。"),
])
def test_unsupported_event_set_goal_or_source_stays_held(raw, source):
    result = ContentEngine().ask(raw, materials=[_material(source)])

    assert result["verdict"].startswith("UNKNOWN_CONTENT_")
    assert result["event_set_status"] == "HOLD"
    assert result["goal_satisfied"] is None
    assert result["success_count_eligible"] is False


def test_source_content_is_not_routed_as_a_ready_event_set():
    assert is_content_request("資料の内容をすべて、二文でまとめてください。")
    result = ContentEngine().ask(
        "資料の内容をすべて、二文でまとめてください。", materials=[_material()]
    )
    assert result["verdict"].startswith("UNKNOWN_CONTENT_")
    assert result["raw_goal_projection"]["target_kind"] == "source_content"
    assert result["success_count_eligible"] is False


def test_changed_source_roles_are_read_from_the_supplied_source():
    changed_source = "太郎が花子に資料を渡した。太郎が資料を読んだ。"
    result = ContentEngine().ask(RAW, materials=[_material(changed_source)])

    assert result["verdict"] == "ANSWER"
    first_event = result["source_event_binding"]["events"][0]
    roles = {item["role"]: item["value"] for item in first_event["roles"]}
    assert roles["agent"] == "太郎"
    assert roles["recipient"] == "花子"
    assert result["verification"]["passed"] is True


def test_consumer_rederives_goal_and_ledger_instead_of_trusting_obligations():
    ledger = read_brief(RAW, (_as_source(_material(), 0),))
    plan = build_plan(ledger)
    realization = realize_plan(plan)
    changed = tuple(
        replace(item, number=1) if item.kind == "sentences" else item
        for item in ledger.obligations
    )
    forged = replace(ledger, obligations=changed)

    with pytest.raises(ContentError) as caught:
        verify_content(forged, plan, realization)
    assert caught.value.details["check"] == "event_set_ledger_rederived"

    changed_source = replace(
        ledger.materials[0], text="花子が太郎に資料を渡した。太郎が資料を送った。"
    )
    forged_source = replace(ledger, materials=(changed_source,))
    with pytest.raises(ContentError) as source_caught:
        verify_content(forged_source, plan, realization)
    assert source_caught.value.details["check"] == "event_set_ledger_rederived"


def test_round5_public_route_keeps_the_original_raw_request():
    vera = Vera.from_texts({"memo": SOURCE}, mode="round5")
    try:
        result = vera.ask(RAW)
    finally:
        vera.close()

    assert result["verdict"] == "PARTIAL"
    assert result["component_verdict"] == "ANSWER"
    assert result["status"] == "PARTIAL_COMPLETENESS_UNVERIFIED"
    assert result["door"] == "round5_content"
    assert result["event_set_status"] == "PARTIAL"
    assert result["response_notice"] == "本文は検証済みですが、依頼された出典イベント全体の網羅性は未確認です。"
    assert result["text"] == result["realization"]["text"]
    assert result["success_count_eligible"] is False
    assert any(step.get("content_intent") is True for step in result["trace"])
