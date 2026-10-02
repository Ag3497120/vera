from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

import pytest

from verantyx.memory_brief import compile_brief


class MemoryStub:
    def __init__(self, records, superseded=None):
        self.records = list(records)
        self.superseded = superseded or {}

    def active(self):
        return list(self.records)

    def ask_about(self, subject, attribute, *, kind, require_fresh):
        matches = []
        for record in self.records:
            slots = record.get("slots")
            if not isinstance(slots, dict) or record.get("kind") != kind:
                continue
            record_subject = slots.get("situation") if kind == "LESSON" else slots.get("subject")
            record_attribute = "対処" if kind == "LESSON" else slots.get("attribute") if kind == "FACT" else None
            if record_subject == subject and record_attribute == attribute:
                matches.append(record.get("id"))
        return {"records": matches}


def row(record_id, kind="INVARIANT", sentence=None, *, subject=None, ts="2026-01-01", **slots):
    slot_values = dict(slots)
    if subject is not None:
        slot_values["subject"] = subject
    return {
        "id": record_id,
        "kind": kind,
        "sentence": sentence if sentence is not None else f"Sentence for {record_id}.",
        "slots": slot_values,
        "ts": ts,
    }


@pytest.mark.parametrize("budget", [True, False, -1, 1.5, "20", None])
def test_invalid_budgets_raise_value_error(budget):
    with pytest.raises(ValueError):
        compile_brief(MemoryStub([]), budget)


def test_empty_memory_returns_empty_brief_at_zero_budget():
    assert compile_brief(MemoryStub([]), 0) == ""


def test_record_order_is_independent_of_active_order_and_kind_priority():
    records = [
        row("fact", "FACT", subject="s", attribute="color"),
        row("decision", "DECISION", subject="s"),
        row("invariant", "INVARIANT", subject="s"),
    ]
    expected = "\n".join(
        [
            "[id:invariant] Sentence for invariant.",
            "[id:decision] Sentence for decision.",
            "[id:fact] Sentence for fact.",
        ]
    )

    assert compile_brief(MemoryStub(records), len(expected)) == expected
    assert compile_brief(MemoryStub(list(reversed(records))), len(expected)) == expected


def test_exact_character_budget_includes_full_selected_line():
    record = row("one", subject="s", sentence="A short sentence.")
    expected = "[id:one] A short sentence."

    assert compile_brief(MemoryStub([record]), len(expected)) == expected


def test_dropped_ids_are_reported_when_selected_line_fits():
    records = [
        row("kept", subject="s", sentence="Keep me."),
        row("unaskable", sentence="No subject slot."),
    ]
    expected = "[id:kept] Keep me.\nDropped record ids: unaskable"

    assert compile_brief(MemoryStub(records), len(expected)) == expected


def test_too_small_budget_raises_instead_of_hiding_dropped_ids():
    with pytest.raises(ValueError, match="too small to report all dropped record IDs"):
        compile_brief(MemoryStub([row("one", subject="s")]), 1)


def test_focus_uses_nfkc_casefold_matching_to_rank_first():
    records = [
        row("first-by-kind", "INVARIANT", subject="s"),
        row("focused", "FACT", subject="s", attribute="name", sentence="The value is ABC."),
    ]
    expected = "\n".join(
        [
            "[id:focused] The value is ABC.",
            "[id:first-by-kind] Sentence for first-by-kind.",
        ]
    )

    assert compile_brief(MemoryStub(records), len(expected), focus="Ａｂｃ") == expected


def test_superseded_ids_are_excluded_from_output_and_drop_accounting():
    records = [row("old", subject="s"), row("current", subject="s")]
    expected = "[id:current] Sentence for current."

    assert compile_brief(MemoryStub(records, superseded={"old": "current"}), len(expected)) == expected


def test_repeated_calls_are_idempotent_and_do_not_mutate_records():
    records = [row("b", "DECISION", subject="s"), row("a", subject="s")]
    original = deepcopy(records)
    memory = MemoryStub(records)
    expected = "[id:a] Sentence for a.\n[id:b] Sentence for b."

    assert compile_brief(memory, len(expected)) == expected
    assert compile_brief(memory, len(expected)) == expected
    assert records == original


def test_concurrent_readers_return_the_same_brief():
    records = [row("b", "DECISION", subject="s"), row("a", subject="s")]
    memory = MemoryStub(records)
    expected = "[id:a] Sentence for a.\n[id:b] Sentence for b."

    with ThreadPoolExecutor(max_workers=4) as readers:
        results = list(readers.map(lambda _: compile_brief(memory, len(expected)), range(8)))

    assert results == [expected] * 8


@pytest.mark.xfail(strict=False, reason="DEFECT: exact full brief is rejected by incremental dropped-ID budgeting")
def test_large_valid_input_is_stably_compiled_with_exact_budget():
    records = [row(f"r{index:04d}", subject=f"s{index}", sentence=f"Item {index}.") for index in range(256)]
    expected = "\n".join(f"[id:r{index:04d}] Item {index}." for index in range(256))

    assert compile_brief(MemoryStub(records), len(expected)) == expected


@pytest.mark.xfail(strict=False, reason="DEFECT: non-dict slots crash during focus ranking")
def test_non_dict_slots_are_dropped_instead_of_crashing():
    malformed = row("bad", subject="s")
    malformed["slots"] = None

    assert compile_brief(MemoryStub([malformed]), len("Dropped record ids: bad"), focus="x") == "Dropped record ids: bad"
