from dataclasses import replace

import pytest

from verantyx.conductor import AgentQuestion, ProjectFrame
from verantyx.conductor_escalate import check_resolved, enrich


class _FixedAnswer:
    def __init__(self, reply, frame=None):
        self.reply = reply
        self.frame = frame
        self.questions = []

    def answer(self, question):
        self.questions.append(question)
        return self.reply

    def _active_record(self, record_id):
        if self.frame is None:
            return None
        return self.frame._active_record(record_id)


def _escalate(frame, text="What is next?", *, options=None, claimed_state=None):
    question = AgentQuestion(
        "q", text, options=options, claimed_state=claimed_state,
    )
    return question, frame.answer(question)


def test_plain_and_polite_questions_keep_their_exact_reask(tmp_path):
    frame = ProjectFrame(tmp_path / "plain-polite.jsonl")
    plain, plain_reply = _escalate(frame, "What is next?")
    polite, polite_reply = _escalate(frame, "Could you tell me what comes next?")

    plain_handoff = enrich(plain_reply, frame, plain)
    polite_handoff = enrich(polite_reply, frame, polite)

    assert plain_reply.kind == polite_reply.kind == "ESCALATE"
    assert plain_handoff.reask is plain
    assert polite_handoff.reask is polite
    assert plain_handoff.reask.text != polite_handoff.reask.text


def test_reask_retains_options_and_claimed_state(tmp_path):
    frame = ProjectFrame(tmp_path / "question-shape.jsonl")
    question, reply = _escalate(
        frame, "Which route should I take?", options=("north", "south"),
        claimed_state={"route": "north"},
    )

    handoff = enrich(reply, frame, question)

    assert handoff.reask == question
    assert handoff.as_dict()["reask"] == {
        "id": question.id,
        "text": question.text,
        "options": ["north", "south"],
        "claimed_state": {"route": "north"},
    }


def test_closed_option_escalation_is_routed_to_a_human(tmp_path):
    frame = ProjectFrame(tmp_path / "closed-options.jsonl")
    question, reply = _escalate(
        frame, "Which option should I choose?", options=("approve", "reject"),
    )

    handoff = enrich(reply, frame, question)

    assert reply.kind == "ESCALATE"
    assert handoff.missing.kind == "vocabulary"
    assert handoff.resolver == "human"
    assert handoff.document_resolvable is False


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: allowed-choice paraphrase is routed to documents instead of a human",
)
def test_allowed_choice_paraphrase_keeps_human_resolution(tmp_path):
    frame = ProjectFrame(tmp_path / "choice-paraphrase.jsonl")
    question, reply = _escalate(
        frame, "Which option should I choose?", options=("approve", "reject"),
    )
    paraphrased = replace(reply, missing="list of allowed choices")

    baseline = enrich(reply, frame, question)
    variant = enrich(paraphrased, frame, question)

    assert baseline.resolver == variant.resolver == "human"
    assert baseline.missing.kind == variant.missing.kind == "vocabulary"


def test_duplicate_enrichment_records_one_pending_refusal(tmp_path):
    frame = ProjectFrame(tmp_path / "duplicate.jsonl")
    question, reply = _escalate(frame)

    first = enrich(reply, frame, question)
    second = enrich(reply, frame, question)

    assert second.gap_id == first.gap_id
    assert len(second._growth.branch_outcomes) == 1
    assert len(second._graph.nodes) == 1


def test_unresolved_reask_does_not_close_the_gap(tmp_path):
    frame = ProjectFrame(tmp_path / "still-missing.jsonl")
    question, reply = _escalate(frame)
    handoff = enrich(reply, frame, question)

    assert check_resolved(handoff, frame) is False
    assert handoff._graph.get(handoff.gap_id).status != "RESOLVED"


def test_reask_closes_only_after_an_active_record_answers(tmp_path):
    frame = ProjectFrame(tmp_path / "resolved.jsonl")
    question, reply = _escalate(frame)
    handoff = enrich(reply, frame, question)
    authority = frame.add_decision("phase ordering", "A before B")
    frame.add_task("A", "完了")
    frame.add_task("B", "未着手")
    edge = frame.add_order("A", "B", authority["id"])
    answer = frame.answer(question)
    recorder = _FixedAnswer(answer, frame)

    assert answer.kind == "ANSWER"
    assert edge["id"] in answer.record_ids
    assert check_resolved(handoff, recorder) is True
    assert recorder.questions == [question]
    assert handoff._graph.get(handoff.gap_id).status == "RESOLVED"


def test_answer_without_citations_does_not_resolve(tmp_path):
    frame = ProjectFrame(tmp_path / "no-citations.jsonl")
    question, reply = _escalate(frame)
    handoff = enrich(reply, frame, question)
    authority = frame.add_decision("phase ordering", "A before B")
    frame.add_task("A", "完了")
    frame.add_task("B", "未着手")
    frame.add_order("A", "B", authority["id"])
    answer = frame.answer(question)
    ungrounded = replace(answer, record_ids=())

    assert answer.kind == "ANSWER"
    assert check_resolved(handoff, _FixedAnswer(ungrounded, frame)) is False
    assert handoff._graph.get(handoff.gap_id).status != "RESOLVED"


def test_inactive_record_citation_does_not_resolve(tmp_path):
    frame = ProjectFrame(tmp_path / "inactive-citation.jsonl")
    question, reply = _escalate(frame)
    handoff = enrich(reply, frame, question)
    authority = frame.add_decision("phase ordering", "A before B")
    frame.add_task("A", "完了")
    frame.add_task("B", "未着手")
    frame.add_order("A", "B", authority["id"])
    answer = frame.answer(question)
    inactive = replace(answer, record_ids=("missing-record",))

    assert answer.kind == "ANSWER"
    assert check_resolved(handoff, _FixedAnswer(inactive, frame)) is False
    assert handoff._graph.get(handoff.gap_id).status != "RESOLVED"


def test_protected_action_cannot_be_closed_by_an_answer(tmp_path):
    frame = ProjectFrame(tmp_path / "protected.jsonl")
    question, reply = _escalate(frame, "Can I publish the draft?")
    handoff = enrich(reply, frame, question)
    task = frame.add_task("status", "進行中")
    supported = frame.answer(AgentQuestion(
        "status", "What is the status?",
        claimed_state={"task_id": "status", "state": "claimed"},
    ))

    assert handoff.protected_action
    assert supported.kind == "ANSWER"
    assert task["id"] in supported.record_ids
    assert check_resolved(handoff, _FixedAnswer(supported, frame)) is False
    assert handoff._graph.get(handoff.gap_id).status != "RESOLVED"
