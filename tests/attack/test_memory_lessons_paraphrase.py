import pytest

from verantyx.memory_lessons import LessonIndex, lessons_for


def lesson(rid, situation, text=None):
    return {
        "id": rid,
        "kind": "LESSON",
        "slots": {
            "situation": situation,
            "lesson": text or f"lesson for {situation}",
        },
    }


def ids(records):
    return [record["id"] for record in records]


def test_exact_trigger_returns_its_lesson():
    records = [lesson("L-train-delay", "train delay")]

    assert ids(lessons_for(records, "train delay")) == ["L-train-delay"]


@pytest.mark.xfail(strict=False, reason="DEFECT: case and repeated whitespace variation does not resolve to its known trigger")
def test_case_and_whitespace_variant_keeps_exact_match():
    records = [lesson("L-train-delay", "train delay")]

    assert ids(lessons_for(records, "  TRAIN   DELAY  ")) == ["L-train-delay"]


@pytest.mark.xfail(strict=False, reason="DEFECT: polite request wording does not resolve to its known trigger")
def test_polite_request_variant_keeps_same_situation_verdict():
    records = [lesson("L-train-delay", "train delay")]

    assert ids(lessons_for(records, "Could you advise me about a train delay?")) == ["L-train-delay"]


@pytest.mark.xfail(strict=False, reason="DEFECT: changed word order does not resolve to its known trigger")
def test_word_order_variant_keeps_same_situation_verdict():
    records = [lesson("L-train-delay", "train delay")]

    assert ids(lessons_for(records, "delay on a train")) == ["L-train-delay"]


def test_particle_variant_keeps_same_situation_verdict():
    records = [lesson("L-train-delay", "電車の遅延")]

    assert ids(lessons_for(records, "電車が遅延")) == ["L-train-delay"]


@pytest.mark.xfail(strict=False, reason="DEFECT: singular and plural situation triggers do not share a verdict")
def test_number_variant_keeps_same_situation_verdict():
    records = [lesson("L-lost-key", "lost key")]

    assert ids(lessons_for(records, "lost keys")) == ["L-lost-key"]


@pytest.mark.xfail(strict=False, reason="DEFECT: entity substitution does not resolve to the shared situation lesson")
def test_entity_variant_keeps_same_situation_verdict():
    records = [lesson("L-train-delay", "train delay")]

    assert ids(lessons_for(records, "bus delay")) == ["L-train-delay"]


def test_changed_meaning_uses_only_its_own_trigger():
    records = [
        lesson("L-delay", "train delay"),
        lesson("L-cancellation", "train cancellation"),
    ]

    assert ids(lessons_for(records, "train cancellation")) == ["L-cancellation"]


def test_nearby_but_different_trigger_does_not_leak_a_lesson():
    records = [lesson("L-delay", "train delay")]

    assert lessons_for(records, "train schedule") == []


def test_unmatched_trigger_abstains_without_an_asker():
    records = [lesson("L-delay", "train delay")]

    assert lessons_for(records, "missed connection") == []


def test_empty_situation_abstains():
    records = [lesson("L-delay", "train delay")]

    assert lessons_for(records, "   ") == []


def test_only_lesson_records_are_indexed():
    records = [
        lesson("L-delay", "train delay"),
        {"id": "A-delay", "kind": "ANSWER", "slots": {"situation": "train delay"}},
    ]

    assert ids(lessons_for(records, "train delay")) == ["L-delay"]


def test_superseded_lesson_is_not_returned():
    records = [
        lesson("L-old", "train delay"),
        lesson("L-new", "train delay", "check the revised schedule"),
    ]

    assert ids(lessons_for(records, "train delay", superseded={"L-old"})) == ["L-new"]


@pytest.mark.xfail(strict=False, reason="DEFECT: callers can mutate the lesson retained in the index")
def test_mutating_returned_lesson_does_not_mutate_the_index():
    index = LessonIndex([lesson("L-delay", "train delay")])

    first = index.lessons_for("train delay")
    first[0]["slots"]["lesson"] = "changed by caller"

    assert index.lessons_for("train delay")[0]["slots"]["lesson"] == "lesson for train delay"
