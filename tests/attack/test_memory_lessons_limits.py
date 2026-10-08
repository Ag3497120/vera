from concurrent.futures import ThreadPoolExecutor
import gc
import tracemalloc

import pytest

from verantyx.memory_lessons import LessonIndex


def lesson(rid, situation, **extra):
    record = {
        "id": rid,
        "kind": "LESSON",
        "slots": {"situation": situation, "lesson": "remember this"},
    }
    record.update(extra)
    return record


def test_empty_and_non_lesson_inputs_abstain():
    index = LessonIndex([None, "not a record", {"id": "fact", "kind": "FACT",
                                                 "slots": {"situation": "black ice"}}])

    assert index.triggers == ()
    assert index.lessons_for("") == []
    assert index.lessons_for("black ice") == []


def test_exact_lookup_returns_only_matching_lessons():
    index = LessonIndex([
        lesson("l-1", "power outage"),
        lesson("l-2", "flat tire"),
        lesson("l-3", "power outage"),
    ])

    assert {record["id"] for record in index.lessons_for("power outage")} == {"l-1", "l-3"}


def test_index_order_does_not_depend_on_input_order():
    records = [lesson("z", "missed train"), lesson("a", "missed train"),
               lesson("m", "missed train")]

    forward = LessonIndex(records).lessons_for("missed train")
    reverse = LessonIndex(list(reversed(records))).lessons_for("missed train")

    assert forward == reverse
    assert {record["id"] for record in forward} == {"a", "m", "z"}


def test_duplicate_ids_are_returned_once_independent_of_input_order():
    first = lesson("same", "route closed", note="first representation")
    second = lesson("same", "route closed", note="second representation")

    result_a = LessonIndex([first, second]).lessons_for("route closed")
    result_b = LessonIndex([second, first]).lessons_for("route closed")

    assert len(result_a) == 1
    assert result_a == result_b


def test_superseded_records_are_excluded():
    older = lesson("old", "broken heater")
    newer = lesson("new", "broken heater", supersedes="old")

    inferred = LessonIndex([older, newer]).lessons_for("broken heater")
    explicit = LessonIndex([older, newer], superseded={"new"}).lessons_for("broken heater")

    assert [record["id"] for record in inferred] == ["new"]
    assert explicit == []


def test_repeated_calls_and_caller_list_mutation_do_not_change_index():
    index = LessonIndex([lesson("l-1", "lost key")])

    first = index.lessons_for("lost key")
    first.clear()

    assert [record["id"] for record in index.lessons_for("lost key")] == ["l-1"]
    assert [record["id"] for record in index.lessons_for("unknown situation")] == []


def test_index_uses_a_snapshot_of_input_records():
    source = lesson("l-1", "frozen pipe")
    index = LessonIndex([source])
    source["slots"]["situation"] = "changed after indexing"
    source["slots"]["lesson"] = "changed text"

    result = index.lessons_for("frozen pipe")
    assert len(result) == 1
    assert result[0]["slots"]["lesson"] == "remember this"


def test_large_finite_index_finds_exact_trigger():
    records = [lesson(f"lesson-{n:05d}", f"situation {n:05d}") for n in range(8000)]
    index = LessonIndex(records)

    result = index.lessons_for("situation 05731")
    assert [record["id"] for record in result] == ["lesson-05731"]
    assert len(index.triggers) == 8000


def test_two_concurrent_readers_get_stable_results():
    index = LessonIndex([lesson(f"l-{n:03d}", "power restored") for n in range(40)])

    def read_many(_):
        return [[record["id"] for record in index.lessons_for("power restored")]
                for _ in range(150)]

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(read_many, range(2)))

    expected = [f"l-{n:03d}" for n in range(40)]
    assert results == [[[*expected] for _ in range(150)] for _ in range(2)]


def test_repeated_lookups_do_not_retain_unbounded_temporary_lists():
    index = LessonIndex([lesson("l-1", "same situation")])
    gc.collect()
    tracemalloc.start()
    before = tracemalloc.get_traced_memory()[0]

    for _ in range(5000):
        index.lessons_for("same situation")
    gc.collect()
    retained = tracemalloc.get_traced_memory()[0] - before
    tracemalloc.stop()

    assert retained < 256_000


def test_malformed_mixed_key_record_does_not_crash():
    index = LessonIndex([{"id": "bad", "kind": "LESSON",
                          "slots": {"situation": "broken route"}, 1: "unexpected key"}])

    assert isinstance(index.lessons_for("broken route"), list)
