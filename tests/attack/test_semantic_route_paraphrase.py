from types import SimpleNamespace

import pytest

from verantyx.semantic_ir import Clause, Nominal, Pattern, Role, Span, Unread, Variable, View
from verantyx.semantic_route import LeafTree


def _clause(source, *roles, predicate="mention", polarity="+", conditions=()):
    text = f"record from {source}"
    span = Span(source, 0, len(text), text)
    return Clause(
        f"{source}-{predicate}", Variable(f"event-{source}"), predicate, span,
        tuple(Role(name, term, span) for name, term in roles), span,
        polarity=polarity, conditions=tuple(conditions),
    )


def _view(clauses, unread=()):
    clauses = tuple(clauses)
    unread = tuple(unread)
    sources = {clause.span.source: f"{clause.span.source}.txt" for clause in clauses}
    sources.update({item.span.source: f"{item.span.source}.txt" for item in unread})
    return View(sources, clauses, unread)


def _request(patterns, text="", *, plan_groups=None):
    if plan_groups is None:
        plan_groups = (patterns,)
    plans = tuple(
        SimpleNamespace(nodes=tuple(SimpleNamespace(pattern=pattern) for pattern in group))
        for group in plan_groups
    )
    return SimpleNamespace(text=text, plans=plans)


def _pattern(*roles, predicate="mention"):
    return Pattern(predicate, tuple(roles))


def _unread(source, text):
    return Unread(Span(source, 0, len(text), text), "opaque source span")


def _sources(view):
    routed, trace = LeafTree(view).restrict(_request((_pattern(("object", "Tokyo")),)))
    assert trace["status"] == "routed"
    return routed, trace


def test_anchor_routes_every_document_with_that_surface_value():
    clauses = [
        _clause("d0", ("destination", "Tokyo"), predicate="visit"),
        _clause("d1", ("destination", "Tokyo"), predicate="avoid", polarity="-"),
    ] + [_clause(f"d{i}", ("destination", f"place-{i}")) for i in range(2, 9)]
    view = _view(clauses, (_unread("d0", "Tokyo is mentioned here"),))

    routed, trace = _sources(view)

    assert trace["status"] == "routed"
    assert set(routed.sources) == {"d0", "d1"}
    assert {clause.id for clause in routed.clauses} == {"d0-visit", "d1-avoid"}
    assert set(routed.clauses) <= set(view.clauses)


def test_polite_plain_particle_and_word_order_paraphrases_keep_route():
    clauses = [
        _clause("d0", ("traveler", "Aiko"), ("destination", "Kobe")),
        _clause("d1", ("traveler", "Aiko"), ("destination", "Kobe"), predicate="report"),
    ] + [_clause(f"d{i}", ("place", f"place-{i}")) for i in range(2, 9)]
    view = _view(clauses, (_unread("d0", "Aiko travels to Kobe"),))
    variants = (
        ("Where did Aiko go?", (("traveler", "Aiko"), ("destination", "Kobe"))),
        ("Could you tell me where Aiko went, please?", (("traveler", "Aiko"), ("destination", "Kobe"))),
        ("Aiko, where did they go to?", (("destination", "Kobe"), ("traveler", "Aiko"))),
        ("Where to did Aiko travel, please?", (("destination", "Kobe"), ("traveler", "Aiko"))),
    )

    routed_sets = []
    for text, roles in variants:
        request = _request((_pattern(*roles, predicate="visit"),), text)
        routed, trace = LeafTree(view).restrict(request)
        assert trace["status"] == "routed"
        routed_sets.append(set(routed.sources))

    assert routed_sets == [{"d0", "d1"}] * len(variants)


def test_entity_swap_changes_the_reached_documents():
    clauses = [
        _clause("d0", ("destination", "Tokyo")),
        _clause("d1", ("destination", "Osaka")),
    ] + [_clause(f"d{i}", ("destination", f"place-{i}")) for i in range(2, 9)]
    view = _view(clauses, (_unread("d0", "Tokyo"), _unread("d1", "Osaka")))

    tokyo, tokyo_trace = LeafTree(view).restrict(_request((_pattern(("destination", "Tokyo")),)))
    osaka, osaka_trace = LeafTree(view).restrict(_request((_pattern(("destination", "Osaka")),)))

    assert tokyo_trace["status"] == osaka_trace["status"] == "routed"
    assert set(tokyo.sources) == {"d0"}
    assert set(osaka.sources) == {"d1"}


