"""Differential checks for compositional reach using controlled test doubles."""
from itertools import product

import pytest

from verantyx import granularity, reach as reach_module


class Store:
    def __init__(self, crosses=None, source_labels=None):
        self.crosses = crosses or {}
        self.source_labels = source_labels or set()


class Model:
    def __init__(self, slots=None):
        self.slots = slots or {}


class Judge:
    def __init__(self, result):
        self.result = result
        self.questions = []

    def ask(self, question):
        self.questions.append(question)
        return self.result


def naive_units(term, splits, slots):
    """Reference the documented positional-attestation rule, independently."""
    reached = []
    for left_size, right_size in splits.get(len(term), ()):
        left, right = term[:left_size], term[left_size:]
        left_words = slots.get((left_size, "L"), set())
        right_words = slots.get((right_size, "R"), set())
        if left in left_words and right in right_words:
            reached.extend(((right, "R"), (left, "L")))
    return reached


def test_units_for_returns_attested_parts_in_head_final_order(monkeypatch):
    monkeypatch.setattr(granularity, "SPLITS", {4: [(2, 2), (1, 3)]})
    model = Model({(2, "L"): {"ab", "bc"}, (2, "R"): {"cd", "ab"},
                   (1, "L"): {"a"}, (3, "R"): {"bcd"}})

    assert reach_module.units_for(model, "abcd") == [
        ("cd", "R"), ("ab", "L"), ("bcd", "R"), ("a", "L")
    ]


def test_units_for_rejects_a_word_attested_only_in_the_wrong_position(monkeypatch):
    monkeypatch.setattr(granularity, "SPLITS", {4: [(2, 2)]})
    model = Model({(2, "L"): {"ab"}, (2, "R"): {"cd"}})

    assert reach_module.units_for(model, "abcd") == [("cd", "R"), ("ab", "L")]
    model.slots[(2, "R")] = set()
    model.slots[(2, "L")] = {"ab", "cd"}
    assert reach_module.units_for(model, "abcd") == []


def test_units_for_matches_naive_reference_over_generated_strings(monkeypatch):
    splits = {size: [(left, size - left) for left in range(1, size)]
              for size in range(2, 6)}
    monkeypatch.setattr(granularity, "SPLITS", splits)

    for size in range(2, 6):
        for letters in product("abc", repeat=size):
            term = "".join(letters)
            slots = {}
            for left_size, right_size in splits[size]:
                left, right = term[:left_size], term[left_size:]
                # Deterministically vary whether each exact substring is
                # attested, while also allowing strings to recur in slots.
                if (sum(map(ord, left)) + left_size) % 3 != 0:
                    slots.setdefault((left_size, "L"), set()).add(left)
                if (sum(map(ord, right)) + right_size) % 4 != 0:
                    slots.setdefault((right_size, "R"), set()).add(right)
            model = Model(slots)
            assert reach_module.units_for(model, term) == naive_units(term, splits, slots)


def test_by_units_selects_part_with_most_crosses(monkeypatch):
    monkeypatch.setattr(granularity, "SPLITS", {4: [(2, 2)]})
    model = Model({(2, "L"): {"ab"}, (2, "R"): {"cd"}})
    store = Store({"ab": [1], "cd": [1, 2, 3]})

    assert reach_module.by_units(store, model, "abcd") == "cd"


def test_by_units_keeps_first_attested_part_on_tie(monkeypatch):
    monkeypatch.setattr(granularity, "SPLITS", {4: [(2, 2)]})
    model = Model({(2, "L"): {"ab"}, (2, "R"): {"cd"}})
    store = Store({"ab": [1, 2], "cd": [3, 4]})

    assert reach_module.by_units(store, model, "abcd") == "cd"


def test_source_label_is_not_returned_as_held_or_unit(monkeypatch):
    monkeypatch.setattr(granularity, "SPLITS", {4: [(2, 2)]})
    model = Model({(2, "L"): {"ab"}, (2, "R"): {"cd"}})
    store = Store({"abcd": [1], "ab": [2], "cd": [3]}, {"abcd", "cd"})

    assert reach_module.reach(store, "abcd", model=model) == {
        "verdict": "UNITS", "term": "abcd", "item": "ab",
        "note": "the corpus splits this term where its own vocabulary "
                "splits; the part is a word it writes, not a fragment",
    }


def test_reach_returns_held_before_consulting_other_routes(monkeypatch):
    monkeypatch.setattr(granularity, "SPLITS", {4: [(2, 2)]})
    model = Model({(2, "L"): {"ab"}, (2, "R"): {"cd"}})
    judge = Judge({"verdict": "ANSWER", "item": "other"})
    store = Store({"abcd": [1], "ab": [2]})

    assert reach_module.reach(store, "abcd", model=model, judge=judge) == {
        "verdict": "HELD", "term": "abcd", "item": "abcd"
    }
    assert judge.questions == []


def test_reach_uses_units_before_containment(monkeypatch):
    monkeypatch.setattr(granularity, "SPLITS", {4: [(2, 2)]})
    model = Model({(2, "L"): {"ab"}, (2, "R"): {"cd"}})
    judge = Judge({"verdict": "ANSWER", "item": "containment"})
    store = Store({"ab": [1]})

    result = reach_module.reach(store, "abcd", model=model, judge=judge)
    assert result["verdict"] == "UNITS"
    assert result["item"] == "ab"
    assert judge.questions == []


def test_reach_reports_containment_answer_and_question(monkeypatch):
    monkeypatch.setattr(granularity, "SPLITS", {})
    judge = Judge({"verdict": "ANSWER_SUPPORTED", "item": "large-term",
                   "agreeing": ["core-1"]})

    result = reach_module.reach(Store(), "small-term", judge=judge)
    assert result["verdict"] == "CONTAINMENT"
    assert result["term"] == "small-term"
    assert result["item"] == "large-term"
    assert result["agreeing"] == ["core-1"]
    assert judge.questions == ["small-termとは"]


@pytest.mark.parametrize("verdict", ["UNKNOWN", "REFUSAL", "", "NO_ANSWER"])
def test_reach_does_not_treat_non_answer_judgment_as_containment(verdict):
    judge = Judge({"verdict": verdict, "item": "must-not-escape"})

    result = reach_module.reach(Store(), "term", judge=judge)
    assert result["verdict"] == "UNKNOWN_NO_REACH"
    assert result["item"] is None
    assert result["term"] == "term"
    assert judge.questions == ["termとは"]


def test_reach_returns_unknown_when_no_route_reaches_term(monkeypatch):
    monkeypatch.setattr(granularity, "SPLITS", {4: [(2, 2)]})
    model = Model({(2, "L"): {"ab"}, (2, "R"): {"cd"}})
    store = Store()

    result = reach_module.reach(store, "abcd", model=model)
    assert result["verdict"] == "UNKNOWN_NO_REACH"
    assert result["item"] is None


def test_build_model_excludes_source_labels(monkeypatch):
    seen = []

    def decompose(terms):
        seen.extend(terms)
        return "model"

    monkeypatch.setattr(granularity, "decompose_units", decompose)
    result = reach_module.build_model(Store({"corpus": [1], "source": [2]}, {"source"}))

    assert result == "model"
    assert seen == ["corpus"]
