from types import SimpleNamespace

import pytest

from verantyx.conductor import AgentQuestion, Reply
from verantyx.conductor_escalate import check_resolved, enrich


def _question() -> AgentQuestion:
    return AgentQuestion(
        id="q-17",
        text="Did Lin approve the transfer, and was it not sent to Rhea?",
        options=["approved", "rejected"],
        claimed_state={"subject": "Lin", "negated": True, "object": "Rhea"},
    )


def _frame(tmp_path):
    return SimpleNamespace(memory=SimpleNamespace(path=tmp_path / "frame.jsonl"))


def _handoff(tmp_path, *, reason="", missing="TRANSFER_RECORD", question=None):
    question = question or _question()
    reply = Reply(
        kind="ESCALATE",
        reason=reason,
        missing=missing,
        question_kind="FACT",
    )
    return enrich(reply, _frame(tmp_path), question), question


class _AnsweringConductor:
    def __init__(self, answer, active_record):
        self._answer = answer
        self._record = active_record
        self.asked = []

    def answer(self, question):
        self.asked.append(question)
        return self._answer

    def _active_record(self, record_id):
        if self._record is None or self._record.get("id") != record_id:
            return None
        return self._record


def test_enrich_rejects_non_escalation_reply(tmp_path):
    with pytest.raises(ValueError, match="ESCALATE"):
        enrich(Reply(kind="ANSWER", answer="approved", record_ids=("r1",)), _frame(tmp_path), _question())


def test_enrich_requires_original_agent_question(tmp_path):
    with pytest.raises(ValueError, match="original AgentQuestion"):
        enrich(Reply(kind="ESCALATE", missing="TRANSFER_RECORD"), _frame(tmp_path))


def test_handoff_keeps_exact_question_with_role_entity_and_negation(tmp_path):
    handoff, question = _handoff(tmp_path)

    assert handoff.question is question
    assert handoff.reask is question
    assert handoff.reask.id == "q-17"
    assert handoff.reask.text == "Did Lin approve the transfer, and was it not sent to Rhea?"
    assert handoff.reask.options == ["approved", "rejected"]
    assert handoff.reask.claimed_state == {"subject": "Lin", "negated": True, "object": "Rhea"}


def test_handoff_serialization_preserves_question_and_reask(tmp_path):
    handoff, _ = _handoff(tmp_path)
    data = handoff.as_dict()

    assert data["question"] == data["reask"]
    assert data["reask"]["text"] == "Did Lin approve the transfer, and was it not sent to Rhea?"
    assert data["reask"]["claimed_state"] == {"subject": "Lin", "negated": True, "object": "Rhea"}


def test_check_resolved_reasks_the_original_question(tmp_path):
    handoff, question = _handoff(tmp_path)
    conductor = _AnsweringConductor(Reply(kind="ESCALATE", missing="TRANSFER_RECORD"), None)

    assert check_resolved(handoff, conductor) is False
    assert conductor.asked == [question]


def test_answer_without_citation_does_not_resolve(tmp_path):
    handoff, _ = _handoff(tmp_path)
    conductor = _AnsweringConductor(Reply(kind="ANSWER", answer="approved"), None)

    assert check_resolved(handoff, conductor) is False


def test_inactive_citation_does_not_resolve(tmp_path):
    handoff, _ = _handoff(tmp_path)
    conductor = _AnsweringConductor(Reply(kind="ANSWER", answer="approved", record_ids=("old-r1",)), None)

    assert check_resolved(handoff, conductor) is False


def test_active_cited_answer_resolves(tmp_path):
    handoff, _ = _handoff(tmp_path)
    answer = Reply(kind="ANSWER", answer="approved", record_ids=("active-r1",))
    conductor = _AnsweringConductor(answer, {"id": "active-r1", "text": "supports the re-asked fact"})

    assert check_resolved(handoff, conductor) is True


def test_protected_action_cannot_be_closed_by_document_answer(tmp_path):
    handoff, _ = _handoff(
        tmp_path,
        reason="outside frame authority: approve the transfer",
        missing="authority approval",
    )
    answer = Reply(kind="ANSWER", answer="approved", record_ids=("active-r1",))
    conductor = _AnsweringConductor(answer, {"id": "active-r1", "text": "some record"})

    assert handoff.protected_action == "approve the transfer"
    assert handoff.resolver == "human"
    assert check_resolved(handoff, conductor) is False


@pytest.mark.parametrize(
    "record",
    [
        {"id": "r-wrong-role", "entity": "Lin", "role": "witness", "predicate": "received", "value": True},
        {"id": "r-swapped-entity", "entity": "Rhea", "role": "approver", "predicate": "transfer_status", "value": "rejected"},
    ],
)
@pytest.mark.xfail(strict=False, reason="DEFECT: check_resolved closes on any active cited record without checking role, entity, or polarity support.")
def test_unrelated_active_record_cannot_ground_resolution(tmp_path, record):
    handoff, _ = _handoff(tmp_path)
    answer = Reply(
        kind="ANSWER",
        answer="Lin approved the transfer and did not send it to Rhea.",
        record_ids=(record["id"],),
    )
    conductor = _AnsweringConductor(answer, record)

    assert check_resolved(handoff, conductor) is False
