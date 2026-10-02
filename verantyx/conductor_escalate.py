"""Typed handoffs for conductor refusals.

An ESCALATE reply is only a reason.  This module pairs it with the exact
question that produced it, names the missing frame material, and records an
append-only refusal outcome beside the frame.  A handoff closes only after
the same question is run through the conductor again and the answer cites a
record.
"""
from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, Mapping, Optional

from .conductor import AgentQuestion, Reply
from .gap_graph import GapGraph, GapNode, gap_graph_path
from .growth_signals import GrowthSignals, growth_signals_path, normalize_query


MissingKind = Literal["record_kind", "vocabulary", "authority"]
Resolver = Literal["human", "document"]


@dataclass(frozen=True)
class MissingMaterial:
    """A typed description of the material needed to retry an escalation."""

    kind: MissingKind
    value: str
    record_kind: Optional[str] = None
    vocabulary: Optional[str] = None
    document_shelf: Optional[str] = None
    allowed_sources: tuple[str, ...] = ()
    instruction: str = ""
    coverage_hole: Optional[bool] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "value": self.value,
            "record_kind": self.record_kind,
            "vocabulary": self.vocabulary,
            "document_shelf": self.document_shelf,
            "allowed_sources": list(self.allowed_sources),
            "instruction": self.instruction,
            "coverage_hole": self.coverage_hole,
        }


@dataclass(frozen=True)
class Handoff:
    """The refusal, repair target, and unchanged question for a later check."""

    question: AgentQuestion
    reply: Reply
    missing: MissingMaterial
    resolver: Resolver
    cause: str
    scope: str
    subject: str
    branch: str
    document_resolvable: bool
    protected_action: Optional[str]
    gap_id: Optional[str]
    growth_path: str
    graph_path: str
    _growth: GrowthSignals = field(repr=False, compare=False)
    _graph: GapGraph = field(repr=False, compare=False)

    @property
    def reask(self) -> AgentQuestion:
        """The exact original question, including options and claimed state."""
        return self.question

    @property
    def resolvable_by_document(self) -> bool:
        return self.document_resolvable

    def as_dict(self) -> dict[str, Any]:
        return {
            "question": {
                "id": self.question.id,
                "text": self.question.text,
                "options": list(self.question.options) if self.question.options is not None else None,
                "claimed_state": self.question.claimed_state,
            },
            "reask": {
                "id": self.question.id,
                "text": self.question.text,
                "options": list(self.question.options) if self.question.options is not None else None,
                "claimed_state": self.question.claimed_state,
            },
            "reply": self.reply.as_dict(),
            "missing": self.missing.as_dict(),
            "resolver": self.resolver,
            "cause": self.cause,
            "scope": self.scope,
            "subject": self.subject,
            "branch": self.branch,
            "document_resolvable": self.document_resolvable,
            "protected_action": self.protected_action,
            "gap_id": self.gap_id,
        }


_RECORD_KIND = re.compile(r"\b([A-Z][A-Z0-9_]{1,})\b")
_PROTECTED_CAUSE = re.compile(r"outside frame authority|outside-authority action", re.I)


def _protected_action(reply: Reply, frame: Any, question: AgentQuestion) -> Optional[str]:
    if _PROTECTED_CAUSE.search(reply.reason or ""):
        return reply.reason.partition(":")[-1].strip() or "protected action"
    checker = getattr(frame, "_protected_action", None)
    if callable(checker):
        return checker(question.text, *(question.options or []))
    return None


