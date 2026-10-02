"""Focused stress cases for the semantic leaf router using small prose-shaped IR views."""

import pytest

from verantyx.semantic_ir import (
    Clause,
    Nominal,
    Operator,
    Pattern,
    Plan,
    Request,
    Role,
    Span,
    Unread,
    Variable,
    View,
)
from verantyx.semantic_route import LeafTree, pattern_anchors


def _clause(source, terms, *, predicate="about", text=None, conditions=(), exceptions=()):
    text = text or f"{source} discusses {', '.join(terms.values())}."
    span = Span(source, 0, len(text), text)
    roles = tuple(Role(name, value, span) for name, value in terms.items())
    return Clause(
        f"{source}:{predicate}:{len(terms)}",
        Variable(f"event:{source}", "event"),
        predicate,
        span,
        roles,
        span,
        conditions=tuple(conditions),
        exceptions=tuple(exceptions),
    )


def _view(clauses, unread=()):
    clauses = tuple(clauses)
    unread = tuple(unread)
    source_names = {c.span.source for c in clauses} | {u.span.source for u in unread}
    sources = {name: " ".join(c.span.text for c in clauses if c.span.source == name) for name in source_names}
    return View(sources, clauses, unread)


def _request(*patterns):
    nodes = tuple(Operator(f"bind-{i}", "Bind", pattern=p) for i, p in enumerate(patterns))
    plan = Plan(nodes, nodes[-1].id if nodes else "root")
    return Request("a prose-shaped question", (plan,), (), ())


def _pattern(predicate="about", **roles):
    return Pattern(predicate, tuple(roles.items()))


def _seven_leaf_view(clauses, unread=()):
    clauses = list(clauses)
    sources = {c.span.source for c in clauses} | {u.span.source for u in unread}
    index = 0
    while len(sources) < 7:
        name = f"background-{index}"
        clauses.append(_clause(name, {"topic": f"topic-{index}"}))
        sources.add(name)
        index += 1
    return _view(clauses, unread)


def test_pattern_anchors_keeps_literal_roles_and_ignores_attributes_and_nominals():
    request = _request(
        Pattern(
            "located_in",
            (("entity", "Orion"), ("attribute", "blue"), ("place", Nominal("city", "Harbor"))),
        )
    )

    assert pattern_anchors(request) == [{"Orion"}]


def test_unanchored_request_keeps_the_full_view():
    view = _seven_leaf_view([_clause("evidence", {"item": "Orion"})])
    request = _request(Pattern("measured_by", (("attribute", "temperature"),)))

    routed, trace = LeafTree(view).restrict(request)

    assert routed is None
    assert trace["status"] == "skipped"
    assert trace["reason"] == "request has no entity anchor"


def test_fewer_than_the_routing_threshold_falls_back_to_the_flat_view():
    view = _view([_clause(f"doc-{i}", {"entity": "Orion" if i == 0 else f"topic-{i}"}) for i in range(6)])

    routed, trace = LeafTree(view).restrict(_request(_pattern(entity="Orion")))

    assert routed is None
    assert trace["status"] == "skipped"
    assert trace["reason"] == "fewer leaves than one routing node"


def test_each_bind_pattern_requires_all_of_its_literal_role_values():
    clauses = [
        _clause("both", {"entity": "Orion", "place": "Harbor"}),
        _clause("entity-only", {"entity": "Orion", "place": "Elsewhere"}),
        _clause("place-only", {"entity": "Other", "place": "Harbor"}),
        *[_clause(f"background-{i}", {"entity": f"topic-{i}"}) for i in range(4)],
    ]
    view = _view(clauses)

    routed, trace = LeafTree(view).restrict(_request(_pattern(entity="Orion", place="Harbor")))

    assert trace["status"] == "routed"
    assert {c.span.source for c in routed.clauses} == {"both"}


