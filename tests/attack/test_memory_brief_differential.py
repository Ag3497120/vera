import random
import unicodedata

import pytest

from verantyx.memory_brief import compile_brief


PRIORITY = {"INVARIANT": 0, "DECISION": 1, "TASK": 2, "LESSON": 3, "FACT": 4}
CLOSED_TASK_STATES = {"完了", "done", "complete", "completed", "finished"}


class FakeMemory:
    def __init__(self, records, sources=None, superseded=None):
        self._records = list(records)
        self.sources = sources or {}
        self.superseded = superseded or {}

    def active(self):
        return list(self._records)

    def ask_about(self, subject, attribute, kind=None, require_fresh=False):
        assert require_fresh is True
        return {"records": self.sources.get((subject, attribute, kind), [])}


def rec(rid, kind="FACT", sentence=None, ts="2025-01-01", **slots):
    return {
        "id": rid,
        "kind": kind,
        "sentence": sentence if sentence is not None else f"Sentence {rid}",
        "ts": ts,
        "slots": slots,
    }


def query_for(record):
    kind = record.get("kind")
    slots = record.get("slots", {})
    subject = slots.get("subject") if kind != "LESSON" else slots.get("situation")
    if kind == "FACT":
        attribute = slots.get("attribute")
    elif kind == "LESSON":
        attribute = "対処"
    else:
        attribute = None
    return subject, attribute, kind


def memory_with_sources(records, askable_ids=(), superseded=None):
    sources = {}
    wanted = {str(rid) for rid in askable_ids}
    for record in records:
        rid = str(record.get("id", ""))
        subject, attribute, kind = query_for(record)
        if rid and subject and rid in wanted:
            sources.setdefault((subject, attribute, kind), []).append(rid)
    return FakeMemory(records, sources=sources, superseded=superseded)


def norm(value):
    return unicodedata.normalize("NFKC", str(value or "")).casefold()


def reference_brief(memory, budget_chars, focus=None):
    """Small specification-based renderer, independent of compile_brief."""
    if isinstance(budget_chars, bool) or not isinstance(budget_chars, int) or budget_chars < 0:
        raise ValueError

    records = [r for r in memory.active() if str(r.get("id", "")) not in memory.superseded]
    if not records:
        return ""

    raw_terms = () if focus is None else ((focus,) if isinstance(focus, str) else focus)
    terms = tuple(dict.fromkeys(norm(term) for term in raw_terms if norm(term)))

    def is_focused(record):
        slots = record.get("slots", {})
        text = " ".join((str(record.get("sentence", "")), *(str(value) for value in slots.values())))
        haystack = norm(text)
        return bool(terms) and any(term in haystack for term in terms)

    def effective_priority(record):
        kind = record.get("kind")
        if kind == "TASK":
            state = norm(record.get("slots", {}).get("state"))
            if not state or state in CLOSED_TASK_STATES:
                return None
        return PRIORITY.get(kind)

    def can_be_asked(record):
        rid = str(record.get("id", ""))
        slots = record.get("slots", {})
        if not rid or not isinstance(slots, dict):
            return False
        subject, attribute, kind = query_for(record)
        if not subject:
            return False
        available = memory.sources.get((subject, attribute, kind), [])
        return rid in {str(source) for source in available}

    records.sort(key=lambda r: (
        0 if is_focused(r) else 1,
        effective_priority(r) if effective_priority(r) is not None else len(PRIORITY),
        str(r.get("ts", "")),
        str(r.get("id", "")),
    ))

    def render(selected):
        selected_ids = {str(record["id"]) for record in selected}
        lines = [f"[id:{record['id']}] {record['sentence']}" for record in selected]
        omitted = [str(record["id"]) for record in records if str(record["id"]) not in selected_ids]
        if omitted:
            lines.append("Dropped record ids: " + ", ".join(omitted))
        return "\n".join(lines)

    chosen = []
    for record in records:
        if effective_priority(record) is None or not record.get("sentence") or not can_be_asked(record):
            continue
        proposed = chosen + [record]
        if len(render(proposed)) <= budget_chars:
            chosen = proposed
    result = render(chosen)
    if len(result) > budget_chars:
        raise ValueError
    return result


def assert_matches_reference(memory, budget, focus=None):
    try:
        expected = reference_brief(memory, budget, focus)
    except ValueError:
        with pytest.raises(ValueError):
            compile_brief(memory, budget, focus)
        return
    assert compile_brief(memory, budget, focus) == expected


def test_empty_memory_and_budget_validation():
    assert compile_brief(FakeMemory([]), 0) == ""
    for invalid in (True, 1.5, -1):
        with pytest.raises(ValueError):
            compile_brief(FakeMemory([]), invalid)


def test_askable_and_unaskable_records_are_accounted_for():
    records = [rec("a", subject="Ada", attribute="role"), rec("b", subject="Bryn", attribute="role")]
    memory = memory_with_sources(records, askable_ids={"a"})
    expected = "[id:a] Sentence a\nDropped record ids: b"
    assert compile_brief(memory, len(expected)) == expected
    assert_matches_reference(memory, len(expected))


