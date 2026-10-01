from __future__ import annotations

from dataclasses import replace

from verantyx.compositional_goal import evaluate_candidate, produce_goal


DOCUMENTS = {"memo": "花子が太郎に資料を渡した。"}


def produce(raw: str):
    return produce_goal(DOCUMENTS, raw)


def evaluate(draft, raw: str, candidate: str = "資料は花子が太郎に渡した。"):
    return evaluate_candidate(
        draft, candidate, raw_request=raw, documents=DOCUMENTS
    )


def test_raw_positive_request_reaches_only_the_represented_candidate_checks():
    raw = "資料の出来事を一文で言い換えてください。"
    draft = produce(raw)

    assert draft.status == "READY"
    assert draft.frame_evidence.source_text == raw
    assert draft.frame_evidence.source_id == "request"
    assert draft.target_binding.status == "BOUND"
    assert draft.target_binding.target == "資料の出来事"
    assert draft.quantity_bindings[0].status == "BOUND"
    assert draft.source_event is not None
    assert draft.source_event.projection.predicate == "渡す"
    assert draft.ledger.materials[0].text == DOCUMENTS["memo"]
    assert draft.frame_evidence.source_text != draft.ledger.materials[0].text

    result = evaluate(draft, raw)
    checks = dict(result.checks)
    assert result.status == "PARTIAL"
    assert result.integrity_status == "verified"
    assert checks["all_draft_fields_rederived"] is True
    assert checks["request_action_target_binding"] is True
    assert checks["request_quantity_binding"] is True
    assert checks["limited_projection_equivalent"] is True
    assert checks["sentence_quantity"] is True
    assert result.represented_requirements_satisfied is True
    assert result.goal_satisfied is None
    assert result.full_semantic_equivalent is None
    assert result.success_count_eligible is False


def test_word_order_and_politeness_change_without_surface_match_gate():
    raw1 = "資料の出来事を一文で言い換えてください。"
    raw2 = "一文で、資料の出来事を言い換えて下さい。"
    first, second = produce(raw1), produce(raw2)

    assert first.status == second.status == "READY"
    assert first.semantic_signature == second.semantic_signature
    assert first.target_binding.argument_span.text == second.target_binding.argument_span.text
    assert evaluate(second, raw2).represented_requirements_satisfied is True


def test_a_target_attached_to_another_action_clause_is_never_borrowed():
    raw = "資料を送信せず手紙を言い換える。"
    draft = produce(raw)

    assert draft.status == "HOLD"
    assert draft.action == "restate"
    assert draft.target == "手紙"
    assert draft.target != "資料"
    assert draft.target_kind == ""
    assert draft.target_binding.status == "BOUND"
    assert "send" in draft.unverified_prohibitions
    assert draft.prohibitions == ()
    assert not any(item.kind in ("prohibited_action", "prohibition_scope")
                   for item in draft.ledger.obligations)
    result = evaluate(draft, raw)
    assert result.integrity_status == "verified"
    assert result.represented_requirements_satisfied is None
    assert dict(result.checks)["producer_ready"] is False
    assert any("producer evidence remains held" in reason for reason in result.unmet)


def test_topic_case_and_quote_scope_remain_unread_or_held():
    topic_raw = "資料の出来事は一文で言い換えてください。"
    topic = produce(topic_raw)
    topic_unread = [topic_raw[span.start:span.end] for span in topic.ledger.unread]
    assert topic.status == "HOLD"
    assert any("は" in text for text in topic_unread)
    assert topic.target_binding is None or topic.target_binding.status == "HOLD"

    quote_raw = "資料の出来事を「送信してください」と一文で言い換えてください。"
    quoted = produce(quote_raw)
    assert quoted.status == "HOLD"
    assert quoted.prohibitions == ()
    assert quoted.unverified_prohibitions == ()
    assert quoted.target_binding is not None
    assert quoted.target_binding.status == "HOLD"
    assert evaluate(quoted, quote_raw).integrity_status == "verified"
    assert evaluate(quoted, quote_raw).represented_requirements_satisfied is None


