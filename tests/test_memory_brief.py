import pytest

from verantyx.memory_brief import compile_brief
from verantyx.memory_frame import Memory


def record(kind, rid, subject=None, value=None, ts="2026-01-01"):
    if kind == "FACT":
        slots = {"subject": subject or "ルーター", "attribute": "未読上限", "value": value or "32件"}
        sentence = f"{slots['subject']}の{slots['attribute']}は{slots['value']}である。"
    elif kind == "DECISION":
        slots = {"subject": subject or "設計", "choice": value or "段階導入"}
        sentence = f"{slots['subject']}の決定は{slots['choice']}である。"
    elif kind == "INVARIANT":
        slots = {"subject": subject or "検証", "rule": value or "封印データを使わない"}
        sentence = f"{slots['subject']}の規則は{slots['rule']}である。"
    elif kind == "TASK":
        slots = {"subject": subject or "brief", "state": value or "進行中"}
        sentence = f"{slots['subject']}の状態は{slots['state']}である。"
    elif kind == "LESSON":
        slots = {"situation": subject or "短い予算", "fix": value or "全件を数える"}
        sentence = f"{slots['situation']}の対処は{slots['fix']}である。"
    else:
        slots = {"subject": subject or "その他", "value": value or "記録"}
        sentence = f"{slots['subject']}の値は{slots['value']}である。"
    return {"id": rid, "kind": kind, "slots": slots, "sentence": sentence, "ts": ts}


class StubMemory:
    def __init__(self, records=(), superseded=(), unaskable=()):
        self.records = list(records)
        self.superseded = {rid: "replacement" for rid in superseded}
        self.unaskable = set(unaskable)
        self.calls = []

    def active(self):
        return [r for r in self.records if r["id"] not in self.superseded]

    def ask_about(self, subject, attribute=None, kind="FACT", require_fresh=True):
        self.calls.append((subject, attribute, kind, require_fresh))
        found = []
        query_attribute = attribute if kind == "FACT" else {
            "DECISION": "決定", "INVARIANT": "規則", "TASK": "状態", "LESSON": "対処"
        }.get(kind)
        for r in self.active():
            if r["id"] in self.unaskable or r["kind"] != kind:
                continue
            slots = r["slots"]
            expected_subject = slots.get("subject", slots.get("situation"))
            expected_attribute = slots.get("attribute") if kind == "FACT" else {
                "DECISION": "決定", "INVARIANT": "規則", "TASK": "状態", "LESSON": "対処"
            }.get(kind)
            if expected_subject == subject and expected_attribute == query_attribute:
                found.append(r["id"])
        return {"verdict": "ANSWER" if found else "UNKNOWN_NO_EVIDENCE", "records": found, "values": []}


def dropped_ids(brief):
    line = next((line for line in brief.splitlines() if line.startswith("Dropped record ids: ")), "")
    return [] if not line else line.removeprefix("Dropped record ids: ").split(", ")


def test_priority_order_is_fixed():
    memory = StubMemory([
        record("FACT", "f"), record("LESSON", "l"), record("TASK", "t"),
        record("DECISION", "d"), record("INVARIANT", "i"),
    ])
    brief = compile_brief(memory, 2000)
    positions = [brief.index(f"[id:{rid}]") for rid in ("i", "d", "t", "l", "f")]
    assert positions == sorted(positions)


def test_output_is_deterministic_across_record_insertion_orders():
    items = [record("FACT", "f"), record("FACT", "a", ts="2025-01-01"), record("DECISION", "d")]
    assert compile_brief(StubMemory(items), 500) == compile_brief(StubMemory(reversed(items)), 500)


def test_ties_use_timestamp_then_record_id():
    memory = StubMemory([record("FACT", "z"), record("FACT", "b"), record("FACT", "a", ts="2025-01-01")])
    brief = compile_brief(memory, 1000)
    assert [brief.index(f"[id:{rid}]") for rid in ("a", "b", "z")] == sorted(
        brief.index(f"[id:{rid}]") for rid in ("a", "b", "z")
    )


