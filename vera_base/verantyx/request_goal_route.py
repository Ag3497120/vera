"""Normal-route adapter for one source-bound request subset.

This connects the existing raw Goal producer to the existing C realizer and
Goal consumer. It is intentionally partial: source resolutions are reported
as navigation only, and a limited projection is never upgraded to Goal
completion or an independent factual witness.
"""
from __future__ import annotations

import hashlib
from collections.abc import Mapping
from typing import Any

from .compositional_goal import GoalDraft, evaluate_candidate, produce_goal
from .content_ir import Atom, ContentError
from .content_realizer import atom_text
from .meaning_bridge import SourceEventEnvelope

MAX_ROUTE_REQUEST_CHARS = 1200
MAX_ROUTE_SOURCE_CHARS = 4096


def is_request_utterance(raw_request: str) -> bool:
    """Select explicit source-bound Goal requests without diverting fact QA.

    Query supplies the speech act; the existing Frame reader supplies the
    action predicate; the Goal producer's finite source/action vocabulary is
    reused as the routing boundary. Quoted spans are masked before either the
    source marker or action can select this route.
    """
    if type(raw_request) is not str:
        return False
    try:
        raw_request.encode("utf-8")
    except UnicodeEncodeError:
        # Route invalid text to the typed producer boundary so it is held,
        # rather than sending malformed Unicode through an older fallback.
        return True
    from .question import read

    query = read(raw_request)
    if query.speech_act.value.act not in ("request", "command"):
        return False

    from . import content_reader
    from .compositional_goal import _CONTENT_ACTIONS, _SIDE_EFFECT_ACTIONS, _SOURCE_MARKERS
    from .frames import read_all

    masked = content_reader.outside_quotes(raw_request)
    if not any(marker in masked for marker in _SOURCE_MARKERS):
        return False
    actions = frozenset(_CONTENT_ACTIONS) | frozenset(_SIDE_EFFECT_ACTIONS)
    if len(raw_request) > MAX_ROUTE_REQUEST_CHARS:
        # Avoid invoking the Frame reader on oversized material, but keep a
        # clearly source-bound unsupported request on the safe HOLD path.
        return any(action in masked for action in actions)
    try:
        frames = read_all(masked)
    except (ImportError, ModuleNotFoundError):
        # Missing parsing capability must not send an explicit source action
        # through an older permissive fallback.
        return any(action in masked for action in actions)
    return any(frame.predicate in actions for frame in frames)


def _span_record(span: Any) -> dict | None:
    if span is None:
        return None
    return {
        "source": getattr(span, "source", None),
        "start": getattr(span, "start", None),
        "end": getattr(span, "end", None),
    }


def _goal_record(draft: GoalDraft) -> dict:
    return {
        "status": draft.status,
        "action": draft.action,
        "target": draft.target,
        "target_kind": draft.target_kind,
        "target_span": _span_record(draft.target_span),
        "target_predicate": draft.target_predicate,
        "source_id": draft.source_id,
        "source_event_sha256": (
            draft.source_event.prototype_sha256
            if type(draft.source_event) is SourceEventEnvelope else ""
        ),
        "required_roles": list(draft.required_roles),
        "quantities": [list(item) for item in draft.quantities],
        "quantity_bindings": [
            {"status": item.status, "reason": item.reason, "value": item.value,
             "frame_id": item.frame_id,
             "modifier_span": _span_record(item.modifier_span)}
            for item in draft.quantity_bindings
        ],
        "target_binding": (
            {"status": draft.target_binding.status,
             "reason": draft.target_binding.reason,
             "frame_id": draft.target_binding.frame_id,
             "argument_span": _span_record(draft.target_binding.argument_span)}
            if draft.target_binding is not None else None
        ),
        "prohibitions": list(draft.prohibitions),
        "unverified_prohibitions": list(draft.unverified_prohibitions),
        "unread_spans": [_span_record(item) for item in draft.ledger.unread],
        "quote_spans": [_span_record(item) for item in draft.quote_data],
        "ambiguity_spans": [_span_record(item) for item in draft.ambiguity_spans],
        "hold_reasons": list(draft.hold_reasons),
    }


