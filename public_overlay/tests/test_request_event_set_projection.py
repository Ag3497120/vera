from __future__ import annotations

from verantyx.compositional_goal import (
    derive_request_event_set_projection,
    derive_request_selection_projection,
)


RAW = "資料の出来事をすべて、二文でまとめてください。"


def test_all_event_summary_binds_target_scope_and_exact_output_quantity():
    projection = derive_request_event_set_projection(RAW)

    assert projection.status == "READY"
    assert projection.action == "summarize_events"
    assert projection.target == "資料の出来事"
    assert projection.target_kind == "source_event"
    assert projection.selector_query == "資料"
    assert projection.query_terms == ("資料",)
    assert projection.selection_scope == "all_matching_events"
    assert projection.event_scope_span is not None
    assert RAW[projection.event_scope_span.start:projection.event_scope_span.end] == "すべて"
    assert projection.required_sentence_count == 2
    assert projection.as_dict()["selection_scope"] == "all_matching_events"


def test_source_content_scope_is_held_and_not_downgraded_to_event_set():
    projection = derive_request_event_set_projection(
        "資料の内容をすべて二文でまとめてください。"
    )

    assert projection.status == "HOLD"
    assert projection.target_kind == "source_content"
    assert projection.selector_query == ""


def test_summary_without_explicit_all_scope_is_held():
    projection = derive_request_event_set_projection(
        "資料の出来事を二文でまとめてください。"
    )

    assert projection.status == "HOLD"
    assert projection.selector_query == ""
    assert projection.selection_scope == "all_matching_events"


def test_unseparated_scope_and_quantity_stay_held_with_the_unread_span():
    projection = derive_request_event_set_projection(
        "資料の出来事をすべて二文でまとめてください。"
    )

    assert projection.status == "HOLD"
    assert projection.selector_query == ""
    assert projection.unread_spans


def test_wrong_output_quantity_quote_or_negation_is_held():
    wrong_quantity = derive_request_event_set_projection(
        "資料の出来事をすべて一文でまとめてください。"
    )
    quote = derive_request_event_set_projection(
        "資料の出来事をすべて二文でまとめてください。『送信してください』"
    )
    negative = derive_request_event_set_projection(
        "資料の出来事をすべて二文でまとめずにください。"
    )

    for projection in (wrong_quantity, quote, negative):
        assert projection.status == "HOLD"
        assert projection.selector_query == ""
        assert projection.unread_spans or projection.reason


def test_event_set_marker_does_not_widen_single_event_projection():
    projection = derive_request_selection_projection(RAW)

    assert projection.status == "HOLD"
    assert projection.selection_scope == "single_event"
    assert projection.selector_query == ""
