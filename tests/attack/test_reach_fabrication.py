"""Adversarial provenance checks for compositional reach."""

from types import SimpleNamespace

import pytest

from verantyx import reach
from verantyx import granularity


class Store:
    def __init__(self, crosses=None, source_labels=None):
        self.crosses = crosses or {}
        self.source_labels = set(source_labels or ())


class Judge:
    def __init__(self, result):
        self.result = result
        self.queries = []

    def ask(self, query):
        self.queries.append(query)
        return self.result


def unit_model(monkeypatch, *, left=(), right=(), splits=((1, 1),)):
    monkeypatch.setattr(granularity, "SPLITS", {2: splits})
    return SimpleNamespace(slots={(1, "L"): set(left),
                                  (1, "R"): set(right)})


def test_exact_core_is_held_before_fallbacks():
    store = Store({"AB": ["core"]})
    judge = Judge({"verdict": "ANSWER", "item": "ABCD"})

    result = reach.reach(store, "AB", judge=judge)

    assert result["verdict"] == "HELD"
    assert result["item"] == "AB"
    assert judge.queries == []


def test_source_label_is_not_a_held_core():
    store = Store({"AB": ["label"]}, source_labels={"AB"})

    result = reach.reach(store, "AB")

    assert result["verdict"] == "UNKNOWN_NO_REACH"
    assert result["item"] is None


def test_units_use_the_attested_right_slot(monkeypatch):
    model = unit_model(monkeypatch, left={"A"}, right={"B"})
    store = Store({"A": ["left core"], "B": ["right core"]})

    result = reach.reach(store, "AB", model=model)

    assert result["verdict"] == "UNITS"
    assert result["item"] == "B"


def test_units_do_not_accept_parts_in_the_opposite_roles(monkeypatch):
    model = unit_model(monkeypatch, left={"B"}, right={"A"})
    store = Store({"B": ["left core"], "A": ["right core"]})

    result = reach.reach(store, "AB", model=model)

    assert result["verdict"] == "UNKNOWN_NO_REACH"
    assert result["item"] is None


def test_labeled_fragment_cannot_support_a_unit_answer(monkeypatch):
    model = unit_model(monkeypatch, left={"A"}, right={"B"})
    store = Store({"B": ["label record"]}, source_labels={"B"})

    result = reach.reach(store, "AB", model=model)

    assert result["verdict"] == "UNKNOWN_NO_REACH"


def test_richest_attested_unit_is_selected(monkeypatch):
    model = unit_model(monkeypatch, left={"A"}, right={"B"})
    store = Store({"B": ["one"], "A": ["one", "two", "three"]})

    assert reach.by_units(store, model, "AB") == "A"


def test_units_route_precedes_containment(monkeypatch):
    model = unit_model(monkeypatch, left={"A"}, right={"B"})
    store = Store({"B": ["core"]})

    class UnusedJudge:
        def ask(self, query):
            raise AssertionError("containment ran before the attested unit")

    result = reach.reach(store, "AB", model=model, judge=UnusedJudge())

    assert result["verdict"] == "UNITS"
    assert result["item"] == "B"


def test_containment_forwards_a_held_containing_item():
    store = Store({"ABCD": ["core"]})
    judge = Judge({"verdict": "ANSWER", "item": "ABCD",
                   "agreeing": ["record-1"]})

    result = reach.reach(store, "AB", judge=judge)

    assert result["verdict"] == "CONTAINMENT"
    assert result["item"] == "ABCD"
    assert result["agreeing"] == ["record-1"]
    assert judge.queries == ["ABとは"]


def test_non_answer_judgment_does_not_become_containment():
    store = Store({"ABCD": ["core"]})
    judge = Judge({"verdict": "UNKNOWN", "item": "ABCD"})

    result = reach.reach(store, "AB", judge=judge)

    assert result["verdict"] == "UNKNOWN_NO_REACH"
    assert result["item"] is None


def test_build_model_excludes_source_labels(monkeypatch):
    seen = []

    def capture(cores):
        seen.extend(cores)
        return "model"

    monkeypatch.setattr(granularity, "decompose_units", capture)
    store = Store({"core": ["r1"], "label": ["r2"]},
                  source_labels={"label"})

    assert reach.build_model(store) == "model"
    assert seen == ["core"]


@pytest.mark.xfail(strict=False,
                   reason="DEFECT: containment ANSWER items are not checked against held containing cores")
def test_containment_cannot_fabricate_an_unheld_noncontaining_item():
    store = Store()
    judge = Judge({"verdict": "ANSWER", "item": "UNRELATED",
                   "agreeing": ["unsupported-record"]})
    expected = {"verdict": "UNKNOWN_NO_REACH", "term": "AB", "item": None,
                "note": "the term does not decompose into anything the corpus "
                        "attests and no held word contains it"}

    results = [reach.reach(store, "AB", judge=judge) for _ in range(2)]

    assert results == [expected, expected]
