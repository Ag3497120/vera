from concurrent.futures import ThreadPoolExecutor

import pytest

from verantyx.conductor import AgentQuestion, ProjectFrame, Reply


def test_empty_frame_escalates_order_with_typed_reason(tmp_path):
    frame = ProjectFrame(tmp_path / "empty.db")

    reply = frame.answer(AgentQuestion("q", "What is next?"))

    assert isinstance(reply, Reply)
    assert reply.kind == "ESCALATE"
    assert reply.question_kind == "ORDER"
    assert reply.missing == "ORDER"


def test_malformed_question_and_options_escalate_without_crashing(tmp_path):
    frame = ProjectFrame(tmp_path / "malformed.db")

    missing = frame.answer(AgentQuestion("q", "   "))
    malformed_options = frame.answer(
        AgentQuestion("q2", "Which option should I choose?", options=("a", "b"))
    )

    assert isinstance(missing, Reply) and missing.kind == "ESCALATE"
    assert missing.missing == "agent question"
    assert isinstance(malformed_options, Reply) and malformed_options.kind == "ESCALATE"
    assert malformed_options.missing == "closed option list"


def test_large_unclassified_question_returns_typed_escalation(tmp_path):
    frame = ProjectFrame(tmp_path / "large.db")
    text = "x" * 500_000

    reply = frame.answer(AgentQuestion("large", text))

    assert isinstance(reply, Reply)
    assert reply.kind == "ESCALATE"
    assert reply.question_kind == "OTHER"


def test_order_answer_is_repeatable_and_has_unique_evidence_ids(tmp_path):
    frame = ProjectFrame(tmp_path / "order.db")
    authority = frame.add_decision("phase ordering", "A before B")
    frame.add_task("A", "完了")
    frame.add_task("B", "進行中")
    edge = frame.add_order("A", "B", authority["id"])

    question = AgentQuestion("q", "What is next?")
    first = frame.answer(question)
    second = frame.answer(question)

    assert first == second
    assert first.kind == "ANSWER"
    assert first.answer == "B"
    assert edge["id"] in first.record_ids
    assert len(first.record_ids) == len(set(first.record_ids))


def test_order_answer_does_not_depend_on_fact_insertion_order(tmp_path):
    authority_text = "A before B"
    first = ProjectFrame(tmp_path / "first-order.db")
    first_authority = first.add_decision("phase ordering", authority_text)
    first.add_task("A", "完了")
    first.add_task("B", "進行中")
    first.add_order("A", "B", first_authority["id"])

    second = ProjectFrame(tmp_path / "second-order.db")
    second_authority = second.add_decision("phase ordering", authority_text)
    second.add_order("A", "B", second_authority["id"])
    second.add_task("B", "進行中")
    second.add_task("A", "完了")

    question = AgentQuestion("q", "What is next?")
    first_reply = first.answer(question)
    second_reply = second.answer(question)

    assert first_reply.kind == second_reply.kind == "ANSWER"
    assert first_reply.answer == second_reply.answer == "B"


def test_order_tie_abstains_instead_of_picking_a_successor(tmp_path):
    frame = ProjectFrame(tmp_path / "tie.db")
    authority = frame.add_decision("phase ordering", "A precedes B and C")
    frame.add_task("A", "完了")
    frame.add_task("B", "進行中")
    frame.add_task("C", "未着手")
    frame.add_order("A", "B", authority["id"])
    frame.add_order("A", "C", authority["id"])

    reply = frame.answer(AgentQuestion("q", "What is next?"))

    assert reply.kind == "ESCALATE"
    assert reply.question_kind == "ORDER"
    assert "ties abstain" in reply.reason


def test_protected_publish_request_escalates(tmp_path):
    frame = ProjectFrame(tmp_path / "protected.db")

    reply = frame.answer(AgentQuestion("q", "Can I publish the draft?"))

    assert reply.kind == "ESCALATE"
    assert "outside frame authority" in reply.reason
    assert reply.missing == "human"


def test_policy_answer_is_grounded_in_active_authority(tmp_path):
    frame = ProjectFrame(tmp_path / "policy.db")
    authority = frame.add_decision("draft use", "approved draft may be processed")
    policy = frame.add_policy(
        "CONFIRM", "approved draft", "allowed", authority["id"]
    )

    reply = frame.answer(
        AgentQuestion("q", "May I process this approved draft?")
    )

    assert reply.kind == "ANSWER"
    assert reply.answer == "allowed"
    assert set(reply.record_ids) == {authority["id"], policy["id"]}


def test_unchanged_task_write_and_status_read_are_idempotent(tmp_path):
    frame = ProjectFrame(tmp_path / "task.db")
    first_record = frame.add_task("ingest", "進行中")
    same_record = frame.add_task("ingest", "進行中")
    question = AgentQuestion(
        "status", "What is the status?",
        claimed_state={"task_id": "ingest", "state": "claimed"},
    )

    first = frame.answer(question)
    second = frame.answer(question)

    assert same_record["id"] == first_record["id"]
    assert first == second
    assert first.kind == "ANSWER"
    assert first.answer == "進行中"
    assert first.record_ids == (first_record["id"],)


def test_two_reader_instances_return_the_same_order_answer(tmp_path):
    path = tmp_path / "shared.db"
    writer = ProjectFrame(path)
    authority = writer.add_decision("phase ordering", "A before B")
    writer.add_task("A", "完了")
    writer.add_task("B", "進行中")
    writer.add_order("A", "B", authority["id"])
    readers = (ProjectFrame(path), ProjectFrame(path))
    question = AgentQuestion("q", "What is next?")

    with ThreadPoolExecutor(max_workers=2) as pool:
        replies = list(pool.map(lambda frame: frame.answer(question), readers * 8))

    assert all(reply.kind == "ANSWER" and reply.answer == "B" for reply in replies)
    assert all(reply == replies[0] for reply in replies)


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: ORDER lookup ignores normalized task identity",
)
def test_order_resolves_task_ids_using_the_same_normalization_as_conflict_checks(tmp_path):
    frame = ProjectFrame(tmp_path / "normalized.db")
    authority = frame.add_decision("phase ordering", "Build before Deploy")
    frame.add_task("Build", "完了")
    frame.add_task("Deploy", "進行中")
    frame.add_order("build", "deploy", authority["id"])

    reply = frame.answer(AgentQuestion("q", "What is next?"))

    assert reply.kind == "ANSWER"
    assert reply.answer == "Deploy"
