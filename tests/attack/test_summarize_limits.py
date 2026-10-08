from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import gc
import tracemalloc

import pytest

from verantyx.summarize import summarize


class Store:
    def __init__(self, crosses, source_labels=()):
        self.crosses = crosses
        self.source_labels = set(source_labels)


def lookup_for(licenses):
    def lookup(subject, facets):
        return licenses.get(subject, [])

    return lookup


def two_path_store():
    return Store({"A": {"x": 2, "y": 3}, "B": {"x": 5, "y": 7}})


def test_fewer_than_two_held_paths_is_a_typed_refusal():
    store = Store({"A": {"x": 1, "y": 1}})

    empty = summarize(store, [], vocab={"A", "x", "y"},
                      edges=lookup_for({"A": [("x", "y")]}))
    result = summarize(store, ["A", "missing"], vocab={"A", "x", "y"},
                       edges=lookup_for({"A": [("x", "y")]}))

    assert empty["verdict"] == "UNKNOWN_TOO_FEW_PATHS"
    assert result["verdict"] == "UNKNOWN_TOO_FEW_PATHS"
    assert result["held"] == ["A"]
    assert result["dropped_subjects"] == ["missing"]


def test_disjoint_paths_are_a_typed_no_crossing_refusal():
    store = Store({"A": {"x": 1}, "B": {"y": 1}})

    result = summarize(store, ["A", "B"], vocab={"A", "B", "x", "y"},
                       edges=lookup_for({"A": [("x", "y")]}))

    assert result["verdict"] == "UNKNOWN_NO_CROSSING"
    assert result["held"] == ["A", "B"]


def test_missing_edge_reader_is_a_typed_refusal():
    result = summarize(two_path_store(), ["A", "B"],
                       vocab={"A", "B", "x", "y"}, edges=None)

    assert result["verdict"] == "UNKNOWN_NO_EDGE_LICENSE"
    assert result["crossing"] == 2


def test_edge_reader_exception_becomes_typed_silence():
    def broken_reader(subject, facets):
        raise OSError("sidecar unavailable")

    result = summarize(two_path_store(), ["A", "B"],
                       vocab={"A", "B", "x", "y"}, edges=broken_reader)

    assert result["verdict"] == "UNKNOWN_NO_EDGE_LICENSE"
    assert result["crossing"] == 2


def test_subject_and_facet_vocabulary_gate_speech():
    result = summarize(two_path_store(), ["A", "B"], vocab={"x", "y"},
                       edges=lookup_for({"A": [("x", "y")]}))

    assert result["verdict"] == "UNKNOWN_NO_EDGE_LICENSE"
    assert result["held"] == ["A", "B"]


def test_only_edge_licensed_claims_are_emitted_with_contract_counts():
    result = summarize(two_path_store(), ["A", "B"],
                       vocab={"A", "B", "x", "y"},
                       edges=lookup_for({"A": [("x", "y")]}))

    assert result["verdict"] == "SUMMARY"
    assert result["crossing"] == 2
    assert result["licensed"] == 1
    assert result["kept"] == [
        {"subject": "A", "pair": ["x", "y"], "width": 4, "mass": 5}
    ]
    assert result["text"] == "A: x と y（同一文）。"


def test_limit_drops_a_whole_tied_rank_group():
    store = Store({
        "A": {"x": 1, "y": 1}, "B": {"x": 1, "y": 1},
        "C": {"x": 2, "y": 2}, "D": {"x": 3, "y": 3},
    })
    subjects = ["A", "B", "C", "D"]
    licenses = {subject: [("x", "y")] for subject in subjects}

    result = summarize(store, subjects, vocab=set(subjects) | {"x", "y"},
                       edges=lookup_for(licenses), limit=3)

    assert result["licensed"] == 4
    assert [claim["subject"] for claim in result["kept"]] == ["D", "C"]
    assert result["dropped_at_cut"] == 2


def test_zero_limit_drops_every_claim_without_splitting_a_group():
    result = summarize(two_path_store(), ["A", "B"],
                       vocab={"A", "B", "x", "y"},
                       edges=lookup_for({"A": [("x", "y")],
                                         "B": [("x", "y")]}),
                       limit=0)

    assert result["verdict"] == "SUMMARY"
    assert result["licensed"] == 2
    assert result["kept"] == []
    assert result["dropped_at_cut"] == 2


