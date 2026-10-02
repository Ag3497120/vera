from __future__ import annotations

from verantyx.compositional_goal import derive_request_selection_projection


def test_action_text_is_excluded_and_local_event_target_drives_selector():
    raw = "資料の出来事を言い換えてください。"
    projection = derive_request_selection_projection(raw)

    assert projection.status == "READY"
    assert projection.action == "restate"
    assert projection.target == "資料の出来事"
    assert projection.target_kind == "source_event"
    assert raw[projection.target_span.start:projection.target_span.end] == projection.target
    assert projection.query_terms == ("資料",)
    assert projection.selector_query == "資料"
    assert "言い" not in projection.query_terms
    assert "換" not in projection.query_terms


def test_quantity_and_politeness_variant_keeps_same_target_projection():
    projection = derive_request_selection_projection(
        "一文で、資料の出来事を言い換えて下さい。"
    )

    assert projection.status == "READY"
    assert projection.query_terms == ("資料",)
    assert projection.selector_query == "資料"


def test_source_content_target_is_held_instead_of_downgraded_to_event():
    projection = derive_request_selection_projection(
        "資料の内容を言い換えてください。"
    )

    assert projection.status == "HOLD"
    assert projection.target_kind == "source_content"
    assert projection.selector_query == ""
    assert projection.query_terms == ()


def test_quoted_instruction_and_negative_action_are_not_selector_authority():
    quoted = derive_request_selection_projection(
        "資料の出来事を言い換えてください。『送信してください』"
    )
    negative = derive_request_selection_projection(
        "資料の出来事を送信せずに言い換えてください。"
    )

    assert quoted.status == "HOLD"
    assert quoted.selector_query == ""
    assert quoted.unread_spans
    assert negative.status == "HOLD"
    assert negative.selector_query == ""
    assert negative.unread_spans
