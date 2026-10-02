"""Independent checks for the semantic leaf router's document reach set."""

from __future__ import annotations

import random

import pytest

from verantyx import semantic_ir as ir
from verantyx.semantic_route import LeafTree


def _span(source: str, text: str = "source text") -> ir.Span:
    return ir.Span(source, 0, len(text), text)


def _clause(source: str, terms: tuple[str, ...], *, predicate: str = "link") -> ir.Clause:
    span = _span(source, " ".join(terms))
    roles = tuple(ir.Role("entity", term, span) for term in terms)
    return ir.Clause(source, ir.Variable("e"), predicate, span, roles, span)


def _view(rows: dict[str, tuple[str, ...]], *, unread=()) -> ir.View:
    clauses = tuple(_clause(source, terms) for source, terms in rows.items())
    return ir.View({source: source for source in rows}, clauses, tuple(unread))


def _request(*role_groups: tuple[tuple[str, object], ...]) -> ir.Request:
    nodes = tuple(
        ir.Operator(f"b{i}", "bind", pattern=ir.Pattern("link", roles))
        for i, roles in enumerate(role_groups)
    )
    plan = ir.Plan(nodes, nodes[-1].id if nodes else "")
    return ir.Request("synthetic question", (plan,), (), ())


def _literal(*terms: str) -> tuple[tuple[str, object], ...]:
    return tuple((f"role{i}", term) for i, term in enumerate(terms))


def _naive_flat_sources(view: ir.View, request: ir.Request, *, anchor_cap: int) -> set[str] | None:
    """Reference the documented flat bind reach: intersect each pattern, then union patterns."""
    if len(view.sources) < 7:
        return None

    patterns: list[set[str]] = []
    for plan in request.plans:
        for node in plan.nodes:
            if node.pattern is None:
                continue
            literals = {
                term
                for name, term in node.pattern.roles
                if name != "attribute" and isinstance(term, str) and term
            }
            if literals:
                patterns.append(literals)
    if not patterns:
        return None

    terms_by_source: dict[str, set[str]] = {source: set() for source in view.sources}
    for clause in view.clauses:
        for role in clause.roles:
            if isinstance(role.term, str) and role.term:
                terms_by_source.setdefault(clause.span.source, set()).add(role.term)

    reached: set[str] = set()
    for pattern in patterns:
        usable: list[set[str]] = []
        for term in pattern:
            holders = {source for source, terms in terms_by_source.items() if term in terms}
            if len(holders) <= anchor_cap:
                usable.append(holders)
        if not usable:
            return None
        matching = set.intersection(*usable)
        reached.update(matching)
    return reached


def _routed_sources(view: ir.View, request: ir.Request, **kwargs) -> set[str] | None:
    routed, _trace = LeafTree(view).restrict(request, **kwargs)
    return None if routed is None else set(routed.sources)


def test_generated_flat_routes_match_independent_naive_reference():
    rng = random.Random(7319)
    for case in range(48):
        count = rng.randint(8, 17)
        vocabulary = [f"entity-{i}" for i in range(12)]
        group = tuple(rng.sample(vocabulary, rng.randint(1, 3)))
        rows = {}
        for i in range(count):
            terms = set(rng.sample(vocabulary, rng.randint(1, 5)))
            if i == 0:
                terms.update(group)
            rows[f"doc-{case}-{i}"] = tuple(sorted(terms))
        view = _view(rows)
        request = _request(_literal(*group))
        expected = _naive_flat_sources(view, request, anchor_cap=100)
        observed = _routed_sources(view, request, anchor_cap=100)
        assert observed == expected, f"generated case {case}: {group!r}"


def test_one_pattern_intersects_every_literal_on_the_same_document():
    view = _view({
        "both": ("Mira", "Kyoto"),
        "only-person": ("Mira", "Osaka"),
        "only-place": ("Noah", "Kyoto"),
        **{f"filler-{i}": (f"other-{i}",) for i in range(5)},
    })
    request = _request(_literal("Mira", "Kyoto"))
    assert _routed_sources(view, request) == {"both"}


def test_separate_bind_patterns_union_their_reach_sets():
    view = _view({
        "first": ("Mira",),
        "second": ("Noah",),
        "both": ("Mira", "Noah"),
        **{f"filler-{i}": (f"other-{i}",) for i in range(5)},
    })
    request = _request(_literal("Mira"), _literal("Noah"))
    assert _routed_sources(view, request) == {"first", "second", "both"}