def _missing_material(
    reply: Reply,
    question: AgentQuestion,
    *,
    protected: Optional[str],
    domains: Optional[Mapping[str, Any]],
    aliases: Optional[Mapping[str, str]],
    subject: str,
    shelf_lookup: Optional[Callable[[str], Any]],
) -> MissingMaterial:
    missing = str(reply.missing or "typed frame record").strip()
    if protected or "human" in missing.casefold() or "authority" in missing.casefold():
        return MissingMaterial(
            kind="authority", value=protected or missing,
            instruction="A human must supply or approve the authoritative record; a document cannot authorize this action.",
        )
    if ("vocabulary" in missing.casefold() or "alias" in missing.casefold()
            or "option mapping" in missing.casefold() or "closed option" in missing.casefold()):
        vocab = missing if missing.casefold() != "vocabulary" else "the closed frame vocabulary for this question"
        return MissingMaterial(
            kind="vocabulary", value=missing, vocabulary=vocab,
            instruction="A human must add or confirm the exact vocabulary term in the frame.",
        )

    found = _RECORD_KIND.search(missing)
    record_kind = found.group(1) if found else None
    shelf = None
    allowed_sources: tuple[str, ...] = ()
    coverage_hole = None
    instruction = "Provide a source document that states the missing material, then add its typed frame record."
    if shelf_lookup is not None:
        result = shelf_lookup(subject)
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except (TypeError, json.JSONDecodeError):
                result = {"document": result}
        if isinstance(result, Mapping):
            shelf = result.get("document")
            coverage_hole = result.get("coverage_hole")
            closest = result.get("closest") or []
            allowed_sources = tuple(str(row["domain"]) for row in closest
                                    if isinstance(row, Mapping) and row.get("domain"))
            repair = result.get("repair")
            if isinstance(repair, Mapping) and repair.get("register"):
                instruction = str(repair["register"])
    elif domains is not None:
        from .coverage import closing_domains, document_needed

        # The same helper powers MCP's what_would_close door.  NOT_ATTESTED
        # is the closest older-line repair: it asks for a sourced statement
        # connecting a subject to the requested condition without asserting it.
        result = document_needed(dict(domains), subject, "NOT_ATTESTED", aliases=dict(aliases or {}))
        where = closing_domains(dict(domains), subject, aliases=dict(aliases or {}))
        shelf = result.get("document")
        coverage_hole = result.get("coverage_hole")
        allowed_sources = tuple(str(row["domain"]) for row in where.get("closest", [])
                                if isinstance(row, Mapping) and row.get("domain"))
        repair = result.get("repair")
        if isinstance(repair, Mapping) and repair.get("register"):
            instruction = str(repair["register"])
    else:
        from .remedy import remedy

        repair = remedy({"verdict": "NOT_ATTESTED", "subject": subject})
        instruction = str(repair.get("register") or instruction)

    return MissingMaterial(
        kind="record_kind", value=missing, record_kind=record_kind,
        document_shelf=str(shelf) if shelf else None,
        allowed_sources=allowed_sources,
        instruction=instruction, coverage_hole=coverage_hole,
    )


def _paths(frame: Any) -> tuple[Path, Path]:
    memory = getattr(frame, "memory", None)
    store_path = getattr(memory, "path", None)
    if store_path is None:
        raise ValueError("frame must expose memory.path for refusal sidecars")
    store_path = Path(store_path)
    return growth_signals_path(store_path), gap_graph_path(store_path)


def _outcome_key(event: Mapping[str, Any]) -> tuple[str, str, str, bool]:
    return (
        str(event.get("scope", "agent_refusal")),
        normalize_query(str(event.get("subject", event.get("query", "")))),
        str(event.get("cause", "")),
        bool(event.get("resolved", False)),
    )


def _record_outcome(
    growth: GrowthSignals,
    *,
    scope: str,
    subject: str,
    cause: str,
    verdict: str,
    branch: str,
    resolved: bool,
) -> None:
    ledger_subject = normalize_query(subject)
    key = (scope, ledger_subject, cause, resolved)
    duplicate = any(
        _outcome_key(event) == key or (
            not event.get("cause")
            and _outcome_key(event)[0] == scope
            and _outcome_key(event)[1] == ledger_subject
            and bool(event.get("resolved", False)) == resolved
            and str(event.get("verdict", "")) == verdict
            and str(event.get("branch", "")) == branch
        )
        for event in growth.branch_outcomes
    )
    if duplicate:
        return
    growth.record_branch_outcome(subject, verdict, branch, resolved)
    event = growth.branch_outcomes[-1]
    event.update({"scope": scope, "subject": subject, "cause": cause})


def _find_or_create_gap(
    graph: GapGraph,
    *,
    subject: str,
    cause: str,
    branch: str,
    allowed_sources: Optional[list[str]],
) -> GapNode:
    same_key = [node for node in graph.nodes.values()
                if node.scope == "agent_refusal" and node.subject == subject
                and node.failure_type == cause]
    if same_key:
        return same_key[0]
    node = graph.create(
        gap_type="unresolved_refusal", subject=subject,
        scope="agent_refusal", severity="QUALITY",
        failure_type=cause, acquisition_methods=[branch],
        allowed_sources=allowed_sources,
    )
    if node.failure_type == cause:
        return node

    # GapGraph's general create API deduplicates on scope+subject.  Refusal
    # causes are an additional identity component, so preserve parallel
    # causes as separate nodes while keeping ordinary gap behavior intact.
    node = GapNode(
        gap_id=f"gap_{uuid.uuid4().hex[:8]}", gap_type="unresolved_refusal",
        subject=subject, scope="agent_refusal", severity="QUALITY",
        failure_type=cause, acquisition_methods=[branch],
        allowed_sources=list(allowed_sources or []),
    )
    graph.nodes[node.gap_id] = node
    return node


