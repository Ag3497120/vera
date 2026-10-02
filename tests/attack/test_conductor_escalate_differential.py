"""Differential checks for typed conductor escalation handoffs."""
from __future__ import annotations

import itertools
import re
from types import SimpleNamespace

import pytest

from verantyx.conductor import AgentQuestion, Reply
from verantyx.conductor_escalate import check_resolved, enrich


_RECORD_KIND = re.compile(r"\b([A-Z][A-Z0-9_]{1,})\b")
_PROTECTED = re.compile(r"outside frame authority|outside-authority action", re.I)


def _typed(cls, **values):
    """Build only the typed fields exercised here, independent of defaults."""
    value = object.__new__(cls)
    for name, item in values.items():
        object.__setattr__(value, name, item)
    return value


def _question(index=0, *, text=None, options=None, claimed_state=None):
    return _typed(
        AgentQuestion,
        id=f"q-{index}",
        text=text if text is not None else f"Where is item {index}?",
        options=options,
        claimed_state=claimed_state,
    )


def _reply(*, kind="ESCALATE", missing="typed frame record", reason="not found",
           question_kind=None, record_ids=()):
    return _typed(
        Reply, kind=kind, missing=missing, reason=reason,
        question_kind=question_kind, record_ids=record_ids,
    )


class _Growth:
    def __init__(self):
        self.branch_outcomes = []

    def record_branch_outcome(self, subject, verdict, branch, resolved):
        self.branch_outcomes.append({
            "subject": subject, "verdict": verdict, "branch": branch,
            "resolved": resolved,
        })

    def save(self, _path):
        pass


class _Node:
    def __init__(self, gap_id, *, gap_type, subject, scope, severity,
                 failure_type, acquisition_methods, allowed_sources):
        self.gap_id = gap_id
        self.gap_type = gap_type
        self.subject = subject
        self.scope = scope
        self.severity = severity
        self.failure_type = failure_type
        self.acquisition_methods = list(acquisition_methods)
        self.allowed_sources = list(allowed_sources or [])
        self.status = "OPEN"


class _Graph:
    def __init__(self):
        self.nodes = {}
        self._next_id = 0

    def create(self, **values):
        for node in self.nodes.values():
            if node.scope == values["scope"] and node.subject == values["subject"]:
                return node
        self._next_id += 1
        node = _Node(f"gap-{self._next_id}", **values)
        self.nodes[node.gap_id] = node
        return node

    def get(self, gap_id):
        return self.nodes.get(gap_id)

    def set_status(self, gap_id, status, *, resolution, verified_by):
        node = self.nodes[gap_id]
        node.status = status
        node.resolution = resolution
        node.verified_by = list(verified_by)

    def save(self, _path):
        pass


def _reference(reply, question, *, subject=None, shelf=None):
    """Naive contract model; it does not call the implementation under test."""
    query_subject = question.text if subject is None else subject
    reason = reply.reason or ""
    missing = str(reply.missing or "typed frame record").strip()
    protected = None
    if _PROTECTED.search(reason):
        protected = reason.partition(":")[-1].strip() or "protected action"

    folded = missing.casefold()
    if protected or "human" in folded or "authority" in folded:
        material = {
            "kind": "authority", "value": protected or missing,
            "record_kind": None, "vocabulary": None, "document_shelf": None,
            "allowed_sources": (), "coverage_hole": None,
            "instruction": "A human must supply or approve the authoritative record; a document cannot authorize this action.",
        }
    elif any(term in folded for term in ("vocabulary", "alias", "option mapping", "closed option")):
        material = {
            "kind": "vocabulary", "value": missing, "record_kind": None,
            "vocabulary": ("the closed frame vocabulary for this question"
                           if folded == "vocabulary" else missing),
            "document_shelf": None, "allowed_sources": (), "coverage_hole": None,
            "instruction": "A human must add or confirm the exact vocabulary term in the frame.",
        }
    else:
        found = _RECORD_KIND.search(missing)
        shelf = shelf or {}
        closest = shelf.get("closest") or []
        repair = shelf.get("repair")
        material = {
            "kind": "record_kind", "value": missing,
            "record_kind": found.group(1) if found else None,
            "vocabulary": None,
            "document_shelf": str(shelf["document"]) if shelf.get("document") else None,
            "allowed_sources": tuple(str(row["domain"]) for row in closest
                                      if isinstance(row, dict) and row.get("domain")),
            "coverage_hole": shelf.get("coverage_hole"),
            "instruction": (str(repair["register"]) if isinstance(repair, dict)
                            and repair.get("register") else
                            "Provide a source document that states the missing material, then add its typed frame record."),
        }

    resolver = "human" if protected or "human" in folded else "document"
    if material["kind"] in ("authority", "vocabulary"):
        resolver = "human"
    cause = "|".join((reply.question_kind or "OTHER", reply.missing or "", reason))
    return {
        "question": question, "subject": query_subject, "protected": protected,
        "material": material, "resolver": resolver, "cause": cause,
        "branch": resolver, "document_resolvable": resolver == "document",
        "initially_resolved": False,
    }


