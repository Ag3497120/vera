import pytest

from verantyx.memory_frame import Memory, WriteRejected, parse_choice


def _memory(tmp_path, name="memory.jsonl", now=None):
    return Memory(str(tmp_path / name), now=now or (lambda: "2026-10-02T00:00:00"))


def _fact(memory, *, subject="ルーター", attribute="未読の上限", value="512", witness=None, **kwargs):
    return memory.write(
        "FACT",
        "attacker-test",
        witness={"kind": "testimony"} if witness is None else witness,
        subject=subject,
        attribute=attribute,
        value=value,
        **kwargs,
    )


def test_empty_memory_returns_unknown_without_sources(tmp_path):
    result = _memory(tmp_path).ask_about("ルーター", "未読の上限")

    assert result["verdict"] == "UNKNOWN_NO_EVIDENCE"
    assert result["values"] == []
    assert result["records"] == []


def test_incomplete_fact_is_rejected_without_appending(tmp_path):
    memory = _memory(tmp_path)

    with pytest.raises(WriteRejected):
        memory.write("FACT", "attacker-test", witness={"kind": "testimony"}, subject="ルーター", attribute="未読上限")

    assert memory.records == {}
    assert memory.path.read_text() == "" if memory.path.exists() else True


def test_sentence_boundary_in_value_is_rejected_without_appending(tmp_path):
    memory = _memory(tmp_path)

    with pytest.raises(WriteRejected):
        _fact(memory, value="512。別の命題")

    assert memory.records == {}


def test_fact_requires_a_witness(tmp_path):
    memory = _memory(tmp_path)

    with pytest.raises(WriteRejected):
        memory.write("FACT", "attacker-test", subject="ルーター", attribute="未読上限", value="512")

    assert memory.records == {}


def test_unknown_witness_kind_is_rejected_without_appending(tmp_path):
    memory = _memory(tmp_path)

    with pytest.raises(WriteRejected):
        _fact(memory, witness={"kind": "remote_assertion"})

    assert memory.records == {}


def test_normalization_is_recorded_and_does_not_change_the_value(tmp_path):
    record = _fact(_memory(tmp_path), attribute="未読の上限", value="512")

    assert record["slots"] == {"subject": "ルーター", "attribute": "未読上限", "value": "512"}
    assert record["normalized"] == {"attribute": "未読の上限"}
    assert record["sentence"] == "ルーターの未読上限は512である。"


def test_changed_text_witness_is_stale_and_excluded_from_fresh_queries(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("運用値は512です。", encoding="utf-8")
    memory = _memory(tmp_path)
    record = _fact(memory, witness={"kind": "text_in_file", "path": str(source), "needle": "運用値は512"})

    source.write_text("運用値は未確認です。", encoding="utf-8")

    assert memory.verify()[record["id"]] == "STALE"
    assert [r["id"] for r in memory.active(require_fresh=False)] == [record["id"]]
    assert memory.active(require_fresh=True) == []
    result = memory.ask_about("ルーター", "未読上限")
    assert result["verdict"] == "UNKNOWN_NO_EVIDENCE"
    assert result["records"] == []


def test_superseded_fact_is_not_active_and_replacement_is_active(tmp_path):
    ticks = iter(("2026-10-02T00:00:01", "2026-10-02T00:00:02", "2026-10-02T00:00:03", "2026-10-02T00:00:04", "2026-10-02T00:00:05"))
    memory = _memory(tmp_path, now=lambda: next(ticks))
    old = _fact(memory, value="512")
    new = _fact(memory, value="256", supersedes=old["id"])

    assert [r["id"] for r in memory.active()] == [new["id"]]
    assert memory.superseded == {old["id"]: new["id"]}


def test_persisted_records_keep_their_ids_and_source_mapping(tmp_path):
    path = tmp_path / "memory.jsonl"
    record = _fact(Memory(str(path), now=lambda: "2026-10-02T00:00:00"))
    reloaded = Memory(str(path), now=lambda: "2026-10-02T00:00:01")

    assert [r["id"] for r in reloaded.active()] == [record["id"]]
    result = reloaded.ask_about("ルーター", "未読上限")
    if result["verdict"] == "ANSWER":
        assert result["records"] == [record["id"]]


def test_different_entity_does_not_receive_the_record_as_an_answer(tmp_path):
    memory = _memory(tmp_path)
    record = _fact(memory)

    result = memory.ask_about("スイッチ", "未読上限")

    assert result["verdict"] != "ANSWER"
    assert record["id"] not in result["records"]


def test_closed_choice_parser_rejects_out_of_range_and_malformed_choices():
    assert parse_choice('{"choice": 2}', 3) == 2
    assert parse_choice('{"choice": null}', 3) is None
    assert parse_choice('{"choice": 3}', 3) is False
    assert parse_choice("no JSON", 3) is False


@pytest.mark.parametrize(
    ("source_text", "needle", "value"),
    [
        ("受付時間は平日である。", "受付時間", "512"),
        ("部署の所在地は東京である。", "東京", "1024"),
    ],
    ids=("partial-unrelated-span-1", "partial-unrelated-span-2"),
)
@pytest.mark.xfail(strict=False, reason="DEFECT: a fresh text substring unrelated to a FACT produces an ANSWER")
def test_partial_unrelated_text_span_cannot_support_a_fact(tmp_path, source_text, needle, value):
    source = tmp_path / "source.txt"
    source.write_text(source_text, encoding="utf-8")
    memory = _memory(tmp_path)
    record = _fact(
        memory,
        value=value,
        witness={"kind": "text_in_file", "path": str(source), "needle": needle},
    )

    result = memory.ask_about("ルーター", "未読上限")

    assert result["verdict"] != "ANSWER" or record["id"] not in result["records"]


@pytest.mark.xfail(strict=False, reason="DEFECT: write event is appended before the supersession target is validated")
def test_rejected_missing_supersession_target_does_not_leave_a_record(tmp_path):
    memory = _memory(tmp_path)

    with pytest.raises(WriteRejected):
        _fact(memory, supersedes="missing-record")

    assert memory.active() == []
