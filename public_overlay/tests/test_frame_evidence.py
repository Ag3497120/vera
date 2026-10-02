"""Small synthetic counterexamples for the Frame evidence sidecar."""

import pytest

from verantyx.frame_evidence import read_frame_evidence


def _role(clause, name):
    return next(arg for arg in clause.arguments if arg.role == name)


def test_repeated_lexeme_keeps_clause_owner_and_exact_particle_spans():
    raw = "葵が赤鍵を持ち、葵が青鍵を置いた。"
    doc = read_frame_evidence("repeat", raw)

    assert doc.source_text == raw
    assert doc.token_offsets_complete
    assert doc.alignment_status == "ALIGNED_BY_READER_ORDER"
    assert len(doc.clauses) == 2
    first, second = doc.clauses
    assert first.clause_id != second.clause_id
    assert first.frame_id != second.frame_id
    assert first.frame.agent == second.frame.agent == "葵"

    first_agent = _role(first, "agent")
    second_agent = _role(second, "agent")
    assert first_agent.owner_frame_id == first.frame_id
    assert second_agent.owner_frame_id == second.frame_id
    assert first_agent.span.text == second_agent.span.text == "葵"
    assert first_agent.span.start < second_agent.span.start
    assert raw[first_agent.span.start:first_agent.span.end] == "葵"
    assert raw[second_agent.span.start:second_agent.span.end] == "葵"
    assert first_agent.case_particle == second_agent.case_particle == "が"
    assert raw[first_agent.particle_span.start:first_agent.particle_span.end] == "が"
    assert raw[second_agent.particle_span.start:second_agent.particle_span.end] == "が"
    # The span check keeps the particle; it does not claim it has been covered
    # away or remove it from the original source.
    assert raw[first_agent.span.start:first_agent.particle_span.end] == "葵が"
    assert raw[second_agent.span.start:second_agent.particle_span.end] == "葵が"
    assert first_agent.origin == second_agent.origin == "EXPLICIT_CASE"
    assert first_agent.permitted and second_agent.permitted


def test_negative_auxiliary_scope_is_exact_and_other_clause_argument_stays_omitted():
    raw = "葵が赤鍵を送信せず、青鍵を保存した。"
    doc = read_frame_evidence("negative-and-omission", raw)
    first, second = doc.clauses

    assert first.frame.predicate == "送信する"
    assert first.predicate_span.text == "送信せ"
    assert first.negation_spans[0].text == "ず"
    assert first.scope_span.text == "送信せず"
    assert first.polarity == "NEGATIVE"
    assert first.scope_status == "KNOWN"
    assert _role(first, "agent").value == "葵"
    assert _role(first, "patient").value == "赤鍵"

    assert second.frame.predicate == "保存する"
    assert second.frame.agent == ""
    assert second.frame.patient == "青鍵"
    missing_agent = _role(second, "agent")
    assert missing_agent.origin == "OMITTED"
    assert missing_agent.value == ""
    assert missing_agent.span is None
    assert not missing_agent.permitted
    assert not any(arg.value == "葵" and arg.role == "agent"
                   for arg in second.arguments)


def test_topic_reuse_is_explicitly_held_as_cross_clause_borrowing():
    raw = "葵は赤鍵を送り、保存した。"
    doc = read_frame_evidence("topic", raw)
    first, second = doc.clauses

    first_agent = _role(first, "agent")
    assert first_agent.origin == "TOPIC_INFERENCE"
    assert not first_agent.permitted
    assert first_agent.span.text == "葵"

    carried_agent = _role(second, "agent")
    assert carried_agent.value == "葵"
    assert carried_agent.origin == "INTERCLAUSE_BORROW"
    assert carried_agent.owner_frame_id == second.frame_id
    assert carried_agent.source_frame_id == first.frame_id
    assert carried_agent.span.text == "葵"
    assert not carried_agent.permitted
    assert "held" in carried_agent.evidence


