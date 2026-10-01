from __future__ import annotations

import hashlib
import json
from dataclasses import replace

import pytest

from verantyx.compositional_goal import evaluate_candidate, produce_goal


DOC = "花子が太郎に資料を渡した。"


def make(raw: str, document: str = DOC):
    return produce_goal({"memo": document}, raw)


def evaluate(draft, raw: str, candidate: str, document: str = DOC):
    return evaluate_candidate(
        draft, candidate, raw_request=raw, documents={"memo": document}
    )


def with_prototype(draft, prototype: str):
    assert draft.source_event is not None
    event = replace(
        draft.source_event,
        prototype=prototype,
        prototype_sha256=hashlib.sha256(prototype.encode("utf-8")).hexdigest(),
    )
    return replace(draft, source_event=event)


def test_composes_raw_action_target_quantity_and_source_policy():
    raw = "資料の出来事を一文で言い換えてください。"
    draft = make(raw)

    assert draft.status == "READY"
    assert draft.query.surface.value == raw
    assert draft.action == "restate"
    assert draft.target == "資料の出来事"
    assert draft.target_kind == "source_event"
    assert draft.quantities == (("exact_sentences", 1),)
    assert draft.source_policy == "one-source-one-assertion-evidence-only"
    assert draft.source_event is not None
    assert draft.ledger.materials[0].family == "document"
    assert draft.ledger.materials[0].purpose == "evidence"
    assert any(item.kind == "source_policy" for item in draft.ledger.obligations)
    assert any(item.kind == "action" and item.value == "restate" for item in draft.ledger.obligations)
    assert any(item.kind == "target" for item in draft.ledger.obligations)
    assert any(item.kind == "exact_sentences" and item.number == 1 for item in draft.ledger.obligations)
    assert draft.frame_evidence.source_text == raw
    assert draft.frame_evidence.source_id == "request"
    assert draft.target_binding.status == "BOUND"
    assert draft.quantity_bindings[0].status == "BOUND"
    assert not draft.hold_reasons


def test_quantity_is_optional_and_absence_is_not_an_unread_slot():
    draft = make("資料の出来事を言い換えてください。")

    assert draft.status == "READY"
    assert draft.quantities == ()
    assert draft.ledger.unread == ()
    result = evaluate(draft, "資料の出来事を言い換えてください。", "資料は花子が太郎に渡した。")
    assert result.status == "PARTIAL"
    assert result.represented_requirements_satisfied is True
    assert result.success_count_eligible is False


def test_word_order_and_politeness_variants_have_same_composed_signature():
    first = make("資料の出来事を一文で言い換えてください。")
    second = make("一文で、資料の出来事を言い換えて下さい。")

    assert first.status == second.status == "READY"
    assert first.semantic_signature == second.semantic_signature


def test_quantity_target_and_prohibition_changes_change_goal_signature():
    base = make("資料の出来事を一文で言い換えてください。")
    two_sentences = make("資料の出来事を二文で言い換えてください。")
    different_target = make("資料の内容を一文で言い換えてください。")
    send_prohibited = make("資料の出来事を送信せずに一文で言い換えてください。")

    assert len({base.semantic_signature, two_sentences.semantic_signature,
                different_target.semantic_signature, send_prohibited.semantic_signature}) == 4
    assert two_sentences.quantities == (("exact_sentences", 2),)
    assert different_target.target_kind == "source_content"
    assert send_prohibited.prohibitions == ()
    assert send_prohibited.unverified_prohibitions == ("send",)
    assert send_prohibited.unverified_prohibition_spans
    assert not any(item.kind in ("prohibited_action", "prohibition_scope")
                   for item in send_prohibited.ledger.obligations)


def test_conflicting_quantities_are_retained_and_held():
    raw = "資料の出来事を一文で二文で言い換えてください。"
    draft = make(raw)

    assert draft.status == "HOLD"
    assert set(draft.quantities) == {("exact_sentences", 1), ("exact_sentences", 2)}
    assert len(draft.ambiguity_spans) >= 2
    assert any("conflict" in reason for reason in draft.hold_reasons)


