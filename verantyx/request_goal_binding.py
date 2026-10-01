"""Narrow same-clause binding from a raw request to one Goal target.

This module consumes FrameEvidence only as local role/span provenance. It does
not certify a proposition as true, authorize an action, or license source
facts. A successful result requires the action Frame and one explicit patient
argument to be uniquely aligned to the same unquoted, positive clause.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Literal

from .frames import Frame
from .frame_evidence import FrameEvidenceDocument, FrameSnapshot, SourceSpan
from .content_ir import Span


@dataclass(frozen=True)
class BindingDecision:
    """Derived local binding record; HOLD includes no inferred target proof."""

    status: Literal["BOUND", "HOLD"]
    reason: str
    clause_id: str = ""
    frame_id: str = ""
    predicate_span: SourceSpan | None = None
    argument_span: SourceSpan | None = None
    particle_span: SourceSpan | None = None
    target: str = ""


@dataclass(frozen=True)
class QuantityAttachment:
    """Local source attachment for a separately parsed quantity phrase."""

    status: Literal["BOUND", "HOLD"]
    reason: str
    clause_id: str = ""
    frame_id: str = ""
    modifier_span: SourceSpan | None = None
    particle_span: SourceSpan | None = None
    value: str = ""


def _snapshot(frame: Frame) -> FrameSnapshot:
    return FrameSnapshot(
        predicate=frame.predicate,
        agent=frame.agent,
        patient=frame.patient,
        recipient=frame.recipient,
        negated=frame.negated,
        past=frame.past,
        ambiguous=frame.ambiguous,
        inferred=frame.inferred,
    )


def _valid_span(raw_request: str, span: SourceSpan | None) -> bool:
    return (
        type(span) is SourceSpan
        and type(span.start) is int
        and type(span.end) is int
        and 0 <= span.start < span.end <= len(raw_request)
        and type(span.text) is str
        and raw_request[span.start:span.end] == span.text
    )


def _valid_goal_span(raw_request: str, source_sha: str, span: Span) -> bool:
    return (
        type(span) is Span
        and type(span.source) is str
        and span.source == "request"
        and type(span.sha256) is str
        and span.sha256 == source_sha
        and type(span.start) is int
        and type(span.end) is int
        and 0 <= span.start < span.end <= len(raw_request)
    )


def bind_action_patient(
    raw_request: str,
    evidence: FrameEvidenceDocument,
    action_frame: Frame,
    action_span: Span,
    target: str,
) -> BindingDecision:
    """Bind an action to one explicit local patient permitted by the sidecar.

    The caller must pass the exact raw request and the action Frame/span it
    derived from that text. Every sidecar gate is checked here; the consumer
    separately re-runs this function from trusted raw input and compares the
    complete sidecar and decision.
    """
    def hold(reason: str) -> BindingDecision:
        return BindingDecision("HOLD", reason)

    if type(raw_request) is not str or type(evidence) is not FrameEvidenceDocument:
        return hold("typed raw request or FrameEvidenceDocument is missing")
    try:
        source_sha = hashlib.sha256(raw_request.encode("utf-8")).hexdigest()
    except UnicodeEncodeError:
        return hold("raw request is not valid UTF-8 for sidecar binding")
    if (evidence.source_id != "request" or evidence.source_text != raw_request
            or evidence.source_sha256 != source_sha):
        return hold("FrameEvidence source envelope does not match exact raw request")
    if (evidence.alignment_status != "ALIGNED_BY_READER_ORDER"
            or evidence.reader_order_alignment_status != "ALIGNED_BY_READER_ORDER"
            or evidence.source_coverage_status not in ("EXACT", "WHITESPACE_ONLY")
            or not evidence.token_positions_complete
            or evidence.unmatched_frames):
        return hold("FrameEvidence alignment or complete source coverage is unresolved")
    if any(gap.classification not in ("WHITESPACE",) for gap in evidence.source_gaps):
        return hold("FrameEvidence contains a non-whitespace or unknown source gap")
    if (type(action_frame) is not Frame or type(action_span) is not Span
            or type(target) is not str or not target):
        return hold("action Frame, source span, or target is not typed")
    if action_frame.negated:
        return hold("action Frame polarity is negative")
    if action_frame.past:
        return hold("past-tense action is outside the request form subset")
    if action_frame.ambiguous or action_frame.inferred:
        return hold("action Frame is ambiguous or inferred")
    if not _valid_goal_span(raw_request, source_sha, action_span):
        return hold("action span is not bound to exact raw request")

    matching_clauses = [clause for clause in evidence.clauses
                        if clause.predicate_span is not None
                        and clause.predicate_span.start == action_span.start
                        and clause.predicate_span.end == action_span.end]
    if len(matching_clauses) != 1:
        return hold("action predicate span does not identify exactly one sidecar clause")
    clause = matching_clauses[0]
    predicate_span = clause.predicate_span
    assert predicate_span is not None
    if (not _valid_span(raw_request, predicate_span)
            or predicate_span.text != raw_request[action_span.start:action_span.end]
            or clause.predicate != action_frame.predicate
            or clause.frame != _snapshot(action_frame)):
        return hold("sidecar predicate span or complete Frame snapshot differs from action Frame")
    if clause.alignment_status != "ALIGNED_BY_READER_ORDER":
        return hold("action clause is not aligned to its Frame")
    if clause.quote_status != "UNQUOTED":
        return hold("action clause is quoted or quote scope is unknown")
    if (clause.scope_status != "KNOWN" or clause.polarity != "POSITIVE"
            or clause.local_scope_status != "KNOWN"
            or clause.local_polarity != "POSITIVE"):
        return hold("action proposition scope or polarity is unresolved")
    if action_frame.patient != target:
        return hold("action Frame patient does not equal the proposed target")

    all_patient_arguments = [argument for argument in clause.arguments
                             if argument.role == "patient"]
    target_arguments = [argument for argument in all_patient_arguments
                        if argument.value == target]
    if len(all_patient_arguments) != 1 or len(target_arguments) != 1:
        return hold("same-clause patient evidence is absent or non-unique")
    argument = target_arguments[0]
    span, particle_span = argument.span, argument.particle_span
    if not _valid_span(raw_request, span):
        return hold("patient argument has no exact raw source span")
    assert span is not None
    if span.text != target:
        return hold("patient span text does not equal the proposed target")
    if (argument.owner_frame_id != clause.frame_id
            or argument.source_frame_id != clause.frame_id
            or argument.origin != "EXPLICIT_CASE"
            or argument.binding_status != "UNIQUE"
            or argument.source_owner_status != "LOCAL_TOKEN_WINDOW"
            or argument.argument_quote_status != "UNQUOTED"
            or argument.case_quote_status != "UNQUOTED"
            or argument.binding_quote_status != "UNQUOTED"
            or type(argument.case_particle) is not str
            or argument.permitted is not True):
        return hold("patient evidence fails explicit same-owner local-case gates")
    if not _valid_span(raw_request, particle_span):
        return hold("patient case particle has no exact raw source span")
    assert particle_span is not None
    if (particle_span.text != argument.case_particle or particle_span.start < span.end
            or raw_request[span.end:particle_span.start].strip()):
        return hold("patient case particle is not locally adjacent to its span")

    return BindingDecision(
        status="BOUND",
        reason="unique explicit same-owner patient span and case particle",
        clause_id=clause.clause_id,
        frame_id=clause.frame_id,
        predicate_span=predicate_span,
        argument_span=span,
        particle_span=particle_span,
        target=target,
    )


def bind_action_quantity(
    raw_request: str,
    evidence: FrameEvidenceDocument,
    action_frame: Frame,
    action_span: Span,
    modifier_span: Span,
    value: str,
) -> QuantityAttachment:
    """Attach a raw-parsed quantity span to the same action clause.

    The quantity value is still parsed by the Goal producer. FrameEvidence's
    UNKNOWN role record contributes only same-clause, explicit local span and
    particle provenance; this routine does not infer a role or quantity.
    """
    def hold(reason: str) -> QuantityAttachment:
        return QuantityAttachment("HOLD", reason)

    if (type(raw_request) is not str or type(evidence) is not FrameEvidenceDocument
            or type(action_frame) is not Frame or type(action_span) is not Span
            or type(modifier_span) is not Span or type(value) is not str):
        return hold("typed raw request, action, or modifier input is missing")
    try:
        source_sha = hashlib.sha256(raw_request.encode("utf-8")).hexdigest()
    except UnicodeEncodeError:
        return hold("raw request is not valid UTF-8 for sidecar binding")
    if (evidence.source_id != "request" or evidence.source_text != raw_request
            or evidence.source_sha256 != source_sha
            or evidence.alignment_status != "ALIGNED_BY_READER_ORDER"
            or evidence.reader_order_alignment_status != "ALIGNED_BY_READER_ORDER"
            or evidence.source_coverage_status not in ("EXACT", "WHITESPACE_ONLY")
            or not evidence.token_positions_complete or evidence.unmatched_frames
            or any(gap.classification != "WHITESPACE" for gap in evidence.source_gaps)):
        return hold("FrameEvidence envelope or source coverage is unresolved")
    if (action_frame.negated or action_frame.past
            or action_frame.ambiguous or action_frame.inferred
            or action_frame.patient == ""
            or action_span.source != "request"
            or modifier_span.source != "request"
            or action_span.sha256 != source_sha
            or modifier_span.sha256 != source_sha
            or not _valid_goal_span(raw_request, source_sha, action_span)
            or not _valid_goal_span(raw_request, source_sha, modifier_span)
            or raw_request[modifier_span.start:modifier_span.end] != value):
        return hold("action or quantity modifier is not a positive exact raw span")
    clauses = [clause for clause in evidence.clauses
               if clause.predicate_span is not None
               and clause.predicate_span.start == action_span.start
               and clause.predicate_span.end == action_span.end]
    if len(clauses) != 1:
        return hold("action predicate span does not identify exactly one sidecar clause")
    clause = clauses[0]
    if (clause.predicate != action_frame.predicate
            or clause.frame != _snapshot(action_frame)
            or clause.alignment_status != "ALIGNED_BY_READER_ORDER"
            or clause.quote_status != "UNQUOTED"
            or clause.scope_status != "KNOWN"
            or clause.polarity != "POSITIVE"
            or clause.local_scope_status != "KNOWN"
            or clause.local_polarity != "POSITIVE"):
        return hold("quantity modifier action-clause scope is unresolved")
    matches = [argument for argument in clause.arguments
               if argument.role == "UNKNOWN" and argument.value == value
               and argument.span is not None
               and argument.span.start == modifier_span.start
               and argument.span.end == modifier_span.end]
    if len(matches) != 1:
        return hold("quantity phrase has no unique same-clause local span")
    argument = matches[0]
    if (argument.owner_frame_id != clause.frame_id
            or argument.source_frame_id != clause.frame_id
            or argument.origin != "EXPLICIT_CASE"
            or argument.binding_status != "UNKNOWN"
            or argument.source_owner_status != "LOCAL_TOKEN_WINDOW"
            or argument.permitted is not False
            or argument.case_particle != "で"
            or argument.argument_quote_status != "UNQUOTED"
            or argument.case_quote_status != "UNQUOTED"
            or argument.binding_quote_status != "UNQUOTED"
            or not _valid_span(raw_request, argument.span)
            or not _valid_span(raw_request, argument.particle_span)):
        return hold("quantity phrase is not an unquoted explicit same-owner modifier")
    assert argument.span is not None and argument.particle_span is not None
    if (argument.span.text != value or argument.particle_span.text != "で"
            or argument.particle_span.start < argument.span.end
            or raw_request[argument.span.end:argument.particle_span.start].strip()):
        return hold("quantity modifier particle is not locally adjacent")
    return QuantityAttachment(
        status="BOUND", reason="local explicit quantity phrase attached to action",
        clause_id=clause.clause_id, frame_id=clause.frame_id,
        modifier_span=argument.span, particle_span=argument.particle_span,
        value=value,
    )


__all__ = ["BindingDecision", "QuantityAttachment", "bind_action_patient",
           "bind_action_quantity"]