def test_quoted_predicate_is_not_labeled_as_an_assertion():
    raw = "彼は「葵が赤鍵を送った」と述べた。"
    doc = read_frame_evidence("quoted", raw)
    quoted, reporting = doc.clauses

    assert quoted.predicate == "送る"
    assert quoted.quote_status == "QUOTED"
    assert quoted.assertion_status == "QUOTED"
    assert quoted.local_polarity == "POSITIVE"
    assert quoted.polarity == "UNKNOWN"
    assert quoted.scope_status == "UNKNOWN"
    assert quoted.quote_span.text == "「葵が赤鍵を送った」"
    assert all(not arg.permitted for arg in quoted.arguments)
    assert reporting.quote_status == "UNQUOTED"
    assert reporting.assertion_status == "UNCLASSIFIED"


def test_cleft_focus_keeps_its_source_cue_but_stays_inferred_and_held():
    raw = "赤鍵を送ったのは葵だ。"
    clause = read_frame_evidence("cleft", raw).clauses[0]
    agent = _role(clause, "agent")

    assert clause.frame.agent == "葵"
    assert agent.value == "葵"
    assert agent.span.text == "葵"
    assert agent.case_particle == "のは"
    assert agent.particle_span.text == "のは"
    assert raw[agent.particle_span.start:agent.particle_span.end] == "のは"
    assert agent.origin == "CLEFT_FOCUS_INFERENCE"
    assert not agent.permitted


@pytest.mark.parametrize("raw", [
    "葵が赤鍵を送らなくはない。",          # two negatives in one auxiliary chain
    "葵が赤鍵を送らないわけではない。",      # second negative outside Frame's chain
])
def test_double_negative_scope_is_unknown_and_held(raw):
    clause = read_frame_evidence("double-negative", raw).clauses[0]

    assert clause.frame.negated is True  # the old Frame bool cannot express this
    assert clause.polarity == "UNKNOWN"
    assert clause.scope_status == "UNKNOWN"
    assert clause.scope_span is None
    assert clause.negation_spans
    assert all(not arg.permitted for arg in clause.arguments)


def test_missing_explicit_argument_does_not_borrow_same_lexeme_from_prior_action():
    raw = "葵が赤鍵を送り、保存した。"
    first, second = read_frame_evidence("no-borrow", raw).clauses

    assert _role(first, "agent").value == "葵"
    assert second.frame.agent == ""
    assert _role(second, "agent").origin == "OMITTED"
    assert all(arg.owner_frame_id == second.frame_id for arg in second.arguments)
    assert not any(arg.value == "赤鍵" and arg.role == "patient"
                   for arg in second.arguments)


@pytest.mark.parametrize("raw,lexeme", [
    ("葵が、葵が赤鍵を送った。", "葵"),
    ("花子が花子が資料を渡した。", "花子"),
    ("葵は葵が赤鍵を送った。", "葵"),
])
def test_duplicate_same_owner_role_mentions_are_all_explicitly_ambiguous(raw, lexeme):
    clause = read_frame_evidence("duplicate-owner", raw).clauses[0]
    candidates = [arg for arg in clause.arguments
                  if arg.role == "agent" and arg.value == lexeme]

    assert clause.frame.agent == lexeme
    assert len(candidates) == 2
    assert len({arg.owner_frame_id for arg in candidates}) == 1
    assert all(arg.binding_status == "AMBIGUOUS" for arg in candidates)
    assert all(not arg.permitted for arg in candidates)
    assert all(raw[arg.span.start:arg.particle_span.end]
               == lexeme + arg.case_particle
               for arg in candidates)
    assert all("multiple same-clause" in arg.evidence for arg in candidates)