_SHELF = {
    "document": "shelf://sample",
    "closest": [{"domain": "archive.example"}, {"other": "ignored"}],
    "coverage_hole": True,
    "repair": {"register": "Register a sourced typed record."},
}


def _run(tmp_path, reply, question, *, subject=None, shelf=None, growth=None, graph=None):
    growth = growth or _Growth()
    graph = graph or _Graph()
    frame = SimpleNamespace(memory=SimpleNamespace(path=str(tmp_path / "records.jsonl")))
    handoff = enrich(
        reply, frame, question, subject=subject,
        shelf_lookup=(lambda _subject: shelf) if shelf is not None else (lambda _subject: _SHELF),
        growth=growth, graph=graph,
    )
    return handoff, growth, graph


def _assert_matches_reference(handoff, expected):
    material = dict(expected["material"])
    material["allowed_sources"] = list(material["allowed_sources"])
    assert handoff.reask is expected["question"]
    assert handoff.subject == expected["subject"]
    assert handoff.protected_action == expected["protected"]
    assert handoff.missing.as_dict() == material
    assert handoff.resolver == expected["resolver"]
    assert handoff.cause == expected["cause"]
    assert handoff.branch == expected["branch"]
    assert handoff.document_resolvable is expected["document_resolvable"]


def test_generated_escalations_match_independent_reference(tmp_path):
    missing_values = (
        "RULE", "human approval", "authority record", "vocabulary",
        "closed option mismatch", "typed frame record", "plain description",
    )
    reasons = (
        "record unavailable", "outside frame authority: transfer funds",
        "outside-authority action: reveal key",
    )
    question_kinds = (None, "RECORD_LOOKUP", "OPTION")
    for index, (missing, reason, question_kind) in enumerate(
        itertools.product(missing_values, reasons, question_kinds)
    ):
        question = _question(index, text=f"  Item {index}?  ",
                             options=("yes", "no") if index % 2 else None,
                             claimed_state="unknown" if index % 3 == 0 else None)
        reply = _reply(missing=missing, reason=reason, question_kind=question_kind)
        expected = _reference(reply, question, subject=f"Item {index}", shelf=_SHELF)
        handoff, growth, graph = _run(
            tmp_path / str(index), reply, question,
            subject=f"Item {index}", growth=_Growth(), graph=_Graph(),
        )
        _assert_matches_reference(handoff, expected)
        assert len(growth.branch_outcomes) == 1
        assert growth.branch_outcomes[0]["resolved"] is False
        node = graph.get(handoff.gap_id)
        assert node is not None and node.failure_type == expected["cause"]


def test_rejects_non_escalation_and_missing_original_question():
    question = _question()
    frame = SimpleNamespace(memory=SimpleNamespace(path="unused.jsonl"))
    with pytest.raises(ValueError, match="ESCALATE"):
        enrich(_reply(kind="ANSWER"), frame, question)
    with pytest.raises(ValueError, match="original AgentQuestion"):
        enrich(_reply(), frame, None)


def test_shelf_lookup_json_string_is_typed_into_repair_fields(tmp_path):
    question = _question(80)
    reply = _reply(missing="POLICY", question_kind="RECORD_LOOKUP")
    shelf = ('{"document":"shelf://json", "coverage_hole":false, '
             '"closest":[{"domain":"policy.example"}], '
             '"repair":{"register":"Add cited POLICY."}}')
    expected_shelf = {
        "document": "shelf://json", "coverage_hole": False,
        "closest": [{"domain": "policy.example"}],
        "repair": {"register": "Add cited POLICY."},
    }
    handoff, _, _ = _run(tmp_path, reply, question, shelf=shelf)
    _assert_matches_reference(handoff, _reference(reply, question, shelf=expected_shelf))