def test_superseded_records_never_appear_even_in_dropped_ids():
    memory = StubMemory([record("INVARIANT", "old"), record("INVARIANT", "new")], superseded=["old"])
    brief = compile_brief(memory, 1000)
    assert "old" not in brief
    assert "new" in brief


def test_dropped_ids_are_exact_and_deterministic():
    records = [record("FACT", "f"), record("DECISION", "d"), record("INVARIANT", "i")]
    memory = StubMemory(records)
    one = compile_brief(memory, len("[id:i] " + records[2]["sentence"] + "\nDropped record ids: d, f"))
    assert "[id:i]" in one
    assert dropped_ids(one) == ["d", "f"]


@pytest.mark.parametrize("extra", [0, 1, 5, 20, 200])
def test_output_never_exceeds_budget(extra):
    records = [record("INVARIANT", "i"), record("FACT", "f")]
    footer_size = len("Dropped record ids: i, f")
    brief = compile_brief(StubMemory(records), footer_size + extra)
    assert len(brief) <= footer_size + extra


def test_exact_fit_includes_whole_record_and_drop_list():
    invariant = record("INVARIANT", "i")
    fact = record("FACT", "f")
    expected = f"[id:i] {invariant['sentence']}\nDropped record ids: f"
    brief = compile_brief(StubMemory([fact, invariant]), len(expected))
    assert brief == expected


def test_record_is_not_truncated_when_it_does_not_fit():
    long_record = record("INVARIANT", "long", value="規則" * 80)
    brief = compile_brief(StubMemory([long_record]), len("Dropped record ids: long"))
    assert "規則" not in brief
    assert dropped_ids(brief) == ["long"]


def test_long_unicode_value_is_kept_whole_when_budget_allows():
    item = record("FACT", "unicode", subject="東京" * 40, value="猫🐈" * 50)
    expected_line = f"[id:unicode] {item['sentence']}"
    brief = compile_brief(StubMemory([item]), len(expected_line))
    assert brief == expected_line
    assert item["sentence"] in brief


def test_focus_moves_matching_record_ahead_within_kind():
    first = record("FACT", "a", subject="青い箱" * 20, value="先")
    match = record("FACT", "b", subject="赤い箱", value="後")
    memory = StubMemory([first, match])
    focused_only = f"[id:b] {match['sentence']}\nDropped record ids: a"
    brief = compile_brief(memory, len(focused_only), focus=["赤い"])
    assert brief == focused_only


def test_focus_accepts_a_single_string_term():
    item = record("FACT", "match", subject="Router")
    other = record("FACT", "other", subject="Switch")
    brief = compile_brief(StubMemory([other, item]), 1000, focus="router")
    assert brief.index("[id:match]") < brief.index("[id:other]")


def test_focus_uses_unicode_nfkc_matching():
    item = record("FACT", "match", subject="router")
    other = record("FACT", "other", subject="switch")
    brief = compile_brief(StubMemory([other, item]), 1000, focus=["ｒｏｕｔｅｒ"])
    assert brief.index("[id:match]") < brief.index("[id:other]")


def test_focus_raises_matching_record_across_kind_priorities():
    fact = record("FACT", "f", subject="focus-target")
    invariant = record("INVARIANT", "i", subject="other")
    expected = f"[id:f] {fact['sentence']}\nDropped record ids: i"
    brief = compile_brief(StubMemory([invariant, fact]), len(expected), focus=["focus-target"])
    assert brief == expected


def test_multiple_focus_terms_match_any_term():
    first = record("FACT", "a", subject="Alpha")
    match = record("FACT", "b", subject="Beta")
    budget = len(f"[id:b] {match['sentence']}\nDropped record ids: a")
    assert "[id:b]" in compile_brief(StubMemory([first, match]), budget, focus=["Gamma", "Beta"])


@pytest.mark.parametrize("state", ["未着手", "進行中", "保留", "停止"])
def test_noncompleted_task_states_are_open_and_eligible(state):
    item = record("TASK", "task", value=state)
    assert "[id:task]" in compile_brief(StubMemory([item]), 200)