@pytest.mark.parametrize("raw,agent,patient", [
    ("葵が赤鍵を送った。", "葵", "赤鍵"),
    ("赤鍵を葵が送った。", "葵", "赤鍵"),
    ("花子が資料を渡した。", "花子", "資料"),
    ("資料を花子が渡した。", "花子", "資料"),
])
def test_unique_role_mentions_remain_unique_under_lexical_and_order_changes(
        raw, agent, patient):
    clause = read_frame_evidence("unique-owner", raw).clauses[0]
    agent_arg = _role(clause, "agent")
    patient_arg = _role(clause, "patient")

    assert (clause.frame.agent, clause.frame.patient) == (agent, patient)
    assert agent_arg.value == agent and patient_arg.value == patient
    assert agent_arg.binding_status == patient_arg.binding_status == "UNIQUE"
    assert agent_arg.permitted and patient_arg.permitted
    assert clause.assertion_status == "UNCLASSIFIED"


def test_whitespace_gaps_are_preserved_and_not_confused_with_token_position_status():
    raw = " 葵 が 赤鍵 を 送った。 "
    doc = read_frame_evidence("whitespace-gaps", raw)

    assert doc.token_positions_complete
    assert doc.token_offsets_complete  # deprecated r1 alias
    assert doc.source_coverage_status == "WHITESPACE_ONLY"
    assert doc.source_gaps
    assert all(gap.classification == "WHITESPACE" for gap in doc.source_gaps)
    assert all(gap.span is not None and gap.span.text.isspace()
               for gap in doc.source_gaps)
    pieces = [(token.span.start, token.span.end) for token in doc.tokens
              if token.span is not None]
    pieces.extend((gap.span.start, gap.span.end) for gap in doc.source_gaps
                  if gap.span is not None)
    cursor = 0
    for start, end in sorted(pieces):
        assert start == cursor
        cursor = end
    assert cursor == len(raw)
    assert doc.alignment_status == "ALIGNED_BY_READER_ORDER"
    assert all(arg.permitted for arg in doc.clauses[0].arguments
               if arg.value and arg.origin == "EXPLICIT_CASE")
    payload = doc.as_dict()
    assert "token_positions_complete" in payload
    assert "token_offsets_complete" not in payload


def test_unread_nul_suffix_is_a_source_gap_and_holds_alignment_scope_and_roles():
    raw = "花子が資料を渡し\x00た。"
    doc = read_frame_evidence("nul-suffix", raw)
    gap = next(gap for gap in doc.source_gaps
               if gap.classification == "UNKNOWN_NONWHITESPACE")
    clause = doc.clauses[0]

    assert doc.token_positions_complete  # all emitted tokens got offsets
    assert doc.reader_order_alignment_status == "ALIGNED_BY_READER_ORDER"
    assert doc.alignment_status == "UNKNOWN_SOURCE_COVERAGE"
    assert doc.source_coverage_status == "UNKNOWN_NONWHITESPACE"
    assert gap.span is not None
    assert gap.span.text == raw[gap.span.start:gap.span.end] == "\x00た。"
    token_and_gap_pieces = [(token.span.start, token.span.end)
                            for token in doc.tokens if token.span is not None]
    token_and_gap_pieces.extend((item.span.start, item.span.end)
                                for item in doc.source_gaps if item.span is not None)
    cursor = 0
    for start, end in sorted(token_and_gap_pieces):
        assert start == cursor
        cursor = end
    assert cursor == len(raw)
    assert clause.alignment_status == "UNKNOWN_SOURCE_COVERAGE"
    assert clause.source_coverage_status == "UNKNOWN_NONWHITESPACE"
    assert clause.polarity == "UNKNOWN"
    assert clause.local_polarity == "UNKNOWN"
    assert clause.scope_status == clause.local_scope_status == "UNKNOWN"
    assert all(not arg.permitted for arg in clause.arguments)
    assert all(arg.binding_status == "UNKNOWN" for arg in clause.arguments
               if arg.origin == "EXPLICIT_CASE")


