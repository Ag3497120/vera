import pytest

from verantyx.memory_frame import Memory
from verantyx.memory_revalidate import RevalidatingMemory


def _memory(tmp_path, *, witness=None):
    memory = Memory(str(tmp_path / "memory.jsonl"))
    record = memory.write(
        "FACT",
        "attacker-test",
        witness=witness or {"kind": "testimony"},
        subject="ルーター",
        attribute="未読の上限",
        value="24",
    )
    return RevalidatingMemory(memory), record


def test_slot_normalization_preserves_answer_for_same_meaning_variants(tmp_path):
    memory, _ = _memory(tmp_path)

    for subject, attribute in [
        ("ルーター", "未読の上限"),
        (" ルーター ", "未読の上限"),
        ("ルーターの", "未読上限"),
    ]:
        answer = memory.ask_about(subject, attribute)
        assert answer["verdict"] == "ANSWER"
        assert answer["values"] == ["24"]


def test_changed_entity_does_not_reuse_the_router_answer(tmp_path):
    memory, _ = _memory(tmp_path)

    answer = memory.ask_about("スイッチ", "未読の上限")

    assert answer["verdict"] == "UNKNOWN_NO_EVIDENCE"
    assert answer["values"] == []


def test_changed_attribute_does_not_reuse_the_unread_limit_answer(tmp_path):
    memory, _ = _memory(tmp_path)

    answer = memory.ask_about("ルーター", "接続人数")

    assert answer["verdict"] == "UNKNOWN_NO_EVIDENCE"
    assert answer["values"] == []


def test_testimony_remains_answerable_and_is_labeled_unverifiable(tmp_path):
    memory, record = _memory(tmp_path, witness={"kind": "testimony"})

    answer = memory.ask_about("ルーター", "未読の上限")

    assert answer["verdict"] == "ANSWER"
    assert answer["values"] == ["24"]
    assert answer["witness_status"] == {record["id"]: "UNVERIFIABLE"}
    assert answer["stale"] == []


def test_fresh_text_witness_keeps_its_record_answerable(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("router unread limit: 24", encoding="utf-8")
    memory, record = _memory(
        tmp_path,
        witness={"kind": "text_in_file", "path": str(source), "needle": "unread limit: 24"},
    )

    answer = memory.ask_about("ルーター", "未読の上限")

    assert answer["verdict"] == "ANSWER"
    assert answer["values"] == ["24"]
    assert answer["witness_status"] == {record["id"]: "FRESH"}
    assert answer["stale"] == []


def test_stale_text_witness_is_labeled_and_cannot_support_an_answer(tmp_path):
    source = tmp_path / "source.txt"
    source.write_text("router unread limit: 12", encoding="utf-8")
    memory, record = _memory(
        tmp_path,
        witness={"kind": "text_in_file", "path": str(source), "needle": "unread limit: 24"},
    )

    answer = memory.ask_about("ルーター", "未読の上限")

    assert answer["verdict"] == "UNKNOWN_NO_EVIDENCE"
    assert answer["values"] == []
    assert answer["witness_status"] == {record["id"]: "STALE"}
    assert answer["stale"] == [record["id"]]


def test_missing_witness_is_unverifiable_without_hiding_typed_memory(tmp_path):
    memory, record = _memory(tmp_path, witness=None)

    answer = memory.ask_about("ルーター", "未読の上限")

    assert answer["verdict"] == "ANSWER"
    assert answer["values"] == ["24"]
    assert answer["witness_status"] == {record["id"]: "UNVERIFIABLE"}


def test_question_paraphrases_do_not_create_an_answer_without_a_complete_request(tmp_path):
    memory, _ = _memory(tmp_path)

    for question in (
        "ルーターの未読の上限は何ですか？",
        "ルーターの未読の上限はいくつ？",
        "ルーターの未読の上限を教えてください。",
    ):
        answer = memory.ask(question)
        assert answer["verdict"] != "ANSWER"
        assert answer["values"] == []


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: equivalent free-form questions receive different UNKNOWN verdicts",
)
def test_equivalent_question_surfaces_keep_the_same_verdict(tmp_path):
    memory, _ = _memory(tmp_path)
    questions = (
        "ルーターの未読の上限は何ですか？",
        "ルーターの未読の上限はいくつ？",
    )

    answers = [memory.ask(question) for question in questions]

    assert [answer["verdict"] for answer in answers] == ["UNKNOWN_NO_EVIDENCE"] * 2
