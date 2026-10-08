"""Differential checks for exact, normalized LESSON trigger lookup."""

from copy import deepcopy
from itertools import product

from verantyx.memory_lessons import LessonIndex, lessons_for, normalize_trigger


def _reference_key(value):
    """Reference normalization for the canonical lowercase labels generated here."""
    return " ".join(value.split()) if isinstance(value, str) else ""


def _reference_lookup(records, situation):
    """Naive index for plain record lists and canonical trigger labels."""
    trigger = _reference_key(situation)
    if not trigger:
        return []

    dead = {record.get("supersedes") for record in records
            if isinstance(record, dict) and record.get("supersedes")}
    by_id = {}
    for record in records:
        if not isinstance(record, dict) or record.get("kind") != "LESSON":
            continue
        rid = record.get("id")
        slots = record.get("slots")
        phrase = slots.get("situation") if isinstance(slots, dict) else None
        key = _reference_key(phrase)
        if rid and rid not in dead and key == trigger and rid not in by_id:
            by_id[rid] = deepcopy(record)
    return [by_id[rid] for rid in sorted(by_id)]


def _lesson(rid, situation, **extra):
    record = {
        "id": rid,
        "kind": "LESSON",
        "slots": {"situation": situation, "lesson": f"note for {rid}"},
    }
    record.update(extra)
    return record


def test_generated_canonical_records_match_independent_reference():
    triggers = ("alarm", "arrival", "repair")
    records = []
    for n, (trigger, kind) in enumerate(product(triggers, ("LESSON", "FACT"))):
        records.append({
            "id": f"item-{n}",
            "kind": kind,
            "slots": {"situation": trigger, "lesson": f"note-{n}"},
        })

    for query in (*triggers, "unseen"):
        assert lessons_for(records, query) == _reference_lookup(records, query)


def test_exact_trigger_returns_all_matching_lessons_in_id_order():
    records = [_lesson("z-last", "alarm"), _lesson("a-first", "alarm")]
    assert [row["id"] for row in lessons_for(records, "alarm")] == ["a-first", "z-last"]


def test_non_lesson_records_are_not_indexed():
    records = [_lesson("lesson", "alarm"), {"id": "fact", "kind": "FACT",
                                               "slots": {"situation": "alarm"}}]
    assert [row["id"] for row in lessons_for(records, "alarm")] == ["lesson"]


def test_records_without_id_or_situation_are_not_indexed():
    records = [
        {"kind": "LESSON", "slots": {"situation": "alarm"}},
        {"id": "no-situation", "kind": "LESSON", "slots": {"lesson": "text"}},
        _lesson("valid", "alarm"),
    ]
    assert [row["id"] for row in lessons_for(records, "alarm")] == ["valid"]


def test_explicitly_superseded_ids_are_omitted():
    records = [_lesson("old", "alarm"), _lesson("current", "alarm")]
    assert [row["id"] for row in lessons_for(records, "alarm", superseded={"old"})] == ["current"]


def test_supersedes_slot_marks_the_old_id_dead():
    records = [_lesson("old", "alarm"), _lesson("new", "alarm", supersedes="old")]
    assert [row["id"] for row in lessons_for(records, "alarm")] == ["new"]


def test_duplicate_ids_are_returned_once():
    records = [_lesson("same", "alarm", detail="first"),
               _lesson("same", "alarm", detail="second")]
    assert len(lessons_for(records, "alarm")) == 1


def test_unmatched_trigger_without_asker_abstains():
    assert lessons_for([_lesson("known", "alarm")], "arrival") == []


def test_empty_and_non_string_situations_abstain():
    index = LessonIndex([_lesson("known", "alarm")])
    assert index.lessons_for("") == []
    assert index.lessons_for(None) == []
    assert normalize_trigger(None) == ""
    assert normalize_trigger(42) == ""


def test_returned_list_is_separate_from_index_membership():
    index = LessonIndex([_lesson("known", "alarm")])
    first = index.lessons_for("alarm")
    first.clear()
    assert [row["id"] for row in index.lessons_for("alarm")] == ["known"]
