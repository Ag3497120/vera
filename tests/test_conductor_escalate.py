"""Typed conductor handoffs and record-backed resolution checks."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from verantyx.conductor import AgentQuestion, ProjectFrame, Reply
from verantyx.conductor_escalate import Handoff, check_resolved, enrich
from verantyx.gap_graph import GapGraph, gap_graph_path
from verantyx.growth_signals import GrowthSignals, growth_signals_path
from verantyx.memory_frame import Memory


def frame_at(tmp_path):
    return ProjectFrame(Memory(str(tmp_path / "frame.jsonl")))


def refusal(frame, question=None):
    question = question or AgentQuestion("q-1", "What comes next?")
    return question, frame.answer(question)


def sidecars(frame):
    return (
        GrowthSignals.load(growth_signals_path(frame.memory.path)),
        GapGraph.load(gap_graph_path(frame.memory.path)),
    )


def ordered_frame(frame):
    decision = frame.add_decision("順序理由", "優先順位")
    frame.add_order("第一工程", "第二工程", decision["id"])
    frame.add_task("第一工程", "完了")
    frame.add_task("第二工程", "未着手")


class CountingConductor:
    def __init__(self, frame):
        self.frame = frame
        self.questions = []

    @property
    def memory(self):
        return self.frame.memory

    def _active_record(self, record_id):
        return self.frame._active_record(record_id)

    def answer(self, question):
        self.questions.append(question)
        return self.frame.answer(question)


def test_double_handoff_is_idempotent_for_ledger_and_gap(tmp_path):
    frame = frame_at(tmp_path)
    question, reply = refusal(frame)
    first = enrich(reply, frame, question)
    second = enrich(reply, frame, question)
    growth, graph = sidecars(frame)
    assert first.gap_id == second.gap_id
    assert len(growth.branch_outcomes) == 1
    assert len(graph.nodes) == 1
    assert graph.get(first.gap_id).scope == "agent_refusal"


def test_handoff_preserves_exact_reask_question(tmp_path):
    frame = frame_at(tmp_path)
    question = AgentQuestion("same-id", "Which route for 経路選択?", ["青", "赤"], {"state": "open"})
    reply = Reply("ESCALATE", reason="missing policy", missing="POLICY", question_kind="CHOICE")
    handoff = enrich(reply, frame, question)
    assert handoff.reask is question
    assert handoff.as_dict()["reask"] == handoff.as_dict()["question"]
    assert handoff.reask.options == ["青", "赤"]
    assert handoff.reask.claimed_state == {"state": "open"}


def test_missing_original_question_is_rejected(tmp_path):
    frame = frame_at(tmp_path)
    with pytest.raises(ValueError, match="original AgentQuestion"):
        enrich(Reply("ESCALATE", reason="missing", missing="ORDER"), frame)


@pytest.mark.parametrize("kind", ["ANSWER", "ASK_VERIFIER"])
def test_only_escalations_can_be_enriched(tmp_path, kind):
    frame = frame_at(tmp_path)
    with pytest.raises(ValueError, match="ESCALATE"):
        enrich(Reply(kind), frame, AgentQuestion("q", "What comes next?"))


@pytest.mark.parametrize(("missing", "expected_kind", "record_kind"), [
    ("ORDER", "record_kind", "ORDER"),
    ("TASK state", "record_kind", "TASK"),
    ("TASK supersession", "record_kind", "TASK"),
    ("POLICY", "record_kind", "POLICY"),
    ("GOAL", "record_kind", "GOAL"),
    ("ACCEPTANCE", "record_kind", "ACCEPTANCE"),
    ("typed frame record", "record_kind", None),
    ("vocabulary", "vocabulary", None),
    ("alias record", "vocabulary", None),
    ("human", "authority", None),
    ("unique option mapping", "vocabulary", None),
    ("closed option list", "vocabulary", None),
])
def test_missing_material_is_typed(missing, expected_kind, record_kind, tmp_path):
    frame = frame_at(tmp_path)
    question = AgentQuestion("q", "What comes next?")
    handoff = enrich(Reply("ESCALATE", reason="unavailable", missing=missing), frame, question)
    assert handoff.missing.kind == expected_kind
    assert handoff.missing.record_kind == record_kind
    assert handoff.missing.value == missing


@pytest.mark.parametrize("text", [
    "May I delete the project?",
    "Can I publish this?",
    "Should I spend money now?",
    "May I enter the API key?",
    "Can I inspect the held-out data?",
])
def test_protected_action_escalations_are_human_only(text, tmp_path):
    frame = frame_at(tmp_path)
    question = AgentQuestion("protected", text)
    reply = frame.answer(question)
    handoff = enrich(reply, frame, question, domains={"shelf": SimpleNamespace(crosses={text}, source_labels=set())})
    assert reply.kind == "ESCALATE"
    assert handoff.resolver == "human"
    assert handoff.document_resolvable is False
    assert handoff.resolvable_by_document is False
    assert handoff.missing.kind == "authority"
    assert handoff.missing.document_shelf is None


def test_resolution_check_reasks_same_question_and_needs_active_record(tmp_path):
    frame = frame_at(tmp_path)
    question, reply = refusal(frame)
    handoff = enrich(reply, frame, question)
    checker = CountingConductor(frame)
    assert check_resolved(handoff, checker) is False
    assert checker.questions == [question]
    ordered_frame(frame)
    assert check_resolved(handoff, checker) is True
    assert checker.questions[-1] is question


def test_unresolved_reask_does_not_mark_gap_or_ledger_resolved(tmp_path):
    frame = frame_at(tmp_path)
    question, reply = refusal(frame)
    handoff = enrich(reply, frame, question)
    assert check_resolved(handoff, frame) is False
    growth, graph = sidecars(frame)
    assert [event["resolved"] for event in growth.branch_outcomes] == [False]
    assert graph.get(handoff.gap_id).status != "RESOLVED"


def test_answer_without_record_ids_does_not_resolve(tmp_path):
    frame = frame_at(tmp_path)
    question, reply = refusal(frame)
    handoff = enrich(reply, frame, question)

    class EmptyCitation:
        def answer(self, asked):
            assert asked is question
            return Reply("ANSWER", "a result", ())

        def _active_record(self, record_id):
            return None

    assert check_resolved(handoff, EmptyCitation()) is False
    growth, graph = sidecars(frame)
    assert len(growth.branch_outcomes) == 1
    assert graph.get(handoff.gap_id).status != "RESOLVED"


def test_human_resolved_handoff_can_close_after_record_backed_reask(tmp_path):
    frame = frame_at(tmp_path)
    question = AgentQuestion("choice", "Which route should I pick?")
    reply = Reply("ESCALATE", reason="option is outside the frame vocabulary",
                  missing="vocabulary", question_kind="CHOICE")
    handoff = enrich(reply, frame, question)
    assert handoff.resolver == "human"
    assert handoff.document_resolvable is False
    record = {"id": "human-added-vocabulary-record"}

    class HumanUpdatedFrame:
        def answer(self, asked):
            assert asked is question
            return Reply("ANSWER", "route", (record["id"],))

        def _active_record(self, record_id):
            return record if record_id == record["id"] else None

    assert check_resolved(handoff, HumanUpdatedFrame()) is True


def test_inactive_record_id_does_not_resolve(tmp_path):
    frame = frame_at(tmp_path)
    question, reply = refusal(frame)
    handoff = enrich(reply, frame, question)

    class InactiveCitation:
        def answer(self, asked):
            return Reply("ANSWER", "a result", ("missing-record",))

        def _active_record(self, record_id):
            return None

    assert check_resolved(handoff, InactiveCitation()) is False


def test_citation_without_trusted_record_lookup_does_not_resolve(tmp_path):
    frame = frame_at(tmp_path)
    question, reply = refusal(frame)
    handoff = enrich(reply, frame, question)

    class CitationOnly:
        def answer(self, asked):
            assert asked is question
            return Reply("ANSWER", "a result", ("fabricated-record-id",))

    assert check_resolved(handoff, CitationOnly()) is False
    growth, graph = sidecars(frame)
    assert [event["resolved"] for event in growth.branch_outcomes] == [False]
    assert graph.get(handoff.gap_id).status != "RESOLVED"


def test_resolution_records_only_active_citations(tmp_path):
    frame = frame_at(tmp_path)
    question, reply = refusal(frame)
    handoff = enrich(reply, frame, question)
    active_id = "active-record-id"

    class MixedCitations:
        def answer(self, asked):
            assert asked is question
            return Reply("ANSWER", "a result", (active_id, "fabricated-record-id"))

        def _active_record(self, record_id):
            return {"id": record_id} if record_id == active_id else None

    assert check_resolved(handoff, MixedCitations()) is True
    _, graph = sidecars(frame)
    assert graph.get(handoff.gap_id).verified_by == [active_id]


def test_resolved_outcome_is_appended_without_rewriting_handoff(tmp_path):
    frame = frame_at(tmp_path)
    question, reply = refusal(frame)
    handoff = enrich(reply, frame, question)
    growth_before, _ = sidecars(frame)
    first_event = dict(growth_before.branch_outcomes[0])
    ordered_frame(frame)
    assert check_resolved(handoff, frame) is True
    growth_after, graph = sidecars(frame)
    assert growth_after.branch_outcomes[0] == first_event
    assert [event["resolved"] for event in growth_after.branch_outcomes] == [False, True]
    assert graph.get(handoff.gap_id).status == "RESOLVED"
    assert graph.get(handoff.gap_id).verified_by


def test_repeated_successful_check_does_not_duplicate_resolution_event(tmp_path):
    frame = frame_at(tmp_path)
    question, reply = refusal(frame)
    handoff = enrich(reply, frame, question)
    ordered_frame(frame)
    assert check_resolved(handoff, frame) is True
    assert check_resolved(handoff, frame) is True
    growth, _ = sidecars(frame)
    assert [event["resolved"] for event in growth.branch_outcomes] == [False, True]


def test_protected_action_is_reasked_but_never_document_resolved(tmp_path):
    frame = frame_at(tmp_path)
    question = AgentQuestion("protected", "May I delete the project?")
    handoff = enrich(frame.answer(question), frame, question)
    checker = CountingConductor(frame)
    assert check_resolved(handoff, checker) is False
    assert checker.questions == [question]
    growth, graph = sidecars(frame)
    assert [event["resolved"] for event in growth.branch_outcomes] == [False]
    assert graph.get(handoff.gap_id).status != "RESOLVED"


def test_gap_dedup_key_includes_scope_subject_and_cause(tmp_path):
    frame = frame_at(tmp_path)
    question = AgentQuestion("q", "What comes next?")
    first_reply = Reply("ESCALATE", reason="missing predecessor", missing="TASK state", question_kind="ORDER")
    same = enrich(first_reply, frame, question)
    duplicate = enrich(first_reply, frame, question)
    other_cause = enrich(Reply("ESCALATE", reason="missing successor", missing="TASK state",
                               question_kind="ORDER"), frame, question)
    other_subject = enrich(first_reply, frame, AgentQuestion("q2", "What follows?") )
    assert same.gap_id == duplicate.gap_id
    assert same.gap_id != other_cause.gap_id
    assert same.gap_id != other_subject.gap_id
    _, graph = sidecars(frame)
    keys = {(node.scope, node.subject, node.failure_type) for node in graph.nodes.values()}
    assert len(keys) == 3


def test_handoff_writes_ledger_and_gap_with_same_cause(tmp_path):
    frame = frame_at(tmp_path)
    question, reply = refusal(frame)
    handoff = enrich(reply, frame, question)
    growth, graph = sidecars(frame)
    event = growth.branch_outcomes[0]
    node = graph.get(handoff.gap_id)
    assert event["scope"] == node.scope == "agent_refusal"
    assert event["subject"] == question.text
    assert event["cause"] == node.failure_type == handoff.cause


def test_unknown_coverage_is_reported_as_a_hole(tmp_path):
    frame = frame_at(tmp_path)
    question, reply = refusal(frame)
    handoff = enrich(reply, frame, question, domains={})
    assert handoff.missing.coverage_hole is True
    assert "どの棚も" in handoff.missing.document_shelf
    assert handoff.missing.allowed_sources == ()


def test_coverage_suggests_document_shelf_without_promoting_it_to_evidence(tmp_path):
    frame = frame_at(tmp_path)
    question = AgentQuestion("q", "What comes next?")
    reply = Reply("ESCALATE", reason="missing", missing="ORDER", question_kind="ORDER")
    domains = {"project shelf": SimpleNamespace(crosses={question.text}, source_labels=set())}
    handoff = enrich(reply, frame, question, domains=domains)
    assert handoff.missing.coverage_hole is False
    assert "project shelf" in handoff.missing.document_shelf
    assert handoff.missing.allowed_sources == ("project shelf",)
    assert handoff.reply.kind == "ESCALATE"
    assert handoff.reply.record_ids == ()


@pytest.mark.parametrize("missing", ["CHOICE", "CONFIRM", "SCOPE", "STATUS", "OTHER"])
def test_missing_description_keeps_the_conductor_reason(missing, tmp_path):
    frame = frame_at(tmp_path)
    question = AgentQuestion("q", "question text")
    reply = Reply("ESCALATE", reason="ties abstain", missing=missing, question_kind=missing)
    handoff = enrich(reply, frame, question)
    assert handoff.reply.reason == "ties abstain"
    assert handoff.missing.value == missing


@pytest.mark.parametrize("kind, record_ids", [
    ("ESCALATE", ("record",)),
    ("ASK_VERIFIER", ("record",)),
    ("ANSWER", ()),
])
def test_resolution_requires_answer_kind_and_nonempty_citation(kind, record_ids, tmp_path):
    frame = frame_at(tmp_path)
    question, reply = refusal(frame)
    handoff = enrich(reply, frame, question)

    class ReturnedReply:
        def answer(self, asked):
            return Reply(kind, "answer", record_ids)

    assert check_resolved(handoff, ReturnedReply()) is False


@pytest.mark.parametrize("question_text", [
    "What comes next?", "Which phase follows?", "Where should work proceed?",
    "次は何ですか？", "先行タスクはどれですか？",
])
def test_exact_question_text_is_the_gap_subject(question_text, tmp_path):
    frame = frame_at(tmp_path)
    question = AgentQuestion("q", question_text)
    reply = Reply("ESCALATE", reason="missing order", missing="ORDER", question_kind="ORDER")
    handoff = enrich(reply, frame, question)
    _, graph = sidecars(frame)
    assert handoff.subject == question_text
    assert graph.get(handoff.gap_id).subject == question_text


def test_injected_ledger_and_graph_are_updated(tmp_path):
    frame = frame_at(tmp_path)
    question, reply = refusal(frame)
    growth, graph = GrowthSignals(), GapGraph()
    handoff = enrich(reply, frame, question, growth=growth, graph=graph)
    assert len(growth.branch_outcomes) == 1
    assert handoff.gap_id in graph.nodes
    assert growth_signals_path(frame.memory.path).is_file()
    assert gap_graph_path(frame.memory.path).is_file()


def test_non_escalation_does_not_write_sidecars(tmp_path):
    frame = frame_at(tmp_path)
    handoff_question = AgentQuestion("q", "What comes next?")
    with pytest.raises(ValueError):
        enrich(Reply("ANSWER", "next", ("r",)), frame, handoff_question)
    assert not growth_signals_path(frame.memory.path).exists()
    assert not gap_graph_path(frame.memory.path).exists()