def _held(reason: str, *, draft: GoalDraft | None = None,
          trace: list[dict] | None = None, evaluation: Any = None) -> dict:
    result = {
        "kind": "unknown",
        "verdict": "UNKNOWN_REQUEST_GOAL_HOLD",
        "status": "HOLD",
        "text": "",
        "candidate_text": None,
        "reason": reason,
        "verified": False,
        "candidate_projection_verified": False,
        "full_goal_verified": False,
        "full_semantic_equivalent": None,
        "goal_satisfied": None,
        "success_count_eligible": False,
        "adoption_eligible": False,
        "world_assigned": False,
        "independent_source_count": 0,
        "trace": list(trace or []),
    }
    if draft is not None:
        result["goal"] = _goal_record(draft)
    if evaluation is not None:
        result["verification"] = {
            "status": evaluation.status,
            "integrity_status": evaluation.integrity_status,
            "limited_projection_equivalent": evaluation.limited_projection_equivalent,
            "full_semantic_equivalent": evaluation.full_semantic_equivalent,
            "goal_satisfied": evaluation.goal_satisfied,
            "represented_requirements_satisfied": evaluation.represented_requirements_satisfied,
            "success_count_eligible": evaluation.success_count_eligible,
            "checks": [{"name": name, "passed": passed}
                       for name, passed in evaluation.checks],
            "unmet": list(evaluation.unmet),
            "unverified_requirements": list(evaluation.unverified_requirements),
        }
    return result


def _representation_trace(draft: GoalDraft, *, candidate_read: bool) -> list[dict]:
    """Expose the A/C boundary without treating shared-source views as votes."""
    trace = [
        {"stage": "request", "representation": "question.Query + FrameEvidence + content_ir.Ledger",
         "authority": "raw user request", "independent_evidence": False},
        {"stage": "source", "representation": "semantic_ir.View → SourceEventEnvelope → content_ir.Atom",
         "source_id": draft.source_id,
         "source_event_sha256": (draft.source_event.prototype_sha256
                                 if type(draft.source_event) is SourceEventEnvelope else ""),
         "authority": "source-bound expression only", "independent_evidence": False},
    ]
    if candidate_read:
        trace.append({"stage": "candidate", "representation": "semantic_ir.View",
                      "authority": "candidate re-read against same source event",
                      "independent_evidence": False})
    trace.append({"stage": "multiresolution_domain_exploration",
                  "status": "NOT_CONNECTED_TO_GOAL_REALIZATION",
                  "independent_witness_count": 0,
                  "not_used_for_candidate_generation": True,
                  "note": "Round5 may attach navigation metadata separately; it is not Goal evidence"})
    return trace


def _candidate_for(draft: GoalDraft) -> tuple[str | None, str]:
    """Build only the already licensed one-event restatement surface."""
    if draft.status != "READY":
        return None, "producer did not establish READY"
    if draft.action != "restate" or draft.target_kind != "source_event":
        return None, "only source_event restatement is implemented"
    exact_counts = {number for kind, number in draft.quantities
                    if kind == "exact_sentences"}
    maximum_counts = {number for kind, number in draft.quantities
                      if kind == "max_sentences"}
    if (any(kind not in ("exact_sentences", "max_sentences")
            for kind, _number in draft.quantities)
            or (exact_counts and exact_counts != {1})
            or any(number < 1 for number in maximum_counts)):
        return None, "the licensed one-event surface does not satisfy the requested sentence count"
    if (draft.reason_required or draft.prohibitions or draft.unverified_prohibitions
            or draft.quote_data or draft.ambiguity_spans or draft.ledger.unread):
        return None, "required meaning remains unverified or unread"
    if (draft.target_binding is None or draft.target_binding.status != "BOUND"
            or len(draft.quantity_bindings) != len(draft.quantities)
            or any(item.status != "BOUND" for item in draft.quantity_bindings)):
        return None, "action target or requested quantity lacks a bound same-clause span"
    envelope = draft.source_event
    if type(envelope) is not SourceEventEnvelope or type(envelope.atom) is not Atom:
        return None, "source event did not provide the exact licensed expression Atom"
    agent = envelope.atom.agent
    if type(agent) is not str or not agent:
        return None, "agent surface is absent from the licensed event"
    try:
        generated = atom_text(envelope.atom, narrator="")
    except ContentError as error:
        return None, "existing realizer held the source event: " + error.verdict
    subject = agent + "が"
    if not generated.startswith(subject):
        return None, "licensed agent case cannot be varied at this surface"
    # The candidate is built from the producer's event slots; this does not
    # copy the source sentence or decide acceptance by matching our output.
    return agent + "は" + generated[len(subject):] + "。", ""