def test_unverified_negation_is_not_a_confirmed_obligation_and_conflicts_hold():
    safe = make("資料の出来事を送信せずに一文で言い換えてください。")
    conflict = make("資料の出来事を言い換えずに一文で言い換えてください。")

    assert safe.status == "HOLD"
    assert safe.prohibitions == ()
    assert safe.unverified_prohibitions == ("send",)
    assert safe.negation_alignment_status == "RAW_SPANS_MATCH_SCOPE_UNKNOWN"
    assert [safe.ledger.brief.text[s.start:s.end]
            for s in safe.raw_negation_spans] == ["ず"]
    assert any("unverified as an instruction-level prohibition" in reason
               for reason in safe.hold_reasons)
    assert not any(item.kind in ("prohibited_action", "prohibition_scope")
                   for item in safe.ledger.obligations)
    assert conflict.status == "HOLD"
    assert "restate" in conflict.unverified_prohibitions
    assert conflict.prohibitions == ()
    assert any("conflicts with an unverified negative predicate" in reason
               for reason in conflict.hold_reasons)
    assert len(conflict.ambiguity_spans) >= 2


def test_quoted_command_is_data_not_a_user_prohibition_or_action():
    raw = "資料に「送信してください」とある内容を一文で言い換えてください。"
    draft = make(raw)

    assert draft.status == "HOLD"
    assert draft.action == "restate"
    assert draft.prohibitions == ()
    assert len(draft.quote_data) == 1
    assert raw[draft.quote_data[0].start:draft.quote_data[0].end] == "「送信してください」"
    assert any("とある内容" in raw[span.start:span.end] for span in draft.ledger.unread)


def test_wh_role_composition_retains_unread_style_and_readability_spans():
    raw = "資料の一件を、誰が何を誰に預けたか分かるように短く言い換えて。"
    source = "花子が太郎に資料を預けた。"
    draft = make(raw, source)

    assert draft.status == "HOLD"
    assert draft.required_roles == ("agent", "patient", "recipient")
    assert draft.target_predicate == "預ける"
    assert any(item.kind == "required_role" and item.value == "recipient"
               for item in draft.ledger.obligations)
    unread_text = [raw[span.start:span.end] for span in draft.ledger.unread]
    assert any("短く" in span for span in unread_text)
    assert any("分かる" in span for span in unread_text)


def test_limited_projection_and_goal_satisfaction_are_separate():
    raw = "資料の出来事を一文で言い換えてください。"
    draft = make(raw)
    candidate = "資料は花子が太郎に渡した。"
    result = evaluate(draft, raw, candidate)

    assert result.status == "PARTIAL"
    assert result.integrity_status == "verified"
    assert result.limited_projection_equivalent is True
    assert result.full_semantic_equivalent is None
    assert result.represented_requirements_satisfied is True
    assert result.goal_satisfied is None
    assert "topic/focus" in result.unrepresented_semantics
    assert "request_action_target_binding" in result.verified_requirements
    assert "request_quantity_binding" in result.verified_requirements
    assert result.success_count_eligible is False

    swapped_roles = evaluate(draft, raw, "太郎が花子に資料を渡した。")
    assert swapped_roles.status == "EVALUATED"
    assert swapped_roles.limited_projection_equivalent is False
    assert swapped_roles.goal_satisfied is False


def test_valid_prototype_json_and_member_order_variants_remain_verified():
    raw = "資料の出来事を一文で言い換えてください。"
    draft = make(raw)
    candidate = "資料は花子が太郎に渡した。"
    assert json.loads(draft.source_event.prototype)["type"] == "View"

    reordered_value = json.loads(draft.source_event.prototype)

    def reverse_object_members(value):
        if type(value) is dict:
            return {key: reverse_object_members(item)
                    for key, item in reversed(tuple(value.items()))}
        if type(value) is list:
            return [reverse_object_members(item) for item in value]
        return value

    reordered = json.dumps(
        reverse_object_members(reordered_value),
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    result = evaluate(with_prototype(draft, reordered), raw, candidate)

    assert result.integrity_status == "verified"
    assert result.status == "PARTIAL"
    assert result.success_count_eligible is False


def test_only_ingest_ms_remains_an_accepted_prototype_difference():
    raw = "資料の出来事を一文で言い換えてください。"
    draft = make(raw)
    value = json.loads(draft.source_event.prototype)
    value["fields"]["ingest_ms"] += 1.25
    changed = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)

    result = evaluate(with_prototype(draft, changed), raw, "資料は花子が太郎に渡した。")

    assert result.integrity_status == "verified"
    assert result.status == "PARTIAL"
    assert result.success_count_eligible is False