def test_argument_and_case_quote_scopes_are_checked_independently_from_predicate():
    raw = "「花子が」資料を太郎に渡した。"
    clause = read_frame_evidence("quoted-argument", raw).clauses[0]
    agent = _role(clause, "agent")
    patient = _role(clause, "patient")

    assert clause.quote_status == "UNQUOTED"
    assert clause.assertion_status == "UNCLASSIFIED"
    assert agent.argument_quote_status == "QUOTED"
    assert agent.case_quote_status == "QUOTED"
    assert agent.binding_quote_status == "CROSSES_QUOTE_SCOPE"
    assert not agent.permitted
    assert patient.argument_quote_status == "UNQUOTED"
    assert patient.case_quote_status == "UNQUOTED"
    assert patient.binding_quote_status == "UNQUOTED"
    assert patient.permitted


def test_quoted_patient_duplicate_keeps_both_candidates_held():
    raw = "「資料を」花子が資料を渡した。"
    clause = read_frame_evidence("quoted-duplicate-patient", raw).clauses[0]
    patients = [arg for arg in clause.arguments
                if arg.role == "patient" and arg.value == "資料"]

    assert len(patients) == 2
    assert all(arg.binding_status == "AMBIGUOUS" for arg in patients)
    assert all(not arg.permitted for arg in patients)
    assert {arg.binding_quote_status for arg in patients} == {
        "CROSSES_QUOTE_SCOPE", "UNQUOTED"
    }


@pytest.mark.parametrize("raw,subject,object_", [
    ("花子は資料を送信しないとは言わなかった。", "花子", "資料"),
    ("資料を花子は送信しないとは言わなかった。", "花子", "資料"),
    ("太郎は書類を送信しないとは言わなかった。", "太郎", "書類"),
])
def test_embedded_negation_separates_local_morphology_from_proposition_scope(
        raw, subject, object_):
    embedded, matrix = read_frame_evidence("embedded-negation", raw).clauses
    patient = _role(embedded, "patient")

    assert embedded.frame.agent == subject
    assert embedded.frame.patient == object_
    assert embedded.local_polarity == "NEGATIVE"
    assert embedded.local_scope_status == "KNOWN"
    assert embedded.local_scope_span.text == "送信しない"
    assert embedded.polarity == "UNKNOWN"
    assert embedded.scope_status == "UNKNOWN"
    assert embedded.scope_span is None
    assert embedded.scope_reason == "COMPLEMENT_OR_EMBEDDING_SCOPE_UNRESOLVED"
    assert not patient.permitted
    assert matrix.predicate == "言う"
    assert matrix.local_polarity == matrix.polarity == "NEGATIVE"
    assert matrix.scope_status == "KNOWN"


@pytest.mark.parametrize("raw", [
    "花子は資料を送信しなかった。",
    "太郎は書類を送信しなかった。",
])
def test_unembedded_negative_control_retains_separate_known_local_and_proposition_scope(raw):
    clause = read_frame_evidence("unembedded-negative", raw).clauses[0]

    assert clause.local_polarity == clause.polarity == "NEGATIVE"
    assert clause.local_scope_status == clause.scope_status == "KNOWN"
    assert clause.local_scope_span == clause.scope_span
    assert clause.scope_reason == "UNEMBEDDED_LOCAL_SCOPE"


def test_nonfinal_relative_clause_keeps_local_morphology_but_holds_proposition_scope():
    relative, matrix = read_frame_evidence(
        "relative-scope", "花子が資料を送った人を見た。").clauses

    assert relative.local_polarity == "POSITIVE"
    assert relative.local_scope_status == "KNOWN"
    assert relative.polarity == "UNKNOWN"
    assert relative.scope_status == "UNKNOWN"
    assert relative.scope_reason == "NONFINAL_CLAUSE_SCOPE_UNRESOLVED"
    assert matrix.scope_status == "KNOWN"


def test_topic_borrow_source_owner_is_only_an_order_hypothesis():
    first, second = read_frame_evidence(
        "topic-order-hypothesis", "葵は赤鍵を送り、保存した。").clauses
    carried = _role(second, "agent")

    assert carried.owner_frame_id == second.frame_id
    assert carried.source_frame_id == first.frame_id
    assert carried.source_owner_status == "ORDER_HYPOTHESIS"
    assert carried.binding_status == "INFERRED"
    assert not carried.permitted