def test_multiple_bind_patterns_union_their_evidence_documents():
    clauses = [
        _clause("orion-doc", {"entity": "Orion"}),
        _clause("harbor-doc", {"entity": "Harbor"}),
        *[_clause(f"background-{i}", {"entity": f"topic-{i}"}) for i in range(5)],
    ]

    routed, trace = LeafTree(_view(clauses)).restrict(
        _request(_pattern(entity="Orion"), _pattern(entity="Harbor"))
    )

    assert trace["status"] == "routed"
    assert {c.span.source for c in routed.clauses} == {"orion-doc", "harbor-doc"}


def test_common_anchor_does_not_hide_a_selective_anchor_in_the_same_pattern():
    clauses = [
        _clause("a", {"entity": "Harbor", "kind": "shared"}),
        _clause("b", {"entity": "Harbor", "kind": "shared"}),
        *[_clause(f"background-{i}", {"entity": f"topic-{i}", "kind": "shared"}) for i in range(5)],
    ]

    routed, trace = LeafTree(_view(clauses)).restrict(
        _request(_pattern(entity="Harbor", kind="shared")), anchor_cap=2
    )

    assert trace["status"] == "routed"
    assert {c.span.source for c in routed.clauses} == {"a", "b"}


def test_only_common_anchors_fall_back_instead_of_narrowing():
    clauses = [_clause(f"doc-{i}", {"entity": "shared"}) for i in range(7)]

    routed, trace = LeafTree(_view(clauses)).restrict(
        _request(_pattern(entity="shared")), anchor_cap=2
    )

    assert routed is None
    assert trace["status"] == "skipped"
    assert trace["reason"] == "every anchor of a pattern is common"


def test_unread_substring_mentions_route_their_document_and_keep_evidence_unread():
    clauses = [
        _clause("evidence", {"entity": "Riverton"}, text="Riverton is a coastal town."),
        *[_clause(f"background-{i}", {"entity": f"topic-{i}"}) for i in range(5)],
    ]
    evidence_unread = Unread(Span("evidence", 40, 61, "A separate unread note."), "opaque sentence")
    mention = Unread(Span("unread-mention", 0, 39, "The notice mentions Riverton's bridge."), "opaque sentence")
    view = _seven_leaf_view(clauses, (evidence_unread, mention))

    routed, trace = LeafTree(view).restrict(_request(_pattern(entity="Riverton")))

    assert trace["status"] == "routed"
    assert {u.span.source for u in routed.unread} == {"evidence", "unread-mention"}
    assert evidence_unread in routed.unread
    assert mention in routed.unread


def test_routed_view_is_a_subset_of_the_input_view():
    clauses = [
        _clause("selected", {"entity": "Orion"}, text="Orion was observed by the station."),
        *[_clause(f"other-{i}", {"entity": f"topic-{i}"}) for i in range(6)],
    ]
    unread = Unread(Span("selected", 40, 55, "A short note."), "opaque sentence")
    view = _view(clauses, (unread,))

    routed, trace = LeafTree(view).restrict(_request(_pattern(entity="Orion")))

    assert trace["status"] == "routed"
    assert set(routed.clauses) <= set(view.clauses)
    assert set(routed.unread) <= set(view.unread)
    assert set(routed.sources) <= set(view.sources)


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: single-character anchors inside longer unread spans are not indexed",
)
def test_single_character_anchor_is_located_in_unread_text():
    clauses = [
        _clause("evidence", {"entity": "Q"}, text="Q has a recorded entry."),
        *[_clause(f"background-{i}", {"entity": f"topic-{i}"}) for i in range(5)],
    ]
    unread = Unread(Span("unread-q", 0, 20, "A note mentions Q."), "opaque sentence")

    routed, trace = LeafTree(_seven_leaf_view(clauses, (unread,))).restrict(
        _request(_pattern(entity="Q"))
    )

    assert trace["status"] == "routed"
    assert unread in routed.unread