@pytest.mark.parametrize("conflicting_type_order", ("first", "last"))
def test_consumer_rejects_duplicate_json_type_keys_in_either_order(conflicting_type_order):
    raw = "資料の出来事を一文で言い換えてください。"
    draft = make(raw)
    value = json.loads(draft.source_event.prototype)
    encoded_fields = json.dumps(value["fields"], ensure_ascii=False, separators=(",", ":"))
    if conflicting_type_order == "first":
        prototype = '{"type":"Other","fields":' + encoded_fields + ',"type":"View"}'
    else:
        prototype = '{"type":"View","fields":' + encoded_fields + ',"type":"Other"}'

    result = evaluate(
        with_prototype(draft, prototype), raw, "資料は花子が太郎に渡した。"
    )

    assert result.status == "HOLD"
    assert result.integrity_status == "invalid"
    assert result.limited_projection_equivalent is None
    assert result.represented_requirements_satisfied is None
    assert result.success_count_eligible is False


@pytest.mark.parametrize("constant", (float("nan"), float("inf"), float("-inf")))
def test_consumer_rejects_nonfinite_prototype_numbers(constant):
    raw = "資料の出来事を一文で言い換えてください。"
    draft = make(raw)
    value = json.loads(draft.source_event.prototype)
    value["fields"]["ingest_ms"] = constant
    prototype = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=True)

    result = evaluate(
        with_prototype(draft, prototype), raw, "資料は花子が太郎に渡した。"
    )

    assert result.status == "HOLD"
    assert result.integrity_status == "invalid"
    assert result.success_count_eligible is False


@pytest.mark.parametrize("malformation", ("root_fields_list", "ingest_ms_string", "wrong_view_tag"))
def test_consumer_rejects_invalid_prototype_types_at_decode_boundary(malformation):
    raw = "資料の出来事を一文で言い換えてください。"
    draft = make(raw)
    value = json.loads(draft.source_event.prototype)
    if malformation == "root_fields_list":
        value["fields"] = []
    elif malformation == "ingest_ms_string":
        value["fields"]["ingest_ms"] = "5.5"
    else:
        value["type"] = 7
    prototype = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)

    result = evaluate(
        with_prototype(draft, prototype), raw, "資料は花子が太郎に渡した。"
    )

    assert result.status == "HOLD"
    assert result.integrity_status == "invalid"
    assert result.limited_projection_equivalent is None
    assert result.success_count_eligible is False


def test_candidate_fails_at_quantity_check_after_raw_binding_is_verified():
    raw = "資料の出来事を二文で言い換えてください。"
    draft = make(raw)
    result = evaluate(draft, raw, "資料は花子が太郎に渡した。")

    assert result.status == "EVALUATED"
    assert result.limited_projection_equivalent is True
    assert result.represented_requirements_satisfied is False
    assert dict(result.checks)["sentence_quantity"] is False
    assert dict(result.checks)["request_quantity_binding"] is True
    assert result.success_count_eligible is False
    assert result.full_semantic_equivalent is None


def test_explanation_requires_reason_evidence_absent_from_single_event():
    raw = "資料の出来事を一文で説明してください。"
    draft = make(raw)
    result = evaluate(draft, raw, "資料は花子が太郎に渡した。")

    assert draft.status == "HOLD"
    assert draft.action == "explain"
    assert draft.reason_required is True
    assert any(item.kind == "reason_evidence" for item in draft.ledger.obligations)
    assert result.status == "HOLD"
    assert result.limited_projection_equivalent is None
    assert result.represented_requirements_satisfied is None
    assert result.success_count_eligible is False
    assert result.full_semantic_equivalent is None


def test_process_prohibition_cannot_be_certified_from_candidate_text_alone():
    raw = "資料の出来事を送信せずに一文で言い換えてください。"
    draft = make(raw)
    result = evaluate(draft, raw, "資料は花子が太郎に渡した。")

    assert result.status == "HOLD"
    assert result.limited_projection_equivalent is None
    assert result.represented_requirements_satisfied is None
    assert result.goal_satisfied is None
    assert result.success_count_eligible is False


