from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace

import pytest

from verantyx.conductor import AgentQuestion, Reply
from verantyx.conductor_escalate import check_resolved, enrich
from verantyx.gap_graph import GapGraph
from verantyx.growth_signals import GrowthSignals


class Frame:
    def __init__(self, path):
        self.memory = SimpleNamespace(path=path)

    def _protected_action(self, text, *options):
        return None


def question(text="Which record applies?", options=None, claimed_state=None):
    return AgentQuestion(
        id="q-1", text=text, options=options, claimed_state=claimed_state
    )


def escalation(missing="DECISION", reason="", question_kind="FACT"):
    return Reply(
        kind="ESCALATE", missing=missing, reason=reason,
        question_kind=question_kind,
    )


def shelf_lookup(subject):
    return {
        "document": "records/decisions",
        "coverage_hole": False,
        "closest": [{"domain": "records.example"}],
        "repair": {"register": "Record a sourced decision."},
    }


class Conductor:
    def __init__(self, reply, active=()):
        self.reply = reply
        self.active = set(active)
        self.questions = []

    def answer(self, question):
        self.questions.append(question)
        return self.reply

    def _active_record(self, record_id):
        return {"id": record_id} if record_id in self.active else None


def make_handoff(tmp_path, reply=None, q=None, **kwargs):
    q = q or question()
    return enrich(
        reply or escalation(), Frame(tmp_path / "memory.jsonl"), q,
        shelf_lookup=shelf_lookup, **kwargs,
    )


def test_rejects_non_escalation_before_touching_frame():
    with pytest.raises(ValueError, match="ESCALATE"):
        enrich(Reply(kind="ANSWER"), None, question())


def test_requires_original_agent_question():
    with pytest.raises(ValueError, match="original AgentQuestion"):
        enrich(escalation(), None, None)


def test_reask_preserves_exact_question_and_all_fields(tmp_path):
    q = question("Pick A or B", ["A", "B"], {"state": "claimed"})

    handoff = make_handoff(tmp_path, q=q)

    assert handoff.reask is q
    assert handoff.question.options == ["A", "B"]
    assert handoff.question.claimed_state == {"state": "claimed"}
    assert handoff.as_dict()["reask"] == handoff.as_dict()["question"]


def test_repeated_enrich_is_idempotent_in_saved_sidecars(tmp_path):
    q = question()
    reply = escalation()
    frame = Frame(tmp_path / "memory.jsonl")

    first = enrich(reply, frame, q, shelf_lookup=shelf_lookup)
    second = enrich(reply, frame, q, shelf_lookup=shelf_lookup)
    graph = GapGraph.load(Path(first.graph_path))
    growth = GrowthSignals.load(Path(first.growth_path))

    assert first.gap_id == second.gap_id
    assert len(graph.nodes) == 1
    assert len(growth.branch_outcomes) == 1


def test_distinct_causes_for_same_subject_keep_distinct_gaps(tmp_path):
    q = question()
    first = make_handoff(tmp_path, escalation("DECISION", "no source"), q)
    second = make_handoff(tmp_path, escalation("DECISION", "conflicting record"), q)
    graph = GapGraph.load(Path(first.graph_path))

    assert first.gap_id != second.gap_id
    assert len(graph.nodes) == 2
    assert {node.failure_type for node in graph.nodes.values()} == {
        first.cause, second.cause,
    }


def test_empty_inputs_become_typed_missing_material(tmp_path):
    q = question("", [], None)
    handoff = make_handoff(tmp_path, escalation("", "", ""), q)

    assert handoff.question is q
    assert handoff.missing.kind == "record_kind"
    assert handoff.missing.value == "typed frame record"
    assert handoff.missing.record_kind is None


def test_large_question_and_missing_values_are_not_truncated(tmp_path):
    text = "Q" * 65_536
    missing = "RECORD_" + "x" * 65_536
    q = question(text)

    handoff = make_handoff(tmp_path, escalation(missing), q)

    assert handoff.subject == text
    assert handoff.question.text == text
    assert handoff.missing.value == missing


