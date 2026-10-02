from concurrent.futures import ThreadPoolExecutor
import gc
import tracemalloc

import pytest

from verantyx.reach import by_units, reach, units_for


class Store:
    def __init__(self, crosses=None, source_labels=None):
        self.crosses = {} if crosses is None else crosses
        self.source_labels = set() if source_labels is None else source_labels


class Model:
    def __init__(self, slots=None):
        self.slots = {} if slots is None else slots


class Judge:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def ask(self, question):
        self.calls.append(question)
        return self.result


def split_model():
    # 損害賠償 -> 損害 + 賠償; the right-hand unit is tried first.
    return Model({(2, "L"): {"損害"}, (2, "R"): {"賠償"}})


def test_held_term_is_returned_without_consulting_routes():
    judge = Judge({"verdict": "ANSWER", "item": "unexpected"})
    result = reach(Store({"賠償": ["core"]}), "賠償", model=split_model(), judge=judge)

    assert result == {"verdict": "HELD", "term": "賠償", "item": "賠償"}
    assert judge.calls == []


def test_source_label_is_not_a_held_core_or_unit():
    store = Store({"損害賠償": ["core"], "賠償": ["core"]}, {"損害賠償", "賠償"})

    assert by_units(store, split_model(), "損害賠償") is None
    assert reach(store, "賠償")["verdict"] == "UNKNOWN_NO_REACH"


def test_attested_units_follow_head_final_order():
    store = Store({"損害": ["core-left"], "賠償": ["core-right"]})

    assert units_for(split_model(), "損害賠償") == [("賠償", "R"), ("損害", "L")]
    assert reach(store, "損害賠償", model=split_model())["item"] == "賠償"


def test_richer_attested_unit_wins():
    store = Store({"賠償": ["one"], "損害": ["one", "two"]})

    assert by_units(store, split_model(), "損害賠償") == "損害"


def test_unit_route_precedes_containment_fallback():
    judge = Judge({"verdict": "ANSWER", "item": "fallback"})

    result = reach(
        Store({"賠償": ["core"]}), "損害賠償", model=split_model(), judge=judge
    )

    assert result["verdict"] == "UNITS"
    assert result["item"] == "賠償"
    assert judge.calls == []


def test_answering_judge_is_reported_as_containment():
    judge = Judge({"verdict": "ANSWER_EXACT", "item": "損害賠償", "agreeing": ["a", "b"]})

    result = reach(Store(), "賠償", judge=judge)

    assert result["verdict"] == "CONTAINMENT"
    assert result["item"] == "損害賠償"
    assert result["agreeing"] == ["a", "b"]
    assert judge.calls == ["賠償とは"]


@pytest.mark.parametrize("verdict", ["REFUSE_UNGROUNDED", "UNKNOWN", ""])
def test_non_answering_judge_leaves_term_unknown(verdict):
    result = reach(Store(), "賠償", judge=Judge({"verdict": verdict}))

    assert result["verdict"] == "UNKNOWN_NO_REACH"
    assert result["item"] is None


def test_empty_store_and_empty_term_are_unknown():
    assert reach(Store(), "")["verdict"] == "UNKNOWN_NO_REACH"
    assert reach(Store(), "")["verdict"] == "UNKNOWN_NO_REACH"


def test_large_and_pathological_strings_return_unknown_without_mutation():
    store = Store()
    huge = "語" * (1024 * 1024)
    odd = "\x00\ud800"
    before = (dict(store.crosses), set(store.source_labels))

    assert reach(store, huge)["verdict"] == "UNKNOWN_NO_REACH"
    assert reach(store, odd)["verdict"] == "UNKNOWN_NO_REACH"
    assert (store.crosses, store.source_labels) == before


def test_repeated_unknown_reads_do_not_retain_terms():
    store = Store()
    tracemalloc.start()
    try:
        gc.collect()
        baseline, _ = tracemalloc.get_traced_memory()
        for i in range(2048):
            term = "term-%04d-" % i + "語" * 128
            assert reach(store, term)["verdict"] == "UNKNOWN_NO_REACH"
        gc.collect()
        current, _ = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert current - baseline < 256 * 1024


def test_repeated_calls_are_idempotent_and_do_not_mutate_inputs():
    store = Store({"損害賠償": ["whole"], "賠償": ["part"]})
    model = split_model()
    crosses_before = {key: list(value) for key, value in store.crosses.items()}
    slots_before = {key: set(value) for key, value in model.slots.items()}

    first = reach(store, "損害賠償", model=model)
    second = reach(store, "損害賠償", model=model)

    assert first == second
    assert store.crosses == crosses_before
    assert model.slots == slots_before


def test_selection_is_independent_of_cross_mapping_insertion_order():
    model = split_model()
    forward = Store({"賠償": ["one"], "損害": ["one", "two"]})
    reverse = Store({"損害": ["one", "two"], "賠償": ["one"]})

    assert reach(forward, "損害賠償", model=model) == reach(
        reverse, "損害賠償", model=model
    )


def test_two_readers_can_reach_independently():
    cases = [
        (Store({"賠償": ["one"]}), "損害賠償", split_model(), "UNITS", "賠償"),
        (Store(), "未知語", Model(), "UNKNOWN_NO_REACH", None),
    ]

    def read(case):
        store, term, model, expected_verdict, expected_item = case
        result = reach(store, term, model=model)
        return result["verdict"], result["item"], expected_verdict, expected_item

    with ThreadPoolExecutor(max_workers=2) as readers:
        results = list(readers.map(read, cases * 32))

    assert all((verdict, item) == (expected_verdict, expected_item)
               for verdict, item, expected_verdict, expected_item in results)