def enrich(
    reply: Reply,
    frame: Any,
    question: Optional[AgentQuestion] = None,
    *,
    domains: Optional[Mapping[str, Any]] = None,
    aliases: Optional[Mapping[str, str]] = None,
    subject: Optional[str] = None,
    shelf_lookup: Optional[Callable[[str], Any]] = None,
    growth: Optional[GrowthSignals] = None,
    graph: Optional[GapGraph] = None,
    growth_signals: Optional[GrowthSignals] = None,
    gap_graph: Optional[GapGraph] = None,
) -> Handoff:
    """Turn an ESCALATE into a typed handoff and record it once.

    ``question`` is the original ``AgentQuestion`` passed to the conductor;
    retaining it makes the resolution check an exact re-ask.  Sidecars default
    to the directory beside ``frame.memory.path`` and can be injected in tests
    or embedded callers.
    """
    if not isinstance(reply, Reply) or reply.kind != "ESCALATE":
        raise ValueError("enrich requires a conductor ESCALATE reply")
    if not isinstance(question, AgentQuestion):
        raise ValueError("enrich requires the original AgentQuestion for an exact re-ask")
    if growth is not None and growth_signals is not None and growth is not growth_signals:
        raise ValueError("pass only one of growth or growth_signals")
    if graph is not None and gap_graph is not None and graph is not gap_graph:
        raise ValueError("pass only one of graph or gap_graph")

    growth_path, graph_path = _paths(frame)
    growth = growth or growth_signals or GrowthSignals.load(growth_path)
    graph = graph or gap_graph or GapGraph.load(graph_path)
    query_subject = subject if subject is not None else question.text
    protected = _protected_action(reply, frame, question)
    resolver: Resolver = "human" if protected else "document"
    if not protected and reply.missing and "human" in reply.missing.casefold():
        resolver = "human"
    material = _missing_material(
        reply, question, protected=protected, domains=domains, aliases=aliases,
        subject=query_subject, shelf_lookup=shelf_lookup,
    )
    if material.kind in {"authority", "vocabulary"}:
        resolver = "human"
    cause = "|".join((reply.question_kind or "OTHER", reply.missing or "", reply.reason or ""))
    scope = "agent_refusal"
    branch = resolver

    allowed_sources = list(material.allowed_sources) or None
    node = _find_or_create_gap(
        graph, subject=query_subject, cause=cause, branch=branch,
        allowed_sources=allowed_sources,
    )
    _record_outcome(
        growth, scope=scope, subject=query_subject, cause=cause,
        verdict=reply.missing or "ESCALATE", branch=branch, resolved=False,
    )
    growth_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    growth.save(growth_path)
    graph.save(graph_path)

    return Handoff(
        question=question, reply=reply, missing=material, resolver=resolver,
        cause=cause, scope=scope, subject=query_subject, branch=branch,
        document_resolvable=(resolver == "document"),
        protected_action=protected, gap_id=node.gap_id,
        growth_path=str(growth_path), graph_path=str(graph_path),
        _growth=growth, _graph=graph,
    )


def _validated_record_ids(reply: Any, conductor: Any) -> tuple[str, ...]:
    if getattr(reply, "kind", None) != "ANSWER":
        return ()
    record_ids = tuple(str(record_id) for record_id in (getattr(reply, "record_ids", ()) or ()) if record_id)
    if not record_ids:
        return ()
    active_record = getattr(conductor, "_active_record", None)
    if callable(active_record):
        validated = []
        for record_id in record_ids:
            try:
                record = active_record(record_id)
            except Exception:
                continue
            if isinstance(record, Mapping) and str(record.get("id", "")) == record_id:
                validated.append(record_id)
        return tuple(validated)
    memory = getattr(conductor, "memory", None)
    active = getattr(memory, "active", None)
    if callable(active):
        try:
            active_ids = {
                str(record.get("id")) for record in active()
                if isinstance(record, Mapping) and record.get("id")
            }
        except Exception:
            return ()
        return tuple(record_id for record_id in record_ids if record_id in active_ids)
    return ()


def check_resolved(handoff: Handoff, conductor: Any) -> bool:
    """Re-ask the unchanged question and close only on a cited ANSWER.

    No caller-supplied success flag is accepted.  Protected-action handoffs
    cannot be closed by documents, even if one is later supplied.
    """
    if not isinstance(handoff, Handoff):
        raise TypeError("check_resolved requires a Handoff")
    answer = conductor.answer(handoff.question)
    if handoff.protected_action:
        return False
    verified_record_ids = _validated_record_ids(answer, conductor)
    if not verified_record_ids:
        return False

    growth_path, graph_path = Path(handoff.growth_path), Path(handoff.graph_path)
    growth = handoff._growth if handoff._growth is not None else GrowthSignals.load(growth_path)
    graph = handoff._graph if handoff._graph is not None else GapGraph.load(graph_path)
    _record_outcome(
        growth, scope=handoff.scope, subject=handoff.subject, cause=handoff.cause,
        verdict=handoff.reply.missing or "ESCALATE", branch=handoff.branch,
        resolved=True,
    )
    if handoff.gap_id:
        node = graph.get(handoff.gap_id)
        if node is not None and node.status != "RESOLVED":
            graph.set_status(
                handoff.gap_id, "RESOLVED",
                resolution="re-asked the same question; conductor returned ANSWER from active record(s)",
                verified_by=list(verified_record_ids),
            )
    growth_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    growth.save(growth_path)
    graph.save(graph_path)
    return True


__all__ = ["Handoff", "MissingMaterial", "enrich", "check_resolved"]