def test_source_input_boundary_requires_one_typed_document():
    with pytest.raises(ValueError):
        produce_goal({"a": DOC, "b": DOC}, "資料の出来事を一文で言い換えてください。")
    with pytest.raises(TypeError):
        produce_goal({"a": 7}, "資料の出来事を一文で言い換えてください.")


def test_legacy_consumer_api_is_unverified_hold_without_raw_inputs():
    draft = make("資料の出来事を一文で言い換えてください。")
    result = evaluate_candidate(draft, "資料は花子が太郎に渡した。")

    assert result.status == "HOLD"
    assert result.integrity_status == "unverified"
    assert result.represented_requirements_satisfied is None
    assert result.success_count_eligible is False
    assert any("legacy API call is unverified" in reason for reason in result.unmet)


@pytest.mark.parametrize(
    "mutation",
    ("quantities", "source_event", "action", "target_kind", "material_purpose"),
)
def test_consumer_rejects_draft_field_tampering_without_partial_success(mutation):
    raw = "資料の出来事を二文で言い換えてください。"
    draft = make(raw)
    if mutation == "quantities":
        tampered = replace(draft, quantities=())
    elif mutation == "source_event":
        other = make(raw, "花子が太郎に手紙を渡した。")
        tampered = replace(draft, source_event=other.source_event)
    elif mutation == "action":
        tampered = replace(draft, action="explain")
    elif mutation == "target_kind":
        tampered = replace(draft, target_kind="source_content")
    else:
        material = replace(draft.ledger.materials[0], purpose="expression")
        ledger = replace(draft.ledger, materials=(material,))
        tampered = replace(draft, ledger=ledger)

    result = evaluate(
        tampered, raw, "資料は花子が太郎に渡した。"
    )

    assert result.status == "HOLD"
    assert result.integrity_status == "invalid"
    assert result.limited_projection_equivalent is None
    assert result.represented_requirements_satisfied is None
    assert result.goal_satisfied is None
    assert result.success_count_eligible is False
    assert result.failed_requirements
    assert any("draft failed producer revalidation" in reason for reason in result.unmet)
    assert "PARTIAL" != result.status


def test_consumer_rejects_raw_request_or_document_rebinding():
    raw = "資料の出来事を一文で言い換えてください。"
    draft = make(raw)

    changed_request = evaluate_candidate(
        draft,
        "資料は花子が太郎に渡した。",
        raw_request="資料の内容を一文で言い換えてください。",
        documents={"memo": DOC},
    )
    changed_source = evaluate_candidate(
        draft,
        "資料は花子が太郎に渡した。",
        raw_request=raw,
        documents={"memo": "花子が太郎に手紙を渡した。"},
    )

    assert changed_request.integrity_status == "invalid"
    assert changed_request.status == "HOLD"
    assert changed_source.integrity_status == "invalid"
    assert changed_source.status == "HOLD"
    assert changed_source.represented_requirements_satisfied is None
    assert changed_source.success_count_eligible is False


def test_malformed_draft_ledger_container_returns_typed_invalid_hold():
    raw = "資料の出来事を一文で言い換えてください。"
    draft = make(raw)
    malformed_ledger = replace(draft.ledger, materials=None)
    malformed = replace(draft, ledger=malformed_ledger)

    result = evaluate(malformed, raw, "資料は花子が太郎に渡した。")

    assert result.status == "HOLD"
    assert result.integrity_status == "invalid"
    assert result.represented_requirements_satisfied is None
    assert result.success_count_eligible is False


@pytest.mark.parametrize(
    "malformed_source_event",
    ("not-an-envelope", {"prototype_sha256": "DO_NOT_ECHO"}, 7, 0, [1], None),
)
def test_invalid_source_event_types_return_typed_invalid_hold_without_repr_leak(
    malformed_source_event,
):
    raw = "資料の出来事を一文で言い換えてください。"
    draft = make(raw)
    malformed = replace(draft, source_event=malformed_source_event)

    result = evaluate(malformed, raw, "資料は花子が太郎に渡した。")

    checks = dict(result.checks)
    evidence = dict(result.evidence)
    assert result.status == "HOLD"
    assert result.integrity_status == "invalid"
    assert result.limited_projection_equivalent is None
    assert result.represented_requirements_satisfied is None
    assert result.goal_satisfied is None
    assert result.success_count_eligible is False
    assert checks["source_event_type_valid"] is (malformed_source_event is None)
    assert evidence["draft_source_event_sha256"] == ""
    assert "DO_NOT_ECHO" not in repr(result)
    assert any("draft.source_event" in reason for reason in result.unmet)


