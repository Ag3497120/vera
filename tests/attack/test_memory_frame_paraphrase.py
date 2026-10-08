import pytest

from verantyx.memory_frame import Memory


def _memory(tmp_path, name="memory.jsonl"):
    return Memory(str(tmp_path / name), now=lambda: "2026-01-01T00:00:00")


def _fact(memory, *, subject="ルーター", attribute="未読上限", value="3件"):
    return memory.write(
        "FACT",
        "attack-test",
        witness={"kind": "testimony"},
        subject=subject,
        attribute=attribute,
        value=value,
    )


def test_canonical_fact_question_returns_written_value(tmp_path):
    memory = _memory(tmp_path)
    record = _fact(memory)

    answer = memory.ask_about("ルーター", "未読上限")

    assert record["sentence"] == "ルーターの未読上限は3件である。"
    assert answer["verdict"] == "ANSWER"
    assert answer["values"] == ["3件"]


def test_genitive_attribute_variant_uses_documented_normalization(tmp_path):
    memory = _memory(tmp_path)
    record = _fact(memory, attribute="未読の上限")

    answer = memory.ask_about("ルーター", "未読の上限")

    assert record["slots"]["attribute"] == "未読上限"
    assert record["normalized"] == {"attribute": "未読の上限"}
    assert answer["verdict"] == "ANSWER"
    assert answer["values"] == ["3件"]


def test_subject_case_particle_variant_uses_documented_normalization(tmp_path):
    memory = _memory(tmp_path)
    _fact(memory)

    answer = memory.ask_about("ルーターは", "未読上限")

    assert answer["verdict"] == "ANSWER"
    assert answer["values"] == ["3件"]


def test_plain_and_polite_what_questions_agree(tmp_path):
    memory = _memory(tmp_path)
    _fact(memory)

    plain = memory.ask("ルーターの未読上限は？")
    polite = memory.ask("ルーターの未読上限は何ですか？")

    assert plain["verdict"] == polite["verdict"] == "ANSWER"
    assert plain["values"] == polite["values"] == ["3件"]


def test_swapped_entity_does_not_reuse_the_record(tmp_path):
    memory = _memory(tmp_path)
    _fact(memory)

    answer = memory.ask_about("スイッチ", "未読上限")

    assert answer["verdict"] == "UNKNOWN_NO_EVIDENCE"
    assert answer["values"] == []
    assert answer["records"] == []


def test_swapped_attribute_does_not_reuse_the_record(tmp_path):
    memory = _memory(tmp_path)
    _fact(memory)

    answer = memory.ask_about("ルーター", "接続数")

    assert answer["verdict"] == "UNKNOWN_NO_EVIDENCE"
    assert answer["values"] == []
    assert answer["records"] == []


def test_changed_record_number_changes_the_answer(tmp_path):
    three = _memory(tmp_path, "three.jsonl")
    four = _memory(tmp_path, "four.jsonl")
    _fact(three, value="3件")
    _fact(four, value="4件")

    answer_three = three.ask_about("ルーター", "未読上限")
    answer_four = four.ask_about("ルーター", "未読上限")

    assert answer_three["verdict"] == answer_four["verdict"] == "ANSWER"
    assert answer_three["values"] == ["3件"]
    assert answer_four["values"] == ["4件"]


def test_decision_frame_survives_polite_question_surface(tmp_path):
    memory = _memory(tmp_path)
    memory.write("DECISION", "attack-test", subject="API", choice="審査中")

    plain = memory.ask_about("API", kind="DECISION")
    polite = memory.ask("APIの決定は何ですか？")

    assert plain["verdict"] == polite["verdict"] == "ANSWER"
    assert plain["values"] == polite["values"] == ["審査中"]


@pytest.mark.xfail(strict=False, reason="DEFECT: lexical の inside an entity is stripped as if it were a genitive particle")
def test_lexical_no_is_not_a_genitive_particle(tmp_path):
    memory = _memory(tmp_path)
    _fact(memory, subject="きのこ")

    answer_for_distinct_entity = memory.ask_about("きこ", "未読上限")

    assert answer_for_distinct_entity["verdict"] == "UNKNOWN_NO_EVIDENCE"
    assert answer_for_distinct_entity["values"] == []


@pytest.mark.xfail(strict=False, reason="DEFECT: numeric paraphrase いくつですか abstains on a supported property value")
def test_numeric_paraphrase_preserves_supported_answer(tmp_path):
    memory = _memory(tmp_path)
    _fact(memory)

    answer = memory.ask("ルーターの未読上限はいくつですか？")

    assert answer["verdict"] == "ANSWER"
    assert answer["values"] == ["3件"]
