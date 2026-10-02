from types import SimpleNamespace

import pytest

from verantyx.semantic_ir import Clause, Pattern, Role, Span, Unread, Variable, View
from verantyx.semantic_route import LeafTree


def _clause(source, predicate, roles, *, polarity="+", conditions=(), exceptions=(), text=None):
    text = text or f"{source}: {predicate}"
    span = Span(source, 0, len(text), text)
    return Clause(
        id=f"{source}:{predicate}:{polarity}",
        event=Variable(f"event_{source}_{predicate}"),
        predicate=predicate,
        predicate_span=span,
        roles=tuple(Role(name, term, span) for name, term in roles),
        span=span,
        polarity=polarity,
        conditions=conditions,
        exceptions=exceptions,
    )


def _request(*patterns):
    nodes = tuple(SimpleNamespace(pattern=pattern) for pattern in patterns)
    return SimpleNamespace(plans=(SimpleNamespace(nodes=nodes),))


def _unread(source, text, reason="unparsed"):
    return Unread(Span(source, 0, len(text), text), reason)


def _base_view(anchor="Mira", *, unread=(), extras=()):
    clauses = [
        _clause("d0", "likes", (("agent", anchor), ("patient", "tea"))),
        *extras,
    ]
    clauses.extend(
        _clause(f"d{i}", "mentions", (("agent", f"person{i}"),))
        for i in range(1, 8)
    )
    sources = {c.span.source: c.span.text for c in clauses}
    sources.update({u.span.source: u.span.text for u in unread})
    return View(sources, tuple(clauses), tuple(unread))


def _route(view, *patterns, **kwargs):
    return LeafTree(view).restrict(_request(*patterns), **kwargs)


def test_route_is_a_subset_and_preserves_original_clause_records():
    extra = _clause("d0", "dislikes", (("agent", "Mira"),), polarity="-")
    view = _base_view(extras=(extra,))
    routed, trace = _route(view, Pattern("likes", (("agent", "Mira"),)))

    assert trace["status"] == "routed"
    assert set(routed.sources) == {"d0"}
    assert set(routed.clauses) == {c for c in view.clauses if c.span.source == "d0"}
    assert all(any(c is original for original in view.clauses) for c in routed.clauses)
    assert all(u in view.unread for u in routed.unread)
    assert routed.clauses[0].span.text == view.clauses[0].span.text


def test_same_anchor_in_separate_documents_keeps_both_polarities():
    negative = _clause("d1", "likes", (("agent", "Mira"),), polarity="-")
    view = _base_view(extras=(negative,))
    routed, _ = _route(view, Pattern("likes", (("agent", "Mira"),)))

    assert {c.span.source for c in routed.clauses} == {"d0", "d1"}
    assert {c.polarity for c in routed.clauses if c.predicate == "likes"} == {"+", "-"}


def test_anchor_mention_in_a_different_role_is_not_lost():
    object_mention = _clause("d2", "owns", (("patient", "Mira"),))
    view = _base_view(extras=(object_mention,))
    routed, _ = _route(view, Pattern("likes", (("agent", "Mira"),)))

    assert "d2" in routed.sources
    assert object_mention in routed.clauses


def test_unrelated_documents_are_not_added_to_the_reach_set():
    view = _base_view()
    routed, _ = _route(view, Pattern("likes", (("agent", "Mira"),)))

    assert set(routed.sources) == {"d0"}
    assert not any(c.span.source != "d0" for c in routed.clauses)


def test_common_anchor_does_not_hide_a_selective_anchor():
    extras = (
        _clause("d1", "likes", (("agent", "shared"), ("patient", "rare"))),
        _clause("d2", "likes", (("agent", "shared"), ("patient", "rare"))),
        _clause("d3", "likes", (("agent", "shared"),)),
    )
    view = _base_view("shared", extras=extras)
    routed, _ = _route(
        view,
        Pattern("likes", (("agent", "shared"), ("patient", "rare"))),
        anchor_cap=2,
    )

    assert set(routed.sources) == {"d1", "d2"}


def test_all_common_pattern_falls_back_to_the_flat_view():
    clauses = tuple(
        _clause(f"d{i}", "mentions", (("agent", "common"),))
        for i in range(8)
    )
    view = View({c.span.source: c.span.text for c in clauses}, clauses)
    routed, trace = _route(view, Pattern("mentions", (("agent", "common"),)), anchor_cap=2)

    assert routed is None
    assert trace["status"] == "skipped"
    assert trace["reason"] == "every anchor of a pattern is common"


def test_unread_anchor_mention_keeps_the_complete_unread_span():
    unread = _unread("unread-doc", "Mira was not invited; check this span")
    view = _base_view(unread=(unread,))
    routed, _ = _route(view, Pattern("likes", (("agent", "Mira"),)))

    assert unread in routed.unread
    assert next(u for u in routed.unread if u is unread).span.text == unread.span.text


def test_instruction_unread_is_retained_whole_when_its_source_is_reached():
    instruction = _unread("d0", "do not treat as evidence", "document instruction excluded")
    view = _base_view(unread=(instruction,))
    routed, _ = _route(view, Pattern("likes", (("agent", "Mira"),)))

    assert instruction in routed.unread
    assert instruction.span.text == "do not treat as evidence"


def test_request_without_entity_anchors_keeps_the_flat_view():
    view = _base_view()
    routed, trace = _route(view, Pattern("likes", ()))

    assert routed is None
    assert trace["status"] == "skipped"
    assert trace["reason"] == "request has no entity anchor"


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: whitespace-normalized unread lookup is undone by the exact-text keep filter",
)
def test_whitespace_variant_unread_mention_is_preserved():
    unread = _unread("unread-doc", "Mira No: contradiction here")
    view = _base_view("MiraNo", unread=(unread,))
    routed, _ = _route(view, Pattern("likes", (("agent", "MiraNo"),)))

    assert "unread-doc" in routed.sources
    assert unread in routed.unread