def test_one_pattern_requires_all_literal_values_on_a_reached_leaf():
    clauses = [
        _clause("d0", ("person", "Mina"), ("place", "Kyoto")),
        _clause("d1", ("person", "Mina")),
        _clause("d2", ("place", "Kyoto")),
    ] + [_clause(f"d{i}", ("place", f"place-{i}")) for i in range(3, 9)]
    view = _view(clauses, (_unread("d0", "Mina is in Kyoto"),))
    request = _request((_pattern(("person", "Mina"), ("place", "Kyoto")),))

    routed, trace = LeafTree(view).restrict(request)

    assert trace["status"] == "routed"
    assert set(routed.sources) == {"d0"}


def test_separate_bind_patterns_union_their_anchor_documents():
    clauses = [
        _clause("d0", ("place", "Tokyo")),
        _clause("d1", ("place", "Osaka")),
    ] + [_clause(f"d{i}", ("place", f"place-{i}")) for i in range(2, 9)]
    view = _view(clauses, (_unread("d0", "Tokyo"), _unread("d1", "Osaka")))
    request = _request(
        (),
        plan_groups=((_pattern(("place", "Tokyo")), _pattern(("place", "Osaka"))),),
    )

    routed, trace = LeafTree(view).restrict(request)

    assert trace["status"] == "routed"
    assert set(routed.sources) == {"d0", "d1"}


def test_common_anchor_keeps_flat_view_instead_of_narrowing():
    clauses = [_clause(f"d{i}", ("organization", "Institute"), ("id", f"id-{i}")) for i in range(9)]
    view = _view(clauses, (_unread("d0", "Institute"),))
    request = _request((_pattern(("organization", "Institute")),))

    routed, trace = LeafTree(view).restrict(request, anchor_cap=3)

    assert routed is None
    assert trace["status"] == "skipped"
    assert trace["reason"] == "every anchor of a pattern is common"


def test_role_only_pattern_keeps_flat_view():
    clauses = [_clause(f"d{i}", ("place", f"place-{i}")) for i in range(8)]
    view = _view(clauses)
    request = _request((_pattern(("attribute", "north")),))

    routed, trace = LeafTree(view).restrict(request)

    assert routed is None
    assert trace["status"] == "skipped"
    assert trace["reason"] == "request has no entity anchor"


def test_guard_entity_brings_in_its_own_fact_document():
    guard = _pattern(("object", "shop"), predicate="open")
    clauses = [
        _clause("d0", ("person", "Ari"), predicate="hire", conditions=(guard,)),
        _clause("d1", ("object", "shop"), predicate="open"),
    ] + [_clause(f"d{i}", ("place", f"place-{i}")) for i in range(2, 9)]
    view = _view(clauses, (_unread("d0", "Ari hired someone"), _unread("d1", "shop is open")))
    request = _request((_pattern(("person", "Ari"), predicate="hire"),))

    routed, trace = LeafTree(view).restrict(request)

    assert trace["status"] == "routed"
    assert {"d0", "d1"} <= set(routed.sources)
    assert "d1-open" in {clause.id for clause in routed.clauses}
    assert trace["followed_terms"] >= 1


@pytest.mark.xfail(strict=False, reason="DEFECT: nominal-valued clause roles are not indexed by their surface head")
def test_nominal_clause_role_head_is_not_dropped_from_the_route():
    nominal_clause = _clause("d0", ("destination", Nominal("Tokyo", "Tokyo")))
    clauses = [nominal_clause] + [_clause(f"d{i}", ("destination", f"place-{i}")) for i in range(1, 9)]
    view = _view(clauses, (_unread("d9", "Tokyo appears in unread text"),))
    request = _request((_pattern(("destination", "Tokyo")),))

    routed, trace = LeafTree(view).restrict(request)

    assert trace["status"] == "routed"
    assert "d9" in routed.sources
    assert "d0" in routed.sources


@pytest.mark.xfail(strict=False, reason="DEFECT: whitespace-normalized unread matches are removed by exact substring filtering")
def test_unread_anchor_match_survives_spacing_variant():
    clauses = [_clause("d0", ("destination", "New York"))]
    clauses.extend(_clause(f"d{i}", ("destination", f"place-{i}")) for i in range(1, 9))
    view = _view(clauses, (_unread("d9", "NewYork appears in an opaque span"),))
    request = _request((_pattern(("destination", "New York")),))

    routed, trace = LeafTree(view).restrict(request)

    assert trace["status"] == "routed"
    assert "d9" in routed.sources
    assert any(item.span.source == "d9" for item in routed.unread)
