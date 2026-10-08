from __future__ import annotations

import json

import pytest

from verantyx.semantic_ir import Clause, Role, Span, Variable, View
from verantyx.semantic_unknown import unknown_candidates


def _clause(
    source: str,
    text: str,
    *,
    clause_id: str = "c1",
    actor: str = "Alice",
    predicate: str = "likes",
    patient: str = "cats",
    polarity: str = "+",
    time: str = "",
) -> Clause:
    source_span = Span(source, 0, len(text), text)
    pred_start = text.index(predicate)
    actor_start = text.index(actor)
    patient_start = text.index(patient)
    return Clause(
        id=clause_id,
        event=Variable(f"event:{clause_id}"),
        predicate=predicate,
        predicate_span=Span(
            source, pred_start, pred_start + len(predicate), predicate
        ),
        roles=(
            Role(
                "actor", actor,
                Span(source, actor_start, actor_start + len(actor), actor),
            ),
            Role(
                "patient", patient,
                Span(source, patient_start,
                     patient_start + len(patient), patient),
            ),
        ),
        span=source_span,
        polarity=polarity,
        time=time,
    )


def _view(
    text: str = "Alice likes cats",
    *,
    polarity: str = "+",
) -> View:
    return View(
        {"s1": text},
        (_clause("s1", text, polarity=polarity),),
    )


def _assert_candidate_is_constructed_only(report) -> None:
    assert report.status == "CANDIDATES"
    assert report.candidates
    for candidate in report.candidates:
        assert candidate.kind in {
            "EXPLAINED_BY_UNITS", "KIN_NEIGHBOURHOOD", "NO_REACH",
        }
        assert candidate.constructed is True
        assert candidate.evidence is False
        assert candidate.term == report.term


def test_non_string_term_is_rejected() -> None:
    with pytest.raises(TypeError, match="term must be a string"):
        unknown_candidates(_view(), None)  # type: ignore[arg-type]


def test_exact_role_term_is_reported_known_without_candidates() -> None:
    report = unknown_candidates(_view(), "Alice")

    assert report.status == "KNOWN_TERM"
    assert report.candidates == ()


def test_exact_predicate_is_reported_known_without_candidates() -> None:
    report = unknown_candidates(_view(), "likes")

    assert report.status == "KNOWN_TERM"
    assert report.candidates == ()


def test_invalid_and_zero_budgets_are_typed_refusals() -> None:
    for budget in (0, -1, True, 1.5):
        report = unknown_candidates(_view(), "Alicecats", budget=budget)
        assert report.status == "BUDGET_REFUSAL"
        assert report.candidates == ()


def test_budget_below_clause_and_role_work_floor_refuses() -> None:
    # One clause, two roles, and the fixed unit of work already exceed 3.
    report = unknown_candidates(_view(), "Alicecats", budget=3)

    assert report.status == "BUDGET_REFUSAL"
    assert report.candidates == ()


def test_constructed_neighbour_candidate_is_not_answer_or_evidence() -> None:
    report = unknown_candidates(_view(), "Alicecats")

    _assert_candidate_is_constructed_only(report)
    assert all(candidate.kind == "KIN_NEIGHBOURHOOD"
               for candidate in report.candidates)
    payload = json.loads(report.to_json())
    assert "answer" not in payload
    assert all(candidate["constructed"] is True
               and candidate["evidence"] is False
               for candidate in payload["candidates"])
    assert all("answer" not in candidate for candidate in payload["candidates"])


def test_each_candidate_unit_has_exact_in_clause_source_provenance() -> None:
    view = _view()
    report = unknown_candidates(view, "Alicecats")
    _assert_candidate_is_constructed_only(report)

    clause_by_id = {clause.id: clause for clause in view.clauses}
    for candidate in report.candidates:
        assert tuple(item.unit for item in candidate.provenance) == candidate.units
        for item in candidate.provenance:
            assert item.clauses
            for location in item.clauses:
                span = location.span
                clause = clause_by_id[location.clause_id]
                clause_span = clause.span
                assert span.text == item.unit
                assert view.sources[span.source][span.start:span.end] == item.unit
                assert clause_span.source == span.source
                assert clause_span.start <= span.start < span.end <= clause_span.end


def test_reversed_entity_order_is_not_mistaken_for_a_held_term() -> None:
    report = unknown_candidates(_view(), "catsAlice")

    assert report.status != "KNOWN_TERM"
    if report.status == "CANDIDATES":
        _assert_candidate_is_constructed_only(report)


def test_negative_clause_does_not_make_a_candidate_testimony() -> None:
    report = unknown_candidates(_view(polarity="-"), "Alicecats")

    _assert_candidate_is_constructed_only(report)
    assert all(candidate.evidence is False for candidate in report.candidates)


def test_conflicting_clause_polarities_do_not_promote_a_candidate_to_answer() -> None:
    first = "Alice likes cats"
    second = "Alice likes cats"
    view = View(
        {"old": first, "new": second},
        (
            _clause("old", first, clause_id="old", polarity="+",
                    time="earlier"),
            _clause("new", second, clause_id="new", polarity="-",
                    time="later"),
        ),
    )
    report = unknown_candidates(view, "Alicecats")

    assert report.status != "KNOWN_TERM"
    if report.status == "CANDIDATES":
        _assert_candidate_is_constructed_only(report)
