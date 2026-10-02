"""Bounded adversarial checks for constructed explanations."""
from __future__ import annotations

import gc
import importlib
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from verantyx import explain as sut


@pytest.fixture
def route(monkeypatch):
    reach_module = importlib.import_module("verantyx.reach")

    def configure(callback, splits=()):
        monkeypatch.setattr(reach_module, "reach", callback)
        monkeypatch.setattr(sut, "_splits_for",
                            lambda model, term: list(splits))

    return configure


def _store(crosses, labels=()):
    return SimpleNamespace(crosses=crosses, source_labels=set(labels))


def _units_route(store, term, model, judge):
    return {"verdict": "UNITS", "term": term}


def test_non_units_route_is_returned_untouched(route):
    result = {"verdict": "CONTAINMENT", "term": "xy", "extra": object()}
    route(lambda store, term, model, judge: result)

    got = sut.explain(None, "xy", model=None, vocab=set())

    assert got is result


@pytest.mark.parametrize("term", ["", "x" * 1_000_000])
def test_unknown_non_units_path_handles_empty_and_huge_terms(route, term):
    result = {"verdict": "UNKNOWN_NO_REACH", "term": term}
    route(lambda store, seen, model, judge: result)

    got = sut.explain(None, term, model=None, vocab=set())

    assert got is result


def test_explanation_is_constructed_and_shared_facets_are_ordered(route):
    facets = {"zeta", "alpha", "middle"}
    store = _store({"a": facets, "bc": set(facets)})
    splits = [{"left": "a", "right": "bc", "at": 1}]
    route(_units_route, splits)

    got = sut.explain(store, "abc", model=object(),
                      vocab={"a", "bc", *facets})

    assert got["verdict"] == "EXPLAINED_BY_UNITS"
    assert got["constructed"] is True
    assert got["crossing"] == ["alpha", "middle", "zeta"]
    assert got["text"].endswith(sut.CONSTRUCTED_MARK)


def test_unworded_crossing_is_not_spoken(route):
    store = _store({"a": {"fragment"}, "bc": {"fragment"}})
    route(_units_route, [{"left": "a", "right": "bc", "at": 1}])

    got = sut.explain(store, "abc", model=object(), vocab={"a", "bc"})

    assert got["crossing"] == ["fragment"]
    assert "fragment" not in got["text"]


def test_crossing_payload_is_bounded_and_labels_are_excluded(route):
    shared = {"facet-%05d" % i for i in range(10_000)}
    store = _store({"a": shared, "bc": shared}, labels={"facet-00000"})
    route(_units_route, [{"left": "a", "right": "bc", "at": 1}])

    got = sut.explain(store, "abc", model=object(), vocab={"a", "bc"})

    assert len(got["crossing"]) == 8
    assert got["crossing"] == sorted(shared - {"facet-00000"})[:8]
    assert not any(facet in got["text"] for facet in got["crossing"])


def test_edges_failure_does_not_change_typed_explanation(route):
    store = _store({"a": {"bc"}})
    route(_units_route, [{"left": "a", "right": "bc", "at": 1}])

    def broken_edges(subject, shown):
        raise RuntimeError("lookup unavailable")

    got = sut.explain(store, "abc", model=object(), vocab={"a", "bc"},
                      edges=broken_edges)

    assert got["verdict"] == "EXPLAINED_BY_UNITS"
    assert got["constructed"] is True
    assert "edge_pairs" not in got


def test_repeated_calls_are_idempotent(route):
    store = _store({"a": {"facet"}, "bc": {"facet"}})
    route(_units_route, [{"left": "a", "right": "bc", "at": 1}])
    args = (store, "abc")
    kwargs = {"model": object(), "vocab": {"a", "bc", "facet"}}

    first = sut.explain(*args, **kwargs)
    second = sut.explain(*args, **kwargs)

    assert first == second


def test_store_insertion_order_does_not_change_explanation(route):
    facets = ["alpha", "middle", "zeta"]
    first_store = _store({"a": set(facets), "bc": set(facets)})
    second_store = _store({"bc": set(reversed(facets)),
                           "a": set(reversed(facets))})
    route(_units_route, [{"left": "a", "right": "bc", "at": 1}])
    kwargs = {"model": object(), "vocab": {"a", "bc", *facets}}

    first = sut.explain(first_store, "abc", **kwargs)
    second = sut.explain(second_store, "abc", **kwargs)

    assert first == second


def test_two_readers_can_explain_independent_stores_concurrently(route,
                                                                 monkeypatch):
    stores = {
        "left": _store({"a": {"shared-left"}, "bc": {"shared-left"}}),
        "right": _store({"d": {"shared-right"}, "ef": {"shared-right"}}),
    }
    splits_by_term = {
        "abc": [{"left": "a", "right": "bc", "at": 1}],
        "def": [{"left": "d", "right": "ef", "at": 1}],
    }
    route(lambda store, term, model, judge: _units_route(store, term, model,
                                                         judge), ())
    # The helper is read-only and keyed only by the term during the overlap.
    monkeypatch.setattr(sut, "_splits_for",
                        lambda model, term: list(splits_by_term[term]))

    def read(term):
        store = stores["left" if term == "abc" else "right"]
        vocab = set(store.crosses) | {"shared-left", "shared-right"}
        return sut.explain(store, term, model=object(), vocab=vocab)

    with ThreadPoolExecutor(max_workers=2) as pool:
        left, right = list(pool.map(read, ("abc", "def")))

    assert left["crossing"] == ["shared-left"]
    assert right["crossing"] == ["shared-right"]


def test_repeated_calls_do_not_retain_unbounded_python_allocations(route):
    store = _store({"a": {"facet"}, "bc": {"facet"}})
    route(_units_route, [{"left": "a", "right": "bc", "at": 1}])
    kwargs = {"model": object(), "vocab": {"a", "bc", "facet"}}
    sut.explain(store, "abc", **kwargs)  # warm imports and one-time setup
    gc.collect()
    tracemalloc.start()
    before = tracemalloc.get_traced_memory()[0]
    for _ in range(1_000):
        sut.explain(store, "abc", **kwargs)
    gc.collect()
    after = tracemalloc.get_traced_memory()[0]
    tracemalloc.stop()

    assert after - before < 256 * 1024
