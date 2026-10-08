from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from verantyx.writer import Writer


class UnreadableStore:
    @property
    def crosses(self):
        raise AssertionError("unknown subject should be refused before store access")

    @property
    def source_labels(self):
        raise AssertionError("unknown subject should be refused before store access")


def known_subject_writer():
    writer = Writer()
    writer.vocab.attested = {"猫": {"test": 1}}
    return writer


def small_store():
    return SimpleNamespace(crosses={"猫": {"走る": 1}}, source_labels=set())


def test_empty_build_has_no_corpora_or_forms():
    writer = Writer.build([], [])

    assert writer.forms == {}
    assert writer.built["corpora"] == {}
    assert writer.built["forms"] == 0


def test_unknown_subject_returns_empty_before_reading_store():
    assert Writer().sentence(UnreadableStore(), "未知") == []


def test_very_large_unknown_subject_is_refused():
    subject = "x" * (2 * 1024 * 1024)

    assert Writer().sentence(UnreadableStore(), subject) == []


def test_zero_sentence_budget_returns_no_sentences():
    assert known_subject_writer().sentence(small_store(), "猫", limit=0) == []


def test_huge_sentence_budget_with_no_forms_returns_no_sentences():
    assert known_subject_writer().sentence(
        small_store(), "猫", limit=10**12
    ) == []


def test_repeated_sentence_calls_are_idempotent():
    writer = known_subject_writer()
    store = small_store()

    first = writer.sentence(store, "猫")
    second = writer.sentence(store, "猫")

    assert first == second == []
    assert writer.forms == {}


def test_two_writers_can_be_read_concurrently():
    readers = [Writer(), known_subject_writer()]
    requests = [(readers[0], "missing", UnreadableStore())] * 40
    requests += [(readers[1], "猫", small_store())] * 40

    def read(request):
        writer, subject, store = request
        return writer.sentence(store, subject)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(read, requests))

    assert len(results) == len(requests)
    assert all(result == [] for result in results)


def test_repeated_unknown_reads_do_not_grow_writer_state():
    writer = Writer.build([], [])
    built_before = dict(writer.built)
    forms_before = dict(writer.forms)
    vocabulary_before = dict(writer.vocab.attested)
    store = UnreadableStore()

    for _ in range(2000):
        assert writer.sentence(store, "absent") == []

    assert writer.built == built_before
    assert writer.forms == forms_before
    assert writer.vocab.attested == vocabulary_before


def test_empty_passage_has_consistent_written_and_skipped_counts():
    writer = Writer.build([], [])
    store = SimpleNamespace(crosses={"seed": {}}, source_labels=set())

    result = writer.passage(store, "seed", steps=0)

    assert result["seed"] == "seed"
    assert result["sentences"] == []
    assert result["written"] == 0
    assert result["skipped"] == len(result["path"])


def test_empty_build_is_independent_of_empty_input_order():
    first = Writer.build(iter(()), [("left", ""), ("right", "")])
    second = Writer.build(iter(()), [("right", ""), ("left", "")])

    assert first.forms == second.forms == {}
    assert first.built["corpora"] == second.built["corpora"] == {
        "left": 0,
        "right": 0,
    }
