"""Independent limit and determinism probes for the semantic leaf router."""

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

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
from verantyx.semantic_route import LeafTree, ROUTE_MIN_LEAVES


def _view(count=7, terms_by_doc=None, unread_by_doc=None, reverse=False):
    names = [f"doc-{i}" for i in range(count)]
    terms_by_doc = terms_by_doc or {
        name: [f"entity-{i}"] for i, name in enumerate(names)
    }
    unread_by_doc = unread_by_doc or {}
    sources = {name: f"text for {name}" for name in names}
    clauses = []
    for i, name in enumerate(names):
        for j, term in enumerate(terms_by_doc.get(name, ())):
            text = str(term)
            span = Span(name, j, j + len(text), text)
            clauses.append(
                Clause(
                    f"{name}-{j}",
                    Variable(f"event-{i}-{j}"),
                    "likes",
                    span,
                    (Role("owner", term, span),),
                    span,
                )
            )
    unread = []
    for name, texts in unread_by_doc.items():
        for j, text in enumerate(texts):
            unread.append(Unread(Span(name, j, j + len(text), text), "unread"))
    if reverse:
        clauses.reverse()
        unread.reverse()
        sources = dict(reversed(tuple(sources.items())))
    return View(sources, tuple(clauses), tuple(unread))


def _request(*terms):
    pattern = Pattern("likes", tuple(("owner", term) for term in terms))
    node = Operator("bind", "Bind", pattern=pattern)
    return Request("who likes", (Plan((node,), "bind"),), (), ())


def _stable(result):
    routed, trace = result
    return routed, {key: value for key, value in trace.items() if key != "route_ms"}


def test_empty_view_is_skipped_without_crashing():
    routed, trace = LeafTree(View({}, ())).restrict(_request("Ada"))

    assert routed is None
    assert trace["status"] == "skipped"
    assert trace["reason"] == "fewer leaves than one routing node"


def test_view_below_minimum_leaf_count_is_left_flat():
    view = _view(ROUTE_MIN_LEAVES - 1)
    routed, trace = LeafTree(view).restrict(_request("Ada"))

    assert routed is None
    assert trace["leaves"] == ROUTE_MIN_LEAVES - 1
    assert trace["status"] == "skipped"


def test_nominal_only_pattern_has_no_literal_anchor_and_is_skipped():
    view = _view()
    request = _request(Nominal("Ada", Variable("person")))
    routed, trace = LeafTree(view).restrict(request)

    assert routed is None
    assert trace["status"] == "skipped"
    assert trace["reason"] == "request has no entity anchor"


def test_every_document_holding_the_anchor_survives_routing():
    view = _view(
        terms_by_doc={
            "doc-0": ["Ada"],
            "doc-1": ["Bert"],
            "doc-2": ["Cora"],
            "doc-3": ["Ada"],
            "doc-4": ["Eli"],
            "doc-5": ["Fay"],
            "doc-6": ["Gus"],
        }
    )
    routed, trace = LeafTree(view).restrict(_request("Ada"))

    assert trace["status"] == "routed"
    assert set(routed.sources) == {"doc-0", "doc-3"}
    assert {clause.span.source for clause in routed.clauses} == {"doc-0", "doc-3"}
    assert set(routed.sources) <= set(view.sources)


def test_unread_text_mention_keeps_its_document_in_the_view():
    view = _view(
        terms_by_doc={
            "doc-0": ["Ada"],
            **{f"doc-{i}": [f"entity-{i}"] for i in range(1, 7)},
        },
        unread_by_doc={"doc-1": ["Opaque Ada note"]},
    )
    routed, trace = LeafTree(view).restrict(_request("Ada"))

    assert trace["status"] == "routed"
    assert "doc-0" in routed.sources
    assert "doc-1" in routed.sources
    assert [item.span.text for item in routed.unread] == ["Opaque Ada note"]


