from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import gc
import tracemalloc

import pytest

from verantyx.semantic_unknown import unknown_candidates


@dataclass(frozen=True)
class SpanStub:
    source: str
    start: int
    end: int
    text: str

    def valid(self, sources):
        return (
            self.source in sources
            and 0 <= self.start <= self.end <= len(sources[self.source])
            and sources[self.source][self.start:self.end] == self.text
        )


@dataclass(frozen=True)
class RoleStub:
    term: str
    span: SpanStub


@dataclass(frozen=True)
class ClauseStub:
    id: str
    predicate: str
    span: SpanStub
    roles: tuple[RoleStub, ...]


@dataclass(frozen=True)
class ViewStub:
    sources: dict[str, str]
    clauses: tuple[ClauseStub, ...]


def empty_view():
    return ViewStub({}, ())


def one_clause_empty_projection():
    return ViewStub(
        {"s": ""},
        (ClauseStub("c", "predicate", SpanStub("s", 0, 0, ""), ()),),
    )


def populated_view(reverse=False):
    text = "alpha beta"
    whole = SpanStub("s", 0, len(text), text)
    alpha = RoleStub("alpha", SpanStub("s", 0, 5, "alpha"))
    beta = RoleStub("beta", SpanStub("s", 6, 10, "beta"))
    clauses = (
        ClauseStub("c1", "joins", whole, (alpha, beta)),
        ClauseStub("c2", "connects", whole, (beta, alpha)),
    )
    return ViewStub({"s": text}, tuple(reversed(clauses)) if reverse else clauses)


def assert_typed_report(report):
    assert report.status in {
        "KNOWN_TERM",
        "CANDIDATES",
        "ABSTAIN_BARE_SUFFIX_SPLIT",
        "ABSTAIN_SPLIT_TIED",
        "ABSTAIN_UNIT_NOT_A_WORD",
        "BUDGET_REFUSAL",
    }
    for candidate in report.candidates:
        assert candidate.kind in {
            "EXPLAINED_BY_UNITS",
            "KIN_NEIGHBOURHOOD",
            "NO_REACH",
        }
        assert candidate.constructed is True
        assert candidate.evidence is False


@pytest.mark.parametrize("budget", [0, -1, 1.5, True, None])
def test_invalid_work_budgets_return_typed_refusal(budget):
    report = unknown_candidates(empty_view(), "mystery", budget=budget)

    assert report.status == "BUDGET_REFUSAL"
    assert report.candidates == ()


def test_non_string_query_is_rejected_as_a_programmer_error():
    with pytest.raises(TypeError, match="term must be a string"):
        unknown_candidates(empty_view(), None)


def test_empty_view_fits_minimal_positive_budget():
    report = unknown_candidates(empty_view(), "mystery", budget=1)

    assert report.status != "BUDGET_REFUSAL"
    assert_typed_report(report)


def test_budget_refusal_has_no_candidates():
    report = unknown_candidates(empty_view(), "mystery", budget=0)

    assert report.status == "BUDGET_REFUSAL"
    assert report.candidates == ()


def test_large_source_projection_refuses_with_a_typed_report():
    text = "word " * 10_000
    span = SpanStub("s", 0, len(text), text)
    clauses = (
        ClauseStub("c1", "first", span, ()),
        ClauseStub("c2", "second", span, ()),
    )
    view = ViewStub({"s": text}, clauses)

    report = unknown_candidates(view, "mystery", budget=1)

    assert report.status == "BUDGET_REFUSAL"
    assert report.candidates == ()


def test_long_query_on_empty_view_returns_a_typed_report():
    report = unknown_candidates(empty_view(), "x" * 16_384, budget=1)

    assert_typed_report(report)


def test_clause_held_role_and_predicate_are_known_terms():
    view = populated_view()

    assert unknown_candidates(view, "alpha", budget=100).status == "KNOWN_TERM"
    assert unknown_candidates(view, "joins", budget=100).status == "KNOWN_TERM"


def test_constructed_outputs_are_typed_and_never_evidence():
    report = unknown_candidates(populated_view(), "alphabeta", budget=100)

    assert_typed_report(report)
    if report.status == "CANDIDATES":
        assert report.candidates


def test_clause_and_role_order_do_not_change_report_json():
    left = unknown_candidates(populated_view(), "alphabeta", budget=100)
    right = unknown_candidates(populated_view(reverse=True), "alphabeta", budget=100)

    assert left.to_json() == right.to_json()


def test_repeated_calls_are_idempotent():
    view = populated_view()
    first = unknown_candidates(view, "alphabeta", budget=100).to_json()

    assert all(
        unknown_candidates(view, "alphabeta", budget=100).to_json() == first
        for _ in range(8)
    )


def test_two_concurrent_readers_return_the_same_report():
    view = populated_view()
    with ThreadPoolExecutor(max_workers=2) as pool:
        reports = list(pool.map(
            lambda _: unknown_candidates(view, "alphabeta", budget=100).to_json(),
            range(2),
        ))

    assert reports[0] == reports[1]


def test_repeated_empty_reads_do_not_retain_unbounded_memory():
    view = empty_view()
    unknown_candidates(view, "mystery", budget=1)
    gc.collect()
    tracemalloc.start()
    try:
        for _ in range(16):
            unknown_candidates(view, "mystery", budget=1)
        gc.collect()
        current, _ = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert current < 1_000_000


def test_exact_projection_budget_is_not_refused():
    # The projection contains one source clause, no role terms, and no source words.
    # The documented budget covers those projected items, so a budget of one fits.
    report = unknown_candidates(one_clause_empty_projection(), "mystery", budget=1)

    assert report.status != "BUDGET_REFUSAL"