def test_attribute_roles_are_not_entity_anchors():
    rows = {"entity": ("Mira",), "attribute-only": ("blue",)}
    rows.update({f"filler-{i}": (f"other-{i}",) for i in range(6)})
    view = _view(rows)
    request = _request((("person", "Mira"), ("attribute", "blue")))
    assert _routed_sources(view, request) == {"entity"}


def test_nominal_only_pattern_has_no_literal_anchor_and_keeps_flat_view():
    rows = {f"doc-{i}": (f"entity-{i}",) for i in range(8)}
    view = _view(rows)
    nominal = ir.Nominal("Mira", ir.Variable("x"))
    request = _request((("person", nominal),))
    assert _routed_sources(view, request) is None


def test_too_few_leaf_documents_skip_routing():
    view = _view({f"doc-{i}": (f"entity-{i}",) for i in range(6)})
    assert _routed_sources(view, _request(_literal("entity-1"))) is None


def test_all_common_anchors_skip_routing_conservatively():
    view = _view({f"doc-{i}": ("public", f"local-{i}") for i in range(8)})
    assert _routed_sources(view, _request(_literal("public")), anchor_cap=1) is None


def test_common_anchor_is_ignored_when_another_anchor_is_selective():
    rows = {f"doc-{i}": ("public", f"local-{i}") for i in range(8)}
    rows["doc-3"] = ("public", "needle", "local-3")
    view = _view(rows)
    request = _request(_literal("public", "needle"))
    expected = _naive_flat_sources(view, request, anchor_cap=1)
    assert expected == {"doc-3"}
    assert _routed_sources(view, request, anchor_cap=1) == expected


def test_unread_mentions_gate_candidate_documents_and_evidence_keeps_all_unread():
    rows = {"evidence": ("Orchid",)}
    rows.update({f"doc-{i}": (f"other-{i}",) for i in range(7)})
    unread = (
        ir.Unread(_span("evidence", "an unrelated correction"), "unsupported"),
        ir.Unread(_span("mention", "Orchid was described"), "unsupported"),
    )
    view = ir.View({**{source: source for source in rows}, "mention": "mention"},
                   tuple(_clause(source, terms) for source, terms in rows.items()), unread)
    routed, _trace = LeafTree(view).restrict(_request(_literal("Orchid")))
    assert routed is not None
    assert set(routed.sources) == {"evidence", "mention"}
    assert {u.span.source for u in routed.unread} == {"evidence", "mention"}
    assert any(u.span.text == "an unrelated correction" for u in routed.unread)


def test_instruction_unread_is_excluded_from_index_but_follows_reached_source():
    rows = {"evidence": ("Orchid",)}
    rows.update({f"doc-{i}": (f"other-{i}",) for i in range(7)})
    instruction = (
        ir.Unread(_span("evidence", "Orchid instruction"), "document instruction excluded"),
        ir.Unread(_span("instruction-only", "Orchid hidden"), "document instruction excluded"),
    )
    sources = {source: source for source in rows}
    sources["instruction-only"] = "instruction-only"
    view = ir.View(sources,
                   tuple(_clause(source, terms) for source, terms in rows.items()), instruction)
    routed, _trace = LeafTree(view).restrict(_request(_literal("Orchid")))
    assert routed is not None
    assert set(routed.sources) == {"evidence"}
    assert {u.span.source for u in routed.unread} == {"evidence"}


def test_two_bind_plan_follows_a_rare_entity_chain_one_join_hop():
    rows = {
        "seed": ("Seed", "Bridge"),
        "middle": ("Bridge", "Target"),
        "target": ("Target", "Leaf"),
        **{f"filler-{i}": (f"other-{i}",) for i in range(5)},
    }
    view = _view(rows)
    request = _request(_literal("Seed"), _literal("Target"))
    assert _routed_sources(view, request, expand_cap=8) == {"seed", "middle", "target"}


def test_routed_view_never_contains_a_clause_from_outside_the_input_view():
    rows = {f"doc-{i}": (f"entity-{i}",) for i in range(8)}
    view = _view(rows)
    routed, _trace = LeafTree(view).restrict(_request(_literal("entity-4")))
    assert routed is not None
    assert set(routed.clauses) <= set(view.clauses)
