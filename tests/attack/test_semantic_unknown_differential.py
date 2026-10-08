"""Independent checks for the public, locally checkable unknown-term rules."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from verantyx.semantic_unknown import unknown_candidates


@dataclass(frozen=True)
class _Span:
    source: str
    start: int
    end: int
    text: str

    def valid(self, sources: dict[str, str]) -> bool:
        raw = sources.get(self.source)
        return (raw is not None and 0 <= self.start <= self.end <= len(raw)
                and raw[self.start:self.end] == self.text)


@dataclass(frozen=True)
class _Role:
    term: str
    span: _Span


@dataclass(frozen=True)
class _Clause:
    id: str
    predicate: str
    span: _Span
    roles: tuple[_Role, ...]


@dataclass(frozen=True)
class _View:
    sources: dict[str, str]
    clauses: tuple[_Clause, ...]


def _view(
    sources: dict[str, str] | None = None,
    *,
    roles: tuple[str, ...] = (),
    predicate: str = "",
) -> _View:
    source_map = dict(sources or {})
    if not source_map and (roles or predicate):
        source_map["s"] = " ".join((*roles, predicate)).strip()
    if not roles and not predicate:
        return _View(source_map, ())
    source = next(iter(source_map))
    raw = source_map[source]
    span = _Span(source, 0, len(raw), raw)
    clause = _Clause("c0", predicate, span,
                     tuple(_Role(term, span) for term in roles))
    return _View(source_map, (clause,))


def _naive_early_result(view: _View, term: object, budget: object):
    """Reference only the public pre-explain decisions, without module code."""
    if not isinstance(term, str):
        return ("TYPE_ERROR", "term must be a string")
    if type(budget) is not int or budget < 0 or budget == 0:
        return ("BUDGET_REFUSAL",
                "the View projection exceeds the non-negative integer work budget")
    role_terms = {role.term for clause in view.clauses
                  for role in clause.roles if isinstance(role.term, str)
                  and role.term}
    if (term in role_terms
            or any(clause.predicate == term for clause in view.clauses)):
        return ("KNOWN_TERM", "a semantic clause already holds this term")

    # These generated sources contain only whitespace-separated ASCII words.
    # Count the distinct words directly, independently of the implementation's
    # vocabulary builder.
    source_words = {word for raw in view.sources.values()
                    for word in raw.split() if word}
    projected_work = (len(view.clauses)
                       + sum(len(clause.roles) for clause in view.clauses)
                       + len(source_words))
    if projected_work > budget:
        return ("BUDGET_REFUSAL",
                "the View projection exceeds the non-negative integer work budget")
    return ("BEYOND_REFERENCE", "")


def _assert_matches_reference(view: _View, term: object, budget: object) -> None:
    expected_status, expected_reason = _naive_early_result(view, term, budget)
    if expected_status == "TYPE_ERROR":
        with pytest.raises(TypeError, match="term must be a string"):
            unknown_candidates(view, term, budget)  # type: ignore[arg-type]
        return
    report = unknown_candidates(view, term, budget)  # type: ignore[arg-type]
    assert report.term == term
    if expected_status == "BEYOND_REFERENCE":
        assert report.status in {
            "CANDIDATES", "ABSTAIN_BARE_SUFFIX_SPLIT", "ABSTAIN_SPLIT_TIED",
            "ABSTAIN_UNIT_NOT_A_WORD",
        }
        for candidate in report.candidates:
            assert candidate.constructed is True
            assert candidate.evidence is False
        return
    assert report.status == expected_status
    if expected_status != "BEYOND_REFERENCE":
        assert report.reason == expected_reason
        assert report.candidates == ()


def test_non_string_terms_raise_before_budget_handling() -> None:
    for term in (None, 7, b"unknown"):
        _assert_matches_reference(_view(), term, -1)


def test_non_integer_or_negative_budgets_refuse() -> None:
    for budget in (None, True, 2.0, "2", -1):
        _assert_matches_reference(_view({"s": "alpha beta"}), "unknown", budget)


def test_zero_budget_refuses_with_a_typed_empty_report() -> None:
    _assert_matches_reference(_view({"s": "alpha"}), "unknown", 0)


def test_role_term_is_known_before_projection_budget_is_checked() -> None:
    view = _view({"s": "Ada met Bob"}, roles=("Ada", "Bob"), predicate="met")
    _assert_matches_reference(view, "Ada", 1)


def test_predicate_is_known_before_projection_budget_is_checked() -> None:
    view = _view({"s": "Ada met Bob"}, roles=("Ada", "Bob"), predicate="met")
    _assert_matches_reference(view, "met", 1)


def test_source_word_counts_toward_projection_budget() -> None:
    view = _view({"s": "alpha beta"})
    # Two distinct source words exceed a budget of one.
    _assert_matches_reference(view, "unseen", 1)


def test_generated_small_views_match_reference_for_budget_refusals() -> None:
    for count in range(1, 6):
        names = tuple(f"person{index}" for index in range(count))
        source = " ".join(names)
        view = _view({"s": source}, roles=names)
        _assert_matches_reference(view, "unseen", 1)


def test_generated_known_terms_precede_any_projection_refusal() -> None:
    for count in range(1, 5):
        names = tuple(f"person{index}" for index in range(count))
        source = " ".join(names) + " meets"
        view = _view({"s": source}, roles=names, predicate="meets")
        for term in (*names, "meets"):
            _assert_matches_reference(view, term, 1)


def test_unknown_result_is_typed_constructed_output_not_an_answer() -> None:
    view = _view({"s": "alpha beta"})
    report = unknown_candidates(view, "unseen")
    assert report.status in {
        "CANDIDATES", "ABSTAIN_BARE_SUFFIX_SPLIT", "ABSTAIN_SPLIT_TIED",
        "ABSTAIN_UNIT_NOT_A_WORD", "BUDGET_REFUSAL",
    }
    assert report.status != "KNOWN_TERM"
    for candidate in report.candidates:
        assert candidate.term == "unseen"
        assert candidate.kind in {
            "EXPLAINED_BY_UNITS", "KIN_NEIGHBOURHOOD", "NO_REACH",
        }
        assert candidate.constructed is True
        assert candidate.evidence is False


def test_unknown_report_serialization_is_stable_and_preserves_typed_flags() -> None:
    view = _view({"s": "alpha beta"})
    first = unknown_candidates(view, "unseen").to_json()
    second = unknown_candidates(view, "unseen").to_json()
    assert first == second
    report = unknown_candidates(view, "unseen").to_dict()
    assert report["term"] == "unseen"
    for candidate in report["candidates"]:
        assert candidate["constructed"] is True
        assert candidate["evidence"] is False