def route_request_goal(raw_request: str, documents: Mapping[str, str]) -> dict:
    """Interpret, realize, and recheck one raw source-bound request.

    A clean route result is still PARTIAL. The consumer's full Goal result is
    `None`, because topic/focus and paraphrase quality are outside this slice.
    """
    if type(raw_request) is not str:
        return _held("raw request must be an exact str", trace=[
            {"part": "compositional_goal.produce_goal", "status": "HOLD"}
        ])
    if (type(documents) is not dict or len(documents) != 1
            or any(type(key) is not str or not key or type(value) is not str
                   for key, value in documents.items())):
        return _held("this route requires exactly one original source document with str ID/text", trace=[
            {"part": "compositional_goal.produce_goal", "status": "HOLD"}
        ])
    # Snapshot the exact typed input once so producer, consumer, and returned
    # source digest all refer to the same source mapping.
    trusted_documents = dict(documents)
    source_id, source_text = next(iter(trusted_documents.items()))
    if len(raw_request) > MAX_ROUTE_REQUEST_CHARS:
        return _held("raw request exceeds the route's 1200-character bound", trace=[
            {"part": "compositional_goal.produce_goal", "status": "HOLD"}
        ])
    if len(source_id) + len(source_text) > MAX_ROUTE_SOURCE_CHARS:
        return _held("original source exceeds the bridge's 4096-character bound", trace=[
            {"part": "compositional_goal.produce_goal", "status": "HOLD"}
        ])
    try:
        raw_request.encode("utf-8")
        source_id.encode("utf-8")
        source_text.encode("utf-8")
    except UnicodeEncodeError:
        return _held("raw request/source text is not valid UTF-8", trace=[
            {"part": "compositional_goal.produce_goal", "status": "HOLD"}
        ])
    draft = produce_goal(trusted_documents, raw_request)
    raw_trace = [{"part": "compositional_goal.produce_goal", "status": draft.status,
                  "query_reused": True, "ledger_reused": True,
                  "frame_evidence_rederived": draft.frame_evidence is not None}]
    representations = _representation_trace(draft, candidate_read=False)
    if draft.status != "READY":
        result = _held("producer holds: " + "; ".join(draft.hold_reasons or ("Goal is not READY",)),
                       draft=draft, trace=raw_trace)
        result["representations"] = representations
        return result
    candidate, generation_hold = _candidate_for(draft)
    if candidate is None:
        result = _held(generation_hold, draft=draft, trace=raw_trace)
        result["representations"] = representations
        return result

    evaluation = evaluate_candidate(
        draft, candidate, raw_request=raw_request, documents=trusted_documents,
    )
    raw_trace.append({"part": "content_realizer.atom_text", "status": "ran",
                      "surface_change": "agent が→は", "candidate_source": "GoalDraft.source_event.atom"})
    raw_trace.append({"part": "compositional_goal.evaluate_candidate", "status": evaluation.status,
                      "integrity_status": evaluation.integrity_status,
                      "raw_and_source_rederived": True,
                      "limited_projection_equivalent": evaluation.limited_projection_equivalent})
    representations = _representation_trace(draft, candidate_read=True)
    if not (evaluation.status == "PARTIAL"
            and evaluation.integrity_status == "verified"
            and evaluation.limited_projection_equivalent is True
            and evaluation.full_semantic_equivalent is None
            and evaluation.represented_requirements_satisfied is True
            and evaluation.goal_satisfied is None
            and evaluation.success_count_eligible is False):
        result = _held("consumer did not establish the exact limited PARTIAL contract",
                       draft=draft, trace=raw_trace, evaluation=evaluation)
        result["representations"] = representations
        return result

    source_sha256 = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
    return {
        "kind": "partial",
        "verdict": "PARTIAL",
        "status": "PARTIAL",
        "text": candidate,
        "candidate_text": candidate,
        "candidate_kind": "source_bound_expression_candidate",
        "verified": False,
        "candidate_projection_verified": True,
        "full_goal_verified": False,
        "limited_projection_equivalent": True,
        "full_semantic_equivalent": None,
        "represented_requirements_satisfied": True,
        "goal_satisfied": None,
        "success_count_eligible": False,
        "adoption_eligible": False,
        "world_assigned": False,
        "independent_source_count": 0,
        "goal": _goal_record(draft),
        "sources": [{"family": "document", "source": source_id,
                     "sha256": source_sha256}],
        "evidence": [
            {"source": source_id, "source_sha256": source_sha256,
             "source_event_sha256": draft.source_event.prototype_sha256,
             "scope": "single source event expression; no actual-world truth claim"}
        ],
        "verification": {
            "status": evaluation.status,
            "integrity_status": evaluation.integrity_status,
            "limited_projection_equivalent": evaluation.limited_projection_equivalent,
            "full_semantic_equivalent": evaluation.full_semantic_equivalent,
            "goal_satisfied": evaluation.goal_satisfied,
            "represented_requirements_satisfied": evaluation.represented_requirements_satisfied,
            "success_count_eligible": evaluation.success_count_eligible,
            "checks": [{"name": name, "passed": passed}
                       for name, passed in evaluation.checks],
            "unmet": list(evaluation.unmet),
            "unrepresented_semantics": list(evaluation.unrepresented_semantics),
        },
        "representations": representations,
        "trace": raw_trace,
    }
