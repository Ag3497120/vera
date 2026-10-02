"""Adversarial provenance checks for the typed memory brief compiler."""

import pytest

from verantyx.memory_brief import compile_brief


class _TypedMemory:
    """Small public-path double that returns IDs only for supported questions."""

    def __init__(self, records, *, answerable=None, superseded=None):
        self._records = list(records)
        self._answerable = ({str(record["id"]) for record in records}
                            if answerable is None else set(answerable))
        self.superseded = superseded or {}

    def active(self):
        return list(self._records)

    def ask_about(self, subject, attribute=None, *, kind="FACT", require_fresh=True):
        sources = []
        for record in self._records:
            slots = record.get("slots", {})
            rid = str(record.get("id", ""))
            expected_subject = slots.get("situation") if kind == "LESSON" else slots.get("subject")
            expected_attribute = slots.get("attribute") if kind == "FACT" else (
                "対処" if kind == "LESSON" else None
            )
            if (rid in self._answerable and record.get("kind") == kind
                    and expected_subject == subject and expected_attribute == attribute):
                sources.append(rid)
        return {"records": sources}


def _fact(rid, subject, attribute, sentence, ts="2026-01-01"):
    return {
        "id": rid,
        "kind": "FACT",
        "ts": ts,
        "sentence": sentence,
        "slots": {"subject": subject, "attribute": attribute},
    }


def _brief(memory, budget=1000, focus=None):
    return compile_brief(memory, budget, focus=focus)


def test_supported_record_is_rendered_verbatim_with_its_id():
    record = _fact("r1", "Aya", "mobility", "Aya uses a cane.")

    assert _brief(_TypedMemory([record])) == "[id:r1] Aya uses a cane."


def test_negation_in_supported_sentence_is_preserved_verbatim():
    record = _fact("r1", "Aya", "mobility", "Aya does not use a cane.")

    assert _brief(_TypedMemory([record])) == "[id:r1] Aya does not use a cane."


def test_same_attribute_for_two_entities_keeps_each_source_attached():
    alice = _fact("alice-home", "Alice", "home", "Alice lives in Kyoto.", "2026-01-01")
    bob = _fact("bob-home", "Bob", "home", "Bob lives in Sapporo.", "2026-01-02")

    assert _brief(_TypedMemory([alice, bob])) == (
        "[id:alice-home] Alice lives in Kyoto.\n[id:bob-home] Bob lives in Sapporo."
    )


def test_record_without_ask_path_source_is_dropped_and_accounted_for():
    unsupported = _fact("forged", "Aya", "employer", "Aya works at Acme.")

    assert _brief(_TypedMemory([unsupported], answerable=set())) == (
        "Dropped record ids: forged"
    )


def test_lesson_uses_its_situation_and_response_role_for_source_check():
    lesson = {
        "id": "lesson1",
        "kind": "LESSON",
        "ts": "2026-01-01",
        "sentence": "When the train is delayed, Aya checks the station board.",
        "slots": {"situation": "train delay", "action": "check station board"},
    }

    assert _brief(_TypedMemory([lesson])) == (
        "[id:lesson1] When the train is delayed, Aya checks the station board."
    )


def test_superseded_record_is_not_rendered_or_counted_as_active_input():
    old = _fact("old", "Aya", "city", "Aya lives in Osaka.", "2025-01-01")
    current = _fact("current", "Aya", "city", "Aya lives in Kobe.", "2026-01-01")
    memory = _TypedMemory([old, current], superseded={"old": "current"})

    assert _brief(memory) == "[id:current] Aya lives in Kobe."


def test_closed_task_is_not_emitted_and_its_id_is_reported():
    task = {
        "id": "task1",
        "kind": "TASK",
        "ts": "2026-01-01",
        "sentence": "Submit the application.",
        "slots": {"subject": "Aya", "state": "completed"},
    }

    assert _brief(_TypedMemory([task])) == "Dropped record ids: task1"


def test_budget_can_fit_drop_accounting_without_partial_record_text():
    record = _fact("r1", "Aya", "job", "Aya is a research scientist.")
    budget = len("Dropped record ids: r1")

    assert _brief(_TypedMemory([record]), budget=budget) == "Dropped record ids: r1"


def test_budget_too_small_to_report_dropped_ids_raises():
    record = _fact("r1", "Aya", "job", "Aya is a research scientist.")
    budget = len("Dropped record ids: r1") - 1

    with pytest.raises(ValueError, match="too small to report all dropped record IDs"):
        _brief(_TypedMemory([record]), budget=budget)


def test_focus_changes_order_without_changing_supported_sentences():
    work = _fact("work", "Aya", "job", "Aya is a researcher.", "2026-01-01")
    home = _fact("home", "Aya", "city", "Aya lives in Kyoto.", "2026-01-02")

    assert _brief(_TypedMemory([work, home]), focus="Kyoto") == (
        "[id:home] Aya lives in Kyoto.\n[id:work] Aya is a researcher."
    )


@pytest.mark.parametrize("budget", [True, -1, 1.5, "100"])
def test_invalid_budget_types_and_ranges_are_rejected(budget):
    with pytest.raises(ValueError, match="budget_chars must be a non-negative integer"):
        _brief(_TypedMemory([_fact("r1", "Aya", "city", "Aya lives in Kyoto.")]), budget=budget)
