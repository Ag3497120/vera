from dataclasses import replace

import pytest

from verantyx.semantic_ir import Span
from verantyx.semantic_reader import document_view
from verantyx.semantic_verify import Rejected, license_clause


def _view(text):
    return document_view({"lead": text})


def _with_clause(view, clause):
    return replace(
        view,
        clauses=tuple(clause if item.id == clause.id else item for item in view.clauses),
    )


def test_identity_clause_is_licensed_against_its_sentence():
    text = "東京は日本の首都です。"
    view = _view(text)

    assert not view.invalid
    assert len(view.clauses) == 1
    clause = view.clauses[0]
    assert clause.rule == "copula"
    assert clause.predicate == "identity"
    assert clause.span.text == text
    assert {(role.name, role.span.text) for role in clause.roles} == {
        ("entity", "東京"),
        ("value", "日本の首都"),
    }
    license_clause(clause, view)


def test_event_clause_licenses_source_roles_and_past_tense():
    text = "太郎は公園を歩いた。"
    view = _view(text)

    assert len(view.clauses) == 1
    clause = view.clauses[0]
    assert clause.rule == "frame"
    assert clause.time == "past"
    assert {role.name: role.span.text for role in clause.roles} == {
        "agent": "太郎",
        "patient": "公園",
    }
    license_clause(clause, view)


def test_negative_event_keeps_negative_polarity_when_licensed():
    text = "太郎は公園を歩かなかった。"
    view = _view(text)

    assert len(view.clauses) == 1
    clause = view.clauses[0]
    assert clause.polarity == "-"
    assert clause.time == "past"
    license_clause(clause, view)


def test_separate_identity_sentences_keep_independent_full_spans():
    text = "東京は日本の首都です。大阪は日本の都市です。"
    view = _view(text)

    assert len(view.clauses) == 2
    assert [clause.span.text for clause in view.clauses] == [
        "東京は日本の首都です。",
        "大阪は日本の都市です。",
    ]
    for clause in view.clauses:
        license_clause(clause, view)


def test_interrogative_identity_is_not_licensed_as_an_assertion():
    view = _view("東京は日本の首都ですか？")

    assert not view.invalid
    assert not view.clauses


def test_rejects_role_term_not_literal_in_its_source_span():
    view = _view("東京は日本の首都です。")
    clause = view.clauses[0]
    value = next(role for role in clause.roles if role.name == "value")
    forged = replace(
        clause,
        roles=tuple(
            replace(role, term="日本の都市") if role.name == "value" else role
            for role in clause.roles
        ),
    )

    with pytest.raises(Rejected, match="role/value licensing"):
        license_clause(forged, _with_clause(view, forged))


def test_rejects_role_span_that_does_not_cover_the_copula_value():
    text = "東京は日本の首都です。"
    view = _view(text)
    clause = view.clauses[0]
    value = next(role for role in clause.roles if role.name == "value")
    span = Span(value.span.source, value.span.start, value.span.end - 1,
                text[value.span.start:value.span.end - 1])
    shortened = replace(value, term=span.text, span=span)
    forged = replace(
        clause,
        roles=tuple(shortened if role.name == "value" else role for role in clause.roles),
    )

    with pytest.raises(Rejected, match="copula argument assignment"):
        license_clause(forged, _with_clause(view, forged))


def test_rejects_clause_span_that_drops_sentence_punctuation():
    text = "東京は日本の首都です。"
    view = _view(text)
    clause = view.clauses[0]
    shortened = Span(clause.span.source, clause.span.start, clause.span.end - 1,
                     text[clause.span.start:clause.span.end - 1])
    forged = replace(clause, span=shortened, body_span=shortened)

    with pytest.raises(Rejected, match="copula full-clause boundary"):
        license_clause(forged, _with_clause(view, forged))


def test_rejects_body_span_that_omits_source_punctuation():
    text = "東京は日本の首都です。"
    view = _view(text)
    clause = view.clauses[0]
    shortened = Span(clause.body_span.source, clause.body_span.start,
                     clause.body_span.end - 1,
                     text[clause.body_span.start:clause.body_span.end - 1])
    forged = replace(clause, body_span=shortened)

    with pytest.raises(Rejected, match="native body boundary"):
        license_clause(forged, _with_clause(view, forged))


def test_rejects_clause_spans_after_the_original_source_changes():
    text = "東京は日本の首都です。"
    view = _view(text)
    changed = replace(view, sources={"lead": "東京は日本の都市です。"})

    with pytest.raises(Rejected, match="source span mismatch"):
        license_clause(view.clauses[0], changed)