@pytest.mark.parametrize("state", ["完了", "done", "complete", "completed", "finished"])
def test_completed_task_states_are_dropped(state):
    item = record("TASK", "task", value=state)
    brief = compile_brief(StubMemory([item]), 100)
    assert "[id:task]" not in brief
    assert dropped_ids(brief) == ["task"]


def test_unaskable_record_is_reported_as_dropped():
    item = record("FACT", "unaskable")
    memory = StubMemory([item], unaskable=["unaskable"])
    brief = compile_brief(memory, 200)
    assert "[id:unaskable]" not in brief
    assert dropped_ids(brief) == ["unaskable"]
    assert memory.calls


@pytest.mark.parametrize("kind,subject,attribute", [
    ("FACT", "ルーター", "未読上限"),
    ("DECISION", "設計", None),
    ("INVARIANT", "検証", None),
    ("TASK", "brief", None),
    ("LESSON", "短い予算", "対処"),
])
def test_askability_uses_memory_ask_about(kind, subject, attribute):
    memory = StubMemory([record(kind, "r")])
    compile_brief(memory, 1000)
    assert memory.calls == [(subject, attribute, kind, True)]


@pytest.mark.parametrize("budget", [0, 1, 50])
def test_empty_memory_returns_empty_brief_for_any_budget(budget):
    assert compile_brief(StubMemory(), budget) == ""


def test_budget_too_small_to_name_dropped_records_is_an_error():
    with pytest.raises(ValueError, match="too small"):
        compile_brief(StubMemory([record("FACT", "r")]), 1)


@pytest.mark.parametrize("budget", [-1, -20])
def test_negative_budget_is_rejected(budget):
    with pytest.raises(ValueError, match="non-negative"):
        compile_brief(StubMemory(), budget)


@pytest.mark.parametrize("budget", [1.5, "40", True, None])
def test_noninteger_budget_is_rejected(budget):
    with pytest.raises(ValueError, match="non-negative integer"):
        compile_brief(StubMemory(), budget)


def test_unsupported_active_kind_is_listed_as_dropped():
    item = record("OTHER", "other")
    assert dropped_ids(compile_brief(StubMemory([item]), 100)) == ["other"]


def test_no_dropped_footer_is_emitted_when_every_record_fits():
    item = record("FACT", "only")
    brief = compile_brief(StubMemory([item]), 1000)
    assert "[id:only]" in brief
    assert "Dropped record ids:" not in brief


def test_empty_focus_and_no_focus_are_equivalent():
    items = [record("FACT", "a"), record("INVARIANT", "i")]
    assert compile_brief(StubMemory(items), 1000, focus=[]) == compile_brief(StubMemory(items), 1000)


@pytest.mark.parametrize("kind,slots,subject,attribute", [
    ("FACT", {"subject": "ルーター", "attribute": "未読上限", "value": "32件"}, "ルーター", "未読上限"),
    ("DECISION", {"subject": "設計", "choice": "段階導入"}, "設計", None),
    ("INVARIANT", {"subject": "検証", "rule": "固定優先"}, "検証", None),
    ("TASK", {"subject": "brief", "state": "進行中"}, "brief", None),
    ("LESSON", {"situation": "短い予算", "fix": "予算確認"}, "短い予算", "対処"),
])
def test_real_memory_records_round_trip_through_ask_about(tmp_path, kind, slots, subject, attribute):
    memory = Memory(str(tmp_path / "memory.jsonl"), now=lambda: "2026-10-02T00:00:00")
    witness = {"kind": "testimony"} if kind in {"FACT", "INVARIANT"} else None
    item = memory.write(kind, "test", witness=witness, **slots)
    brief = compile_brief(memory, 500)
    answer = memory.ask_about(subject, attribute, kind=kind)
    assert f"[id:{item['id']}]" in brief
    assert item["sentence"] in brief
    assert item["id"] in answer["records"]