def test_superseded_records_disappear_and_closed_tasks_stay_dropped():
    records = [
        rec("old", subject="O", attribute="x"),
        rec("closed", kind="TASK", subject="T", state="DONE"),
        rec("open", kind="TASK", subject="T2", state="in progress"),
    ]
    memory = memory_with_sources(records, askable_ids={"old", "closed", "open"}, superseded={"old": "new"})
    expected = "[id:open] Sentence open\nDropped record ids: closed"
    assert compile_brief(memory, 200) == expected
    assert_matches_reference(memory, 200)


def test_nfkc_casefolded_focus_ranks_matching_record_first():
    records = [
        rec("invariant", kind="INVARIANT", sentence="Always store this", subject="X"),
        rec("fact", sentence="Use STRASSE data", subject="Y", attribute="source"),
    ]
    memory = memory_with_sources(records, askable_ids={"invariant", "fact"})
    result = compile_brief(memory, 200, focus="ＳＴＲＡＳＳＥ")
    assert result.splitlines() == ["[id:fact] Use STRASSE data", "[id:invariant] Always store this"]
    assert_matches_reference(memory, 200, focus="ＳＴＲＡＳＳＥ")


def test_kind_timestamp_and_id_order_break_ties():
    records = [
        rec("z", kind="FACT", ts="1", subject="S", attribute="a"),
        rec("d", kind="DECISION", ts="3", subject="S"),
        rec("b", kind="INVARIANT", ts="9", subject="S"),
        rec("c", kind="DECISION", ts="2", subject="S"),
        rec("a", kind="FACT", ts="1", subject="S", attribute="a"),
    ]
    memory = memory_with_sources(records, askable_ids={r["id"] for r in records})
    result = compile_brief(memory, 500)
    assert [line.split("]", 1)[0][4:] for line in result.splitlines()] == ["b", "c", "d", "a", "z"]
    assert_matches_reference(memory, 500)


def test_source_membership_and_lesson_question_shape_control_askability():
    records = [
        rec("f1", subject="same", attribute="color"),
        rec("f2", subject="same", attribute="color"),
        rec("lesson", kind="LESSON", situation="rain", response="carry an umbrella"),
    ]
    memory = memory_with_sources(records, askable_ids={"f1", "lesson"})
    assert_matches_reference(memory, 300)
    assert compile_brief(memory, 300).splitlines() == [
        "[id:lesson] Sentence lesson", "[id:f1] Sentence f1", "Dropped record ids: f2"
    ]


def test_budget_uses_python_character_length_and_reports_omissions():
    records = [rec("日本", sentence="猫", subject="ねこ", attribute="種類"), rec("x", subject="X", attribute="y")]
    memory = memory_with_sources(records, askable_ids={"日本"})
    expected = reference_brief(memory, 100)
    assert_matches_reference(memory, len(expected))
    assert len(compile_brief(memory, len(expected))) == len(expected)


def test_later_short_candidate_can_fit_after_earlier_long_candidate_is_skipped():
    records = [
        rec("long", kind="INVARIANT", sentence="x" * 90, subject="L"),
        rec("s", kind="DECISION", sentence="short", subject="S"),
    ]
    memory = memory_with_sources(records, askable_ids={"long", "s"})
    budget = len("[id:s] short\nDropped record ids: long")
    assert compile_brief(memory, budget) == "[id:s] short\nDropped record ids: long"
    assert_matches_reference(memory, budget)


def test_deterministic_generated_cases_match_naive_reference():
    rng = random.Random(20261002)
    kinds = ("INVARIANT", "DECISION", "TASK", "LESSON", "FACT")
    states = ("open", "done", "完了", "waiting")
    for case in range(60):
        records = []
        for index in range(rng.randint(1, 8)):
            kind = rng.choice(kinds)
            slots = {"subject": f"subject-{case}-{index}"}
            if kind == "FACT":
                slots["attribute"] = rng.choice(("color", "owner", "status"))
            elif kind == "LESSON":
                slots.pop("subject")
                slots["situation"] = f"situation-{case}-{index}"
                slots["response"] = rng.choice(("plan", "avoid", "retry"))
            elif kind == "TASK":
                slots["state"] = rng.choice(states)
            sentence = f"case {case} item {index} " + rng.choice(("alpha", "STRASSE", "東京"))
            records.append(rec(f"{case}-{index}", kind=kind, sentence=sentence,
                               ts=f"2025-01-{rng.randint(1, 4):02d}", **slots))
        askable = {record["id"] for record in records if rng.random() < 0.7}
        superseded = {record["id"]: "replacement" for record in records if rng.random() < 0.15}
        memory = memory_with_sources(records, askable_ids=askable, superseded=superseded)
        focus = rng.choice((None, "alpha", "ＳＴＲＡＳＳＥ", ["東京", "missing"]))
        budget = rng.randint(0, 240)
        assert_matches_reference(memory, budget, focus)


def test_nonaskable_records_are_never_rendered_as_answers():
    records = [rec("unsupported", sentence="Unsupported claim", subject="S", attribute="A")]
    memory = memory_with_sources(records)
    output = compile_brief(memory, 100)
    assert output == "Dropped record ids: unsupported"
    assert "Unsupported claim" not in output