@pytest.mark.parametrize(
    ("raw", "document"),
    (("", DOC), ("資料の出来事を一文で言い換えてください。", ""),
     ("資料の出来事を一文で言い換えてください。", "???")),
)
def test_empty_or_unreadable_request_source_holds_without_exception(raw, document):
    draft = make(raw, document)

    result = evaluate(draft, raw, "資料は花子が太郎に渡した。", document)

    assert draft.status == "HOLD"
    assert result.status == "HOLD"
    assert result.limited_projection_equivalent is None
    assert result.represented_requirements_satisfied is None
    assert result.success_count_eligible is False


def test_source_content_target_is_held_for_unverified_completeness():
    raw = "資料の内容を一文で言い換えてください。"
    draft = make(raw)

    assert draft.target_kind == "source_content"
    assert draft.status == "HOLD"
    assert draft.target_span is not None
    assert any(span.start <= draft.target_span.start and draft.target_span.end <= span.end
               for span in draft.ledger.unread)
    assert not any(item.kind == "target" for item in draft.ledger.obligations)
    assert any("source_content completeness is not verified" in reason
               for reason in draft.hold_reasons)

    result = evaluate(draft, raw, "資料は花子が太郎に渡した。")

    assert result.status == "HOLD"
    assert result.integrity_status == "verified"
    assert result.limited_projection_equivalent is None
    assert result.represented_requirements_satisfied is None
    assert result.success_count_eligible is False


@pytest.mark.parametrize(
    ("raw", "quoted_only"),
    (
        ("資料の出来事を一文で言い換えてください。『送信してください』", False),
        ("資料の出来事を一文で言い換えてください。『二文で送信せず言い換える。別の資料も送る。』", False),
        ("『資料の出来事を二文で送信せず言い換えてください。』", True),
    ),
)
def test_unbound_quote_spans_hold_without_promoting_quoted_commands(raw, quoted_only):
    draft = make(raw)

    assert draft.status == "HOLD"
    assert draft.quote_data
    assert all(any(unread.start <= quote.start and quote.end <= unread.end
                   for unread in draft.ledger.unread)
               for quote in draft.quote_data)
    assert draft.prohibitions == ()
    assert draft.unverified_prohibitions == ()
    if quoted_only:
        assert draft.action == ""
        assert draft.quantities == ()
    else:
        assert draft.action == "restate"
        assert draft.quantities == (("exact_sentences", 1),)

    result = evaluate(draft, raw, "資料は花子が太郎に渡した。")

    assert result.status == "HOLD"
    assert result.integrity_status == "verified"
    assert result.limited_projection_equivalent is None
    assert result.represented_requirements_satisfied is None
    assert result.success_count_eligible is False


def test_quote_free_word_order_variant_still_reaches_limited_partial_result():
    raw = "一文で、資料の出来事を言い換えて下さい。"
    draft = make(raw)
    assert draft.status == "READY"
    assert draft.quote_data == ()

    result = evaluate(draft, raw, "資料は花子が太郎に渡した。")

    assert result.status == "PARTIAL"
    assert result.integrity_status == "verified"
    assert result.represented_requirements_satisfied is True
    assert result.full_semantic_equivalent is None
    assert result.goal_satisfied is None
    assert result.success_count_eligible is False


def test_cross_action_target_borrowing_and_negative_scope_are_held():
    raw = "資料を送信せず手紙を言い換える。"
    draft = make(raw)
    assert draft.status == "HOLD"
    assert draft.target == "手紙"
    assert draft.target != "資料"
    assert draft.target_kind == ""
    assert draft.target_binding.status == "BOUND"
    assert draft.unverified_prohibitions == ("send",)
    assert any("not compositionally linked to the named source" in reason
               for reason in draft.hold_reasons)

    double_negative = make("資料の出来事を送信しないわけではなく一文で言い換えてください。")
    assert double_negative.status == "HOLD"
    assert any("negative construction remains unverified" in reason
               for reason in double_negative.hold_reasons)