def test_claim_selection_is_independent_of_path_and_edge_iteration_order():
    store = Store({
        "A": {"x": 1, "y": 1, "z": 1},
        "B": {"x": 1, "y": 1, "z": 1},
    })
    vocab = {"A", "B", "x", "y", "z"}
    forward = {"A": [("x", "y"), ("x", "z")], "B": [("y", "z")]}
    reverse = {"A": [("x", "z"), ("x", "y")], "B": [("y", "z")]}

    first = summarize(store, ["A", "B"], vocab=vocab,
                      edges=lookup_for(forward), limit=3)
    second = summarize(store, ["B", "A"], vocab=vocab,
                       edges=lookup_for(reverse), limit=3)

    stable_fields = ("crossing", "licensed", "kept", "dropped_at_cut", "text")
    assert {key: first[key] for key in stable_fields} == {
        key: second[key] for key in stable_fields
    }
    assert [claim["pair"] for claim in first["kept"]] == [
        ["x", "y"], ["x", "z"], ["y", "z"]
    ]


def test_repeated_calls_are_idempotent_and_do_not_mutate_inputs():
    store = two_path_store()
    subjects = ["A", "B"]
    vocab = {"A", "B", "x", "y"}
    licenses = {"A": [("x", "y")], "B": [("x", "y")]}
    before_crosses = {subject: counts.copy()
                      for subject, counts in store.crosses.items()}

    first = summarize(store, subjects, vocab=vocab,
                      edges=lookup_for(licenses), limit=1)
    second = summarize(store, subjects, vocab=vocab,
                       edges=lookup_for(licenses), limit=1)

    assert first == second
    assert store.crosses == before_crosses


def test_two_concurrent_readers_return_identical_results():
    store = two_path_store()
    vocab = {"A", "B", "x", "y"}
    lookup = lookup_for({"A": [("x", "y")], "B": [("x", "y")]})
    start = Barrier(2)

    def reader():
        start.wait(timeout=2)
        return [summarize(store, ["A", "B"], vocab=vocab, edges=lookup)
                for _ in range(40)]

    with ThreadPoolExecutor(max_workers=2) as pool:
        left = pool.submit(reader)
        right = pool.submit(reader)
        left_results = left.result(timeout=5)
        right_results = right.result(timeout=5)

    assert left_results == right_results
    assert all(result == left_results[0] for result in left_results)


def test_many_repeated_calls_do_not_retain_unreturned_summaries():
    store = two_path_store()
    vocab = {"A", "B", "x", "y"}
    lookup = lookup_for({"A": [("x", "y")]})
    tracemalloc.start()
    try:
        for _ in range(10):
            summarize(store, ["A", "B"], vocab=vocab, edges=lookup)
        gc.collect()
        before, _ = tracemalloc.get_traced_memory()
        for _ in range(1000):
            summarize(store, ["A", "B"], vocab=vocab, edges=lookup)
        gc.collect()
        after, _ = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert after - before < 128 * 1024


def test_large_equal_rank_input_is_bounded_by_group_drop():
    size = 1024
    subjects = ["s%04d" % index for index in range(size)]
    store = Store({subject: {"x": 1, "y": 1} for subject in subjects})
    vocab = set(subjects) | {"x", "y"}
    lookup = lookup_for({subject: [("x", "y")] for subject in subjects})

    result = summarize(store, subjects, vocab=vocab, edges=lookup, limit=5)

    assert result["licensed"] == size
    assert result["kept"] == []
    assert result["dropped_at_cut"] == size


@pytest.mark.xfail(strict=False,
                   reason="DEFECT: duplicate subject IDs count as multiple crossing paths")
def test_duplicate_subject_id_does_not_create_a_second_path():
    store = Store({"A": {"x": 1, "y": 1}})

    result = summarize(store, ["A", "A"], vocab={"A", "x", "y"},
                       edges=lookup_for({"A": [("x", "y")]}))

    assert result["verdict"] == "UNKNOWN_TOO_FEW_PATHS"


@pytest.mark.xfail(strict=False,
                   reason="DEFECT: malformed edge pair escapes as ValueError")
def test_malformed_edge_record_does_not_crash_the_reader():
    result = summarize(two_path_store(), ["A", "B"],
                       vocab={"A", "B", "x", "y"},
                       edges=lookup_for({"A": [("x",)]}))

    assert result["verdict"] == "UNKNOWN_NO_EDGE_LICENSE"
