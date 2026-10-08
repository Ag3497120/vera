from __future__ import annotations

from verantyx.multigrain_source_binding import bind_request_event_set


RAW = "資料の出来事をすべて、二文でまとめてください。"


def test_all_explicit_target_events_bind_to_distinct_source_spans_in_order():
    source = "花子が太郎に資料を渡した。太郎が資料を読んだ。"
    result = bind_request_event_set(RAW, {"memo": source})

    assert result.status == "BOUND"
    assert result.source_id == "memo"
    assert result.target_anchor == "資料"
    assert result.explicit_anchor_occurrence_count == 2
    assert len(result.events) == 2
    assert [event.predicate for event in result.events] == ["渡す", "読む"]
    assert [event.clause_text for event in result.events] == [
        "花子が太郎に資料を渡した。", "太郎が資料を読んだ。"
    ]
    assert [event.clause_span for event in result.events] == [(0, 13), (13, 23)]
    assert all(event.assertion_status == "UNCLASSIFIED" for event in result.events)
    public = result.as_dict()
    assert public["explicit_anchor_coverage"] == "COMPLETE_FOR_LITERAL_OCCURRENCES"
    assert public["semantic_event_set_complete"] is None
    assert public["source_truth_status"] == "UNCLASSIFIED; no truth or authority claim"
    assert public["goal_satisfied"] is None
    assert public["success_count_eligible"] is False


def test_one_matching_event_is_not_promoted_to_an_event_set():
    result = bind_request_event_set(RAW, {"memo": "花子が太郎に資料を渡した。"})

    assert result.status == "HOLD"
    assert not result.events
    assert "fewer than two" in result.reason


def test_every_literal_anchor_occurrence_must_have_a_local_case_owner():
    source = "花子が太郎に資料を渡した。資料について。"
    result = bind_request_event_set(RAW, {"memo": source})

    assert result.status == "HOLD"
    assert not result.events
    assert "owner" in result.reason or "permitted" in result.reason


def test_quoted_or_negative_source_event_is_not_selected_as_positive_evidence():
    quoted = bind_request_event_set(
        RAW, {"memo": "花子が『資料』を渡した。太郎が資料を読んだ。"}
    )
    negative = bind_request_event_set(
        RAW, {"memo": "花子は資料を渡さなかった。太郎が資料を読んだ。"}
    )

    for result in (quoted, negative):
        assert result.status == "HOLD"
        assert not result.events


def test_source_content_request_and_multi_document_inputs_hold():
    source_content = bind_request_event_set(
        "資料の内容をすべて、二文でまとめてください。",
        {"memo": "花子が太郎に資料を渡した。太郎が資料を読んだ。"},
    )
    multiple_documents = bind_request_event_set(
        RAW,
        {"a": "花子が太郎に資料を渡した。", "b": "太郎が資料を読んだ。"},
    )

    assert source_content.status == "HOLD"
    assert multiple_documents.status == "HOLD"