def test_routing_is_independent_of_document_input_order():
    terms = {
        "doc-0": ["Ada"],
        "doc-1": ["Bert"],
        "doc-2": ["Cora"],
        "doc-3": ["Ada"],
        "doc-4": ["Eli"],
        "doc-5": ["Fay"],
        "doc-6": ["Gus"],
    }
    request = _request("Ada")
    first = LeafTree(_view(terms_by_doc=terms)).restrict(request)
    reversed_input = LeafTree(_view(terms_by_doc=terms, reverse=True)).restrict(request)

    assert _stable(first) == _stable(reversed_input)


def test_repeated_calls_return_the_same_routed_view_and_trace():
    tree = LeafTree(
        _view(
            terms_by_doc={
                "doc-0": ["Ada"],
                "doc-1": ["Bert"],
                "doc-2": ["Cora"],
                "doc-3": ["Ada"],
                "doc-4": ["Eli"],
                "doc-5": ["Fay"],
                "doc-6": ["Gus"],
            }
        )
    )

    assert _stable(tree.restrict(_request("Ada"))) == _stable(
        tree.restrict(_request("Ada"))
    )


def test_restricting_an_already_routed_view_is_idempotent():
    view = _view(9, {f"doc-{i}": ["Ada"] for i in range(9)})
    request = _request("Ada")
    routed, trace = LeafTree(view).restrict(request)

    assert trace["status"] == "routed"
    rerouted, reroute_trace = LeafTree(routed).restrict(request)

    assert reroute_trace["status"] == "routed"
    assert rerouted == routed


def test_two_concurrent_readers_match_serial_results():
    view = _view(
        10,
        {
            "doc-0": ["Ada"],
            "doc-1": ["Bob"],
            **{f"doc-{i}": [f"entity-{i}"] for i in range(2, 10)},
        },
    )
    tree = LeafTree(view)
    requests = {"Ada": _request("Ada"), "Bob": _request("Bob")}
    serial = {key: _stable(tree.restrict(request)) for key, request in requests.items()}

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {
            key: pool.submit(tree.restrict, request)
            for key, request in requests.items()
        }
        concurrent = {key: _stable(future.result()) for key, future in futures.items()}

    assert concurrent == serial


def test_anchor_cap_is_inclusive_and_overflow_keeps_the_flat_view():
    request = _request("Ada")
    at_cap = _view(128, {f"doc-{i}": ["Ada"] for i in range(128)})
    over_cap = _view(129, {f"doc-{i}": ["Ada"] for i in range(129)})

    routed, trace = LeafTree(at_cap).restrict(request)
    skipped, overflow_trace = LeafTree(over_cap).restrict(request)

    assert trace["status"] == "routed"
    assert len(routed.sources) == 128
    assert skipped is None
    assert overflow_trace["status"] == "skipped"
    assert overflow_trace["reason"] == "every anchor of a pattern is common"


def test_256_document_view_routes_to_all_anchor_holders():
    terms = {f"doc-{i}": [f"entity-{i}"] for i in range(256)}
    terms["doc-0"] = ["Ada"]
    terms["doc-255"] = ["Ada"]
    routed, trace = LeafTree(_view(256, terms)).restrict(_request("Ada"))

    assert trace["status"] == "routed"
    assert set(routed.sources) == {"doc-0", "doc-255"}


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: arity=1 makes LeafTree construction fail to terminate",
)
def test_degenerate_arity_finishes_or_is_rejected_promptly():
    code = '''
from verantyx.semantic_ir import Clause, Role, Span, Variable, View
from verantyx.semantic_route import LeafTree
clauses = []
sources = {}
for i in range(7):
    source = "doc-" + str(i)
    span = Span(source, 0, 1, source)
    sources[source] = source
    clauses.append(Clause(source, Variable("e" + str(i)), "likes", span,
                          (Role("owner", source, span),), span))
LeafTree(View(sources, tuple(clauses)), arity=1)
'''
    try:
        result = subprocess.run(
            [sys.executable, "-B", "-c", code],
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=2,
        )
    except subprocess.TimeoutExpired:
        pytest.fail("LeafTree(..., arity=1) did not finish within two seconds")

    assert result.returncode == 0, result.stderr
