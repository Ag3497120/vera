"""Adversarial contract checks for typed conductor escalations."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from verantyx.conductor import AgentQuestion, Reply
from verantyx.conductor_escalate import check_resolved, enrich
from verantyx.gap_graph import GapGraph
from verantyx.growth_signals import GrowthSignals


class _Frame:
    def __init__(self, path: Path) -> None:
        self.memory = SimpleNamespace(path=path)


class _Conductor:
    def __init__(self, reply: Reply, active_ids: tuple[str, ...] | None = None) -> None:
        self._reply = reply
        self.questions = []
        if active_ids is not None:
            self.memory = SimpleNamespace(
                active=lambda: [{"id": record_id} for record_id in active_ids]
            )

    def answer(self, question: AgentQuestion) -> Reply:
        self.questions.append(question)
        return self._reply


def _question(text: str = "Which record supports this claim?") -> AgentQuestion:
    return AgentQuestion(
        id="question-1",
        text=text,
        options=["supported", "unknown"],
        claimed_state={"state": "Unknown"},
    )


def _escalation(
    *, missing: str = "PERMIT_RECORD", reason: str = "record is absent",
    question_kind: str = "RECORD",
) -> Reply:
    return Reply(
        kind="ESCALATE", missing=missing, reason=reason,
        question_kind=question_kind,
    )


def _enrich(
    tmp_path: Path,
    *,
    question: AgentQuestion | None = None,
    reply: Reply | None = None,
    growth: GrowthSignals | None = None,
    graph: GapGraph | None = None,
    **kwargs,
):
    return enrich(
        reply or _escalation(),
        _Frame(tmp_path / "memory.json"),
        question or _question(),
        growth=growth or GrowthSignals(),
        graph=graph or GapGraph(),
        **kwargs,
    )


def test_enrich_rejects_non_escalations_and_missing_original_question(tmp_path):
    question = _question()
    with pytest.raises(ValueError, match="ESCALATE"):
        enrich(Reply(kind="ANSWER", answer="yes", record_ids=("r1",)), object(), question)
    with pytest.raises(ValueError, match="original AgentQuestion"):
        enrich(_escalation(), object())


def test_handoff_preserves_exact_reask_and_writes_refusal_sidecars(tmp_path):
    question = _question("Which permit is recorded for the station?")
    growth, graph = GrowthSignals(), GapGraph()
    handoff = _enrich(tmp_path, question=question, growth=growth, graph=graph)

    assert handoff.reask is question
    assert handoff.as_dict()["reask"] == handoff.as_dict()["question"]
    assert handoff.reply.kind == "ESCALATE"
    saved_growth = json.loads(Path(handoff.growth_path).read_text())
    saved_graph = json.loads(Path(handoff.graph_path).read_text())
    assert len(saved_growth["branch_outcomes"]) == 1
    assert saved_growth["branch_outcomes"][0]["resolved"] is False
    assert saved_growth["branch_outcomes"][0]["cause"] == handoff.cause
    assert saved_graph[handoff.gap_id]["status"] == "DETECTED"


def test_record_kind_and_shelf_metadata_are_typed_without_answering(tmp_path):
    handoff = _enrich(
        tmp_path,
        subject="Northfield station",
        shelf_lookup=lambda _: {
            "document": "permits/rail.json",
            "coverage_hole": True,
            "closest": [{"domain": "transport.gov.example"}],
        },
    )

    assert handoff.missing.kind == "record_kind"
    assert handoff.missing.record_kind == "PERMIT_RECORD"
    assert handoff.missing.document_shelf == "permits/rail.json"
    assert handoff.missing.allowed_sources == ("transport.gov.example",)
    assert handoff.missing.coverage_hole is True
    assert handoff.reply.kind == "ESCALATE"
    assert handoff.as_dict()["reply"]["answer"] is None


def test_outside_authority_handoff_cannot_close_from_a_cited_answer(tmp_path):
    question = _question("May the agent approve a transfer?")
    handoff = _enrich(
        tmp_path, question=question,
        reply=_escalation(
            missing="APPROVAL_RECORD",
            reason="outside frame authority: approve transfer",
        ),
    )
    conductor = _Conductor(Reply(kind="ANSWER", answer="approved", record_ids=("r1",)))

    assert handoff.resolver == "human"
    assert handoff.document_resolvable is False
    assert handoff.protected_action == "approve transfer"
    assert check_resolved(handoff, conductor) is False
    assert conductor.questions == [question]


def test_vocabulary_gap_requires_human_resolution_route(tmp_path):
    handoff = _enrich(tmp_path, reply=_escalation(missing="closed option vocabulary"))

    assert handoff.missing.kind == "vocabulary"
    assert handoff.resolver == "human"
    assert handoff.document_resolvable is False
    assert "human" in handoff.missing.instruction.casefold()


def test_reask_does_not_close_on_non_answer_even_with_record_id(tmp_path):
    handoff = _enrich(tmp_path)
    conductor = _Conductor(Reply(kind="ESCALATE", record_ids=("r1",)))

    assert check_resolved(handoff, conductor) is False
    assert handoff._graph.get(handoff.gap_id).status == "DETECTED"
    assert len(handoff._growth.branch_outcomes) == 1


def test_reask_answer_without_record_citation_does_not_close(tmp_path):
    handoff = _enrich(tmp_path)
    conductor = _Conductor(Reply(kind="ANSWER", answer="yes"))

    assert check_resolved(handoff, conductor) is False
    assert handoff._graph.get(handoff.gap_id).status == "DETECTED"
    assert len(handoff._growth.branch_outcomes) == 1


def test_reask_citation_must_name_an_active_record_and_then_closes(tmp_path):
    handoff = _enrich(tmp_path)
    assert check_resolved(
        handoff,
        _Conductor(Reply(kind="ANSWER", answer="yes", record_ids=("stale",)), ("active",)),
    ) is False

    active_conductor = _Conductor(
        Reply(kind="ANSWER", answer="yes", record_ids=("active",)), ("active",)
    )
    assert check_resolved(handoff, active_conductor) is True
    assert active_conductor.questions == [handoff.question]
    assert handoff._graph.get(handoff.gap_id).status == "RESOLVED"
    assert [event["resolved"] for event in handoff._growth.branch_outcomes] == [False, True]


def test_repeated_resolution_check_does_not_duplicate_resolved_ledger_entry(tmp_path):
    handoff = _enrich(tmp_path)
    conductor = _Conductor(Reply(kind="ANSWER", answer="yes", record_ids=("r1",)))

    assert check_resolved(handoff, conductor) is True
    assert check_resolved(handoff, conductor) is True
    assert len(handoff._growth.branch_outcomes) == 2
    assert sum(event["resolved"] for event in handoff._growth.branch_outcomes) == 1


def test_duplicate_enrichment_deduplicates_gap_and_unresolved_outcome(tmp_path):
    growth, graph, question = GrowthSignals(), GapGraph(), _question()
    first = _enrich(tmp_path, question=question, growth=growth, graph=graph)
    second = _enrich(tmp_path, question=question, growth=growth, graph=graph)

    assert first.gap_id == second.gap_id
    assert len(graph.nodes) == 1
    assert len(growth.branch_outcomes) == 1


def test_same_subject_with_distinct_refusal_causes_keeps_parallel_gaps(tmp_path):
    growth, graph, question = GrowthSignals(), GapGraph(), _question("Northfield permit status")
    first = _enrich(tmp_path, question=question, growth=growth, graph=graph)
    second = _enrich(
        tmp_path,
        question=question,
        reply=_escalation(reason="source does not establish status"),
        growth=growth,
        graph=graph,
    )

    assert first.gap_id != second.gap_id
    assert len(graph.nodes) == 2
    assert len(growth.branch_outcomes) == 2