@pytest.mark.parametrize(
    "answer, active, expected",
    [
        (Reply(kind="ANSWER"), ("record-1",), False),
        (Reply(kind="ESCALATE", record_ids=("record-1",)), ("record-1",), False),
        (Reply(kind="ANSWER", record_ids=("stale",)), ("record-1",), False),
    ],
)
def test_reask_does_not_resolve_without_active_answer_citation(
    tmp_path, answer, active, expected
):
    q = question()
    handoff = make_handoff(tmp_path, q=q)
    conductor = Conductor(answer, active)

    assert check_resolved(handoff, conductor) is expected
    assert len(conductor.questions) == 1
    assert conductor.questions[0] is q


def test_active_record_answer_resolves_once_even_when_rechecked(tmp_path):
    q = question()
    handoff = make_handoff(tmp_path, q=q)
    conductor = Conductor(Reply(kind="ANSWER", record_ids=("record-1",)), ("record-1",))

    assert check_resolved(handoff, conductor)
    assert check_resolved(handoff, conductor)
    growth = GrowthSignals.load(Path(handoff.growth_path))
    graph = GapGraph.load(Path(handoff.graph_path))

    assert sum(bool(event.get("resolved")) for event in growth.branch_outcomes) == 1
    assert graph.get(handoff.gap_id).status == "RESOLVED"
    assert conductor.questions == [q, q]


def test_protected_action_cannot_be_closed_by_document_answer(tmp_path):
    q = question("Approve the transfer?")
    handoff = make_handoff(
        tmp_path,
        escalation("authority", "outside frame authority: approve transfer"),
        q,
    )
    conductor = Conductor(Reply(kind="ANSWER", record_ids=("record-1",)), ("record-1",))

    assert handoff.resolver == "human"
    assert handoff.protected_action == "approve transfer"
    assert not check_resolved(handoff, conductor)


def test_two_causes_are_order_independent(tmp_path):
    q = question()
    causes = [escalation("DECISION", "reason A"), escalation("STATUS", "reason B")]
    observed = []
    for label, ordered in (("forward", causes), ("reverse", list(reversed(causes)))):
        frame = Frame(tmp_path / label / "memory.jsonl")
        handoffs = []
        for reply in ordered:
            handoffs.append(enrich(reply, frame, q, shelf_lookup=shelf_lookup))
        graph = GapGraph.load(Path(handoffs[0].graph_path))
        observed.append(sorted(node.failure_type for node in graph.nodes.values()))

    assert observed[0] == observed[1]
    assert len(observed[0]) == 2


class BarrierGrowth(GrowthSignals):
    def __init__(self):
        super().__init__()
        self.resolution_barrier = Barrier(2)

    def record_branch_outcome(self, subject, verdict, branch, resolved=False):
        if resolved:
            self.resolution_barrier.wait(timeout=5)
        return super().record_branch_outcome(subject, verdict, branch, resolved)

    def save(self, path):
        return None


class NoSaveGraph(GapGraph):
    def save(self, path):
        return None


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: concurrent resolution checks can append duplicate resolved ledger outcomes",
)
def test_concurrent_rechecks_record_only_one_resolved_outcome(tmp_path):
    growth = BarrierGrowth()
    graph = NoSaveGraph()
    q = question()
    handoff = make_handoff(tmp_path, q=q, growth=growth, graph=graph)
    conductor = Conductor(Reply(kind="ANSWER", record_ids=("record-1",)), ("record-1",))

    with ThreadPoolExecutor(max_workers=2) as readers:
        results = list(readers.map(lambda _: check_resolved(handoff, conductor), range(2)))

    assert results == [True, True]
    assert sum(bool(event.get("resolved")) for event in growth.branch_outcomes) == 1