def test_duplicate_refusal_is_recorded_once(tmp_path):
    question = _question(81, text="Which policy applies?")
    reply = _reply(missing="POLICY", reason="missing record", question_kind="LOOKUP")
    growth, graph = _Growth(), _Graph()
    first, _, _ = _run(tmp_path, reply, question, growth=growth, graph=graph)
    second, _, _ = _run(tmp_path, reply, question, growth=growth, graph=graph)
    assert first.gap_id == second.gap_id
    assert len(graph.nodes) == 1
    assert len(growth.branch_outcomes) == 1


class _AnsweringConductor:
    def __init__(self, answer, active_ids=()):
        self.answer_value = answer
        self.active_ids = set(active_ids)
        self.asked = []

    def answer(self, question):
        self.asked.append(question)
        return self.answer_value

    def _active_record(self, record_id):
        return {"id": record_id} if record_id in self.active_ids else None


def test_resolution_needs_answer_with_active_record_citation(tmp_path):
    question = _question(82, text="Which policy applies?")
    reply = _reply(missing="POLICY", reason="missing record", question_kind="LOOKUP")
    handoff, growth, graph = _run(tmp_path, reply, question)
    answer = _reply(kind="ANSWER", record_ids=("stale-record",))
    conductor = _AnsweringConductor(answer, active_ids=("active-record",))
    assert check_resolved(handoff, conductor) is False
    assert conductor.asked == [question]
    assert not any(event["resolved"] for event in growth.branch_outcomes)
    assert graph.get(handoff.gap_id).status == "OPEN"

    answer = _reply(kind="ANSWER", record_ids=("active-record",))
    conductor.answer_value = answer
    assert check_resolved(handoff, conductor) is True
    assert conductor.asked[-1] is question
    assert [event["resolved"] for event in growth.branch_outcomes] == [False, True]
    node = graph.get(handoff.gap_id)
    assert node.status == "RESOLVED"
    assert node.verified_by == ["active-record"]


def test_protected_action_stays_open_after_cited_answer(tmp_path):
    question = _question(83, text="May I transfer funds?", options=("yes", "no"))
    reply = _reply(missing="authority approval",
                   reason="outside frame authority: transfer funds")
    handoff, growth, graph = _run(tmp_path, reply, question)
    conductor = _AnsweringConductor(
        _reply(kind="ANSWER", record_ids=("active-record",)),
        active_ids=("active-record",),
    )
    assert check_resolved(handoff, conductor) is False
    assert conductor.asked == [question]
    assert [event["resolved"] for event in growth.branch_outcomes] == [False]
    assert graph.get(handoff.gap_id).status == "OPEN"


def test_resolution_rejects_uncited_and_non_answer_replies(tmp_path):
    question = _question(84)
    reply = _reply(missing="RULE", reason="missing")
    handoff, growth, graph = _run(tmp_path, reply, question)
    for answer in (_reply(kind="ANSWER", record_ids=()),
                   _reply(kind="ESCALATE", record_ids=("active-record",))):
        conductor = _AnsweringConductor(answer, active_ids=("active-record",))
        assert check_resolved(handoff, conductor) is False
    assert [event["resolved"] for event in growth.branch_outcomes] == [False]
    assert graph.get(handoff.gap_id).status == "OPEN"


def test_repeated_successful_reask_keeps_one_resolved_outcome(tmp_path):
    question = _question(85, text="Which policy applies?")
    reply = _reply(missing="POLICY", reason="missing record")
    handoff, growth, graph = _run(tmp_path, reply, question)
    conductor = _AnsweringConductor(
        _reply(kind="ANSWER", record_ids=("active-record",)),
        active_ids=("active-record",),
    )
    assert check_resolved(handoff, conductor) is True
    assert check_resolved(handoff, conductor) is True
    assert [event["resolved"] for event in growth.branch_outcomes] == [False, True]
    assert len(graph.nodes) == 1
    assert graph.get(handoff.gap_id).status == "RESOLVED"