def test_past_tense_is_not_silently_covered():
    raw = "資料の出来事を一文で言い換えた。"
    draft = produce(raw)
    unread = [raw[span.start:span.end] for span in draft.ledger.unread]

    assert draft.status == "HOLD"
    assert draft.target_binding.status == "HOLD"
    assert any("past-tense action" in reason for reason in draft.hold_reasons)
    assert any("た" in text for text in unread)
    assert evaluate(draft, raw).represented_requirements_satisfied is None


def test_unresolved_conditional_is_retained_as_unread():
    raw = "資料の出来事を一文で言い換えるなら、二文にしてください。"
    draft = produce(raw)
    unread = [raw[span.start:span.end] for span in draft.ledger.unread]

    assert draft.status == "HOLD"
    assert any("なら" in text for text in unread)
    assert any("conditional" in reason or "scope" in reason
               for reason in draft.hold_reasons)
    assert evaluate(draft, raw).represented_requirements_satisfied is None


def test_wh_plus_mo_is_unread_and_not_a_required_recipient():
    raw = "資料の出来事を誰にも送らずに一文で言い換えてください。"
    draft = produce(raw)
    unread = [raw[span.start:span.end] for span in draft.ledger.unread]

    assert draft.status == "HOLD"
    assert draft.required_roles == ()
    assert not any(item.kind == "required_role" and item.value == "recipient"
                   for item in draft.ledger.obligations)
    assert any("誰にも" in span for span in unread)
    assert draft.prohibitions == ()
    assert draft.unverified_prohibitions == ("send",)
    assert draft.unverified_prohibition_spans
    assert [raw[span.start:span.end] for span in draft.raw_negation_spans] == ["ず"]
    assert draft.negation_alignment_status == "RAW_SPANS_MATCH_SCOPE_UNKNOWN"


def test_quantity_change_is_retained_and_candidate_is_rejected_at_quantity_check():
    raw = "資料の出来事を二文で言い換えてください。"
    draft = produce(raw)
    result = evaluate(draft, raw, candidate="資料は花子が太郎に渡した。")

    assert draft.status == "READY"
    assert draft.quantities == (("exact_sentences", 2),)
    assert draft.quantity_bindings[0].status == "BOUND"
    assert result.status == "EVALUATED"
    assert dict(result.checks)["limited_projection_equivalent"] is True
    assert dict(result.checks)["sentence_quantity"] is False
    assert result.represented_requirements_satisfied is False
    assert result.success_count_eligible is False


def test_full_sidecar_and_derived_binding_are_rechecked_before_candidate_scoring():
    raw = "資料の出来事を一文で言い換えてください。"
    draft = produce(raw)
    clause = draft.frame_evidence.clauses[0]
    patient = next(argument for argument in clause.arguments
                   if argument.role == "patient")
    changed_patient = replace(patient, permitted=False)
    changed_clause = replace(
        clause,
        arguments=tuple(changed_patient if argument is patient else argument
                        for argument in clause.arguments),
    )
    tampered_sidecar = replace(
        draft.frame_evidence,
        clauses=(changed_clause,) + draft.frame_evidence.clauses[1:],
    )
    tampered = replace(draft, frame_evidence=tampered_sidecar)
    result = evaluate(tampered, raw)

    assert result.status == "HOLD"
    assert result.integrity_status == "invalid"
    assert result.limited_projection_equivalent is None
    assert result.represented_requirements_satisfied is None
    assert result.success_count_eligible is False
    assert any("frame_evidence" in path for path in result.unverified_requirements)


def test_nul_suffix_unknown_coverage_is_held_with_raw_span_retained():
    raw = "資料の出来事を一文で言い換えてください。\x00"
    draft = produce(raw)
    unread = [raw[span.start:span.end] for span in draft.ledger.unread]

    assert draft.status == "HOLD"
    assert draft.target_binding.status == "HOLD"
    assert any("\x00" in span for span in unread)
    assert evaluate(draft, raw).limited_projection_equivalent is None
