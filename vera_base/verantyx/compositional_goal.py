"""Small compositional, source-bound raw Goal diagnostic.

This is an opt-in producer/consumer seam, not a router. It reuses Query,
Frame, Ledger, and the existing single-event source bridge. A Goal is READY
only when every unquoted request token in this finite subset is accounted
for. Unknown and ambiguous spans remain attached to the original request.

Supported actions are paraphrase and explanation. Explanation additionally
requires grounds that a single assertion event cannot supply, so it remains
held. The consumer reports the bridge's limited projection result separately
from represented Goal checks; full semantic equivalence is always unknown.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
import hashlib
import json
from typing import Any, Literal

from . import content_reader
from .content_ir import ContentError, Ledger, Obligation, Source, Span, digest
from .frames import Frame, read_all
from .frame_evidence import FrameEvidenceDocument, read_frame_evidence
from .meaning_bridge import (
    BridgeError,
    SourceEventEnvelope,
    bridge_source_event,
    restore_source_event,
    verify_event_realization,
)
from .question import Query, read as read_question
from .request_goal_binding import (
    BindingDecision,
    QuantityAttachment,
    bind_action_patient,
    bind_action_quantity,
)
from .semantic_reader import document_view
from .typed_edges import _base, _tagger


VERSION = "compositional-raw-goal-v1"

# This is a word-to-operation map, not a whole-request template. Unmapped
# predicates are preserved as unread and block readiness.
_CONTENT_ACTIONS = {
    "言い換える": "restate",
    "説明する": "explain",
    "解説する": "explain",
    "要約する": "unsupported_summary",
    "まとめる": "unsupported_summary",
}
_SIDE_EFFECT_ACTIONS = {"送信する": "send", "送る": "send"}
_SOURCE_MARKERS = ("資料", "原文", "出典")
_TARGET_HEADS = {"出来事": "source_event", "一件": "source_event", "内容": "source_content"}
_ROLE_ORDER = ("agent", "patient", "recipient")
_ROLE_WORDS = {
    ("誰", "が"): "agent",
    ("だれ", "が"): "agent",
    ("何", "を"): "patient",
    ("なに", "を"): "patient",
    ("誰", "に"): "recipient",
    ("だれ", "に"): "recipient",
}
_PUNCTUATION = {"、", "。", "！", "!", "？", "?", "；", ";", "：", ":", "（", "）", "(", ")"}
_POLITE = {"ください", "下さい"}
_NEGATION_MARKERS = {"ない", "なかっ", "ず", "ぬ", "ません", "なく"}
_JP_NUMBERS = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
               "七": 7, "八": 8, "九": 9, "十": 10}
_QUOTE_PAIRS = {"「": "」", "『": "』"}


@dataclass(frozen=True)
class _LocatedToken:
    token: Any
    start: int
    end: int
    aligned: bool = True


@dataclass(frozen=True)
class _FrameRecord:
    frame: Frame
    span: Span | None
    token_indices: tuple[int, ...]
    negation_span: Span | None = None


@dataclass(frozen=True)
class GoalDraft:
    """The reusable existing Query/Ledger plus diagnostic binding metadata."""

    query: Query
    ledger: Ledger
    status: str
    action: str = ""
    target: str = ""
    target_kind: str = ""
    target_span: Span | None = None
    target_predicate: str = ""
    source_event: SourceEventEnvelope | None = None
    source_id: str = ""
    source_policy: str = ""
    required_roles: tuple[str, ...] = ()
    quantities: tuple[tuple[str, int], ...] = ()
    prohibitions: tuple[str, ...] = ()
    unverified_prohibitions: tuple[str, ...] = ()
    unverified_prohibition_spans: tuple[Span, ...] = ()
    raw_negation_spans: tuple[Span, ...] = ()
    negation_alignment_status: str = "NO_NEGATION"
    reason_required: bool = False
    quote_data: tuple[Span, ...] = ()
    ambiguity_spans: tuple[Span, ...] = ()
    hold_reasons: tuple[str, ...] = ()
    semantic_signature: str = ""
    frame_evidence: FrameEvidenceDocument | None = None
    target_binding: BindingDecision | None = None
    quantity_bindings: tuple[QuantityAttachment, ...] = ()


@dataclass(frozen=True)
class GoalEvaluation:
    """Text-only consumer result. None means this consumer lacks evidence."""

    status: str
    limited_projection_equivalent: bool | None
    full_semantic_equivalent: None
    goal_satisfied: bool | None
    represented_requirements_satisfied: bool | None = None
    checks: tuple[tuple[str, bool | None], ...] = ()
    unmet: tuple[str, ...] = ()
    evidence: tuple[tuple[str, str], ...] = ()
    unrepresented_semantics: tuple[str, ...] = (
        "topic/focus",
        "discourse linkage beyond one event",
        "lexical paraphrase quality",
    )
    integrity_status: Literal["verified", "unverified", "invalid"] = "unverified"
    verified_requirements: tuple[str, ...] = ()
    unverified_requirements: tuple[str, ...] = ()
    failed_requirements: tuple[str, ...] = ()
    success_count_eligible: bool = False


def _span(source: Source, start: int, end: int) -> Span:
    return Span.of(source, start, end)


def _valid_evidence_span(text: str, span: Any) -> bool:
    return (
        span is not None
        and type(getattr(span, "start", None)) is int
        and type(getattr(span, "end", None)) is int
        and 0 <= span.start < span.end <= len(text)
        and type(getattr(span, "text", None)) is str
        and text[span.start:span.end] == span.text
    )


def _located_tokens(text: str) -> tuple[_LocatedToken, ...]:
    cursor = 0
    out = []
    for token in _tagger()(text):
        at = text.find(token.surface, cursor)
        if at < 0:
            # Retain the rest of the original request as unread below; never
            # silently skip a token that cannot be aligned.
            out.append(_LocatedToken(token, cursor, len(text), False))
            cursor = len(text)
            continue
        end = at + len(token.surface)
        out.append(_LocatedToken(token, at, end))
        cursor = end
    return tuple(out)


def _quote_data(raw: str, source: Source) -> tuple[tuple[Span, ...], tuple[Span, ...]]:
    stack: list[tuple[str, int]] = []
    spans: list[Span] = []
    for index, char in enumerate(raw):
        if char in _QUOTE_PAIRS:
            stack.append((_QUOTE_PAIRS[char], index))
        elif stack and char == stack[-1][0]:
            _, start = stack.pop()
            spans.append(_span(source, start, index + 1))
    unclosed = tuple(_span(source, start, len(raw)) for _, start in stack)
    return tuple(sorted(spans, key=lambda item: item.start)), unclosed


def _frame_token_range(record_frame: Frame, located: tuple[_LocatedToken, ...], used: set[int], after: int) -> tuple[int, ...]:
    """Locate a Frame predicate over original offsets, including する stems."""
    pred = record_frame.predicate
    candidates: list[tuple[int, ...]] = []
    if pred.endswith("する") and pred != "する":
        stem = pred[:-2]
        for index, item in enumerate(located):
            if index in used or _base(item.token) != "する" or index == 0:
                continue
            if located[index - 1].token.surface == stem and index - 1 not in used:
                candidates.append((index - 1, index))
    else:
        for index, item in enumerate(located):
            if index not in used and _base(item.token) == pred:
                candidates.append((index,))
    candidates.sort(key=lambda indices: indices[0])
    eligible = [indices for indices in candidates if located[indices[0]].start >= after]
    if eligible:
        return eligible[0]
    return candidates[0] if candidates else ()


def _frame_records(frames: tuple[Frame, ...], located: tuple[_LocatedToken, ...], source: Source) -> tuple[_FrameRecord, ...]:
    used: set[int] = set()
    after = 0
    out = []
    for frame in frames:
        indices = _frame_token_range(frame, located, used, after)
        if not indices:
            out.append(_FrameRecord(frame, None, ()))
            continue
        used.update(indices)
        first, last = located[indices[0]], located[indices[-1]]
        frame_span = _span(source, first.start, last.end)
        after = last.end
        negative = None
        if frame.negated:
            following = [i for i, item in enumerate(located) if item.start >= last.end]
            if following:
                i = following[0]
                if located[i].token.surface in ("ず", "ない", "なかっ") or _base(located[i].token) == "ぬ":
                    negative = _span(source, located[i].start, located[i].end)
                    used.add(i)
                    after = max(after, located[i].end)
        out.append(_FrameRecord(frame, frame_span, indices, negative))
    return tuple(out)


def _source_markers(located: tuple[_LocatedToken, ...], source: Source) -> tuple[Span, ...]:
    return tuple(_span(source, item.start, item.end) for item in located
                 if item.token.surface in _SOURCE_MARKERS)


def _quantity_readings(located: tuple[_LocatedToken, ...], source: Source) -> tuple[tuple[tuple[str, int, Span], ...], set[int]]:
    readings = []
    covered: set[int] = set()
    for index in range(len(located) - 1):
        number_token = located[index].token.surface
        if number_token in _JP_NUMBERS:
            number = _JP_NUMBERS[number_token]
        elif number_token.isdecimal():
            number = int(number_token)
        else:
            continue
        if located[index + 1].token.surface != "文":
            continue
        end_index = index + 1
        kind = "exact_sentences"
        if end_index + 1 < len(located) and located[end_index + 1].token.surface == "以内":
            kind = "max_sentences"
            end_index += 1
        readings.append((kind, number, _span(source, located[index].start, located[end_index].end)))
        covered.update(range(index, end_index + 1))
    return tuple(readings), covered


def _role_readings(located: tuple[_LocatedToken, ...], source: Source) -> tuple[tuple[tuple[str, Span], ...], set[int]]:
    readings = []
    covered: set[int] = set()
    for index in range(len(located) - 1):
        key = (located[index].token.surface, located[index + 1].token.surface)
        role = _ROLE_WORDS.get(key)
        if role:
            readings.append((role, _span(source, located[index].start, located[index + 1].end)))
            covered.update((index, index + 1))
    return tuple(readings), covered


def _target_kind(target: str) -> str:
    # Compose a small source-marker + genitive + referent noun phrase. A
    # modifier or an unknown head stays unread; it is not swallowed by the
    # otherwise useful opaque Frame.patient value.
    for marker in _SOURCE_MARKERS:
        for head, kind in _TARGET_HEADS.items():
            if target in (marker + "の" + head, marker + head):
                return kind
    return ""


def _merge_unread(spans: list[Span], source: Source) -> tuple[Span, ...]:
    ranges = sorted((span.start, span.end) for span in spans if span.start < span.end)
    merged: list[list[int]] = []
    for start, end in ranges:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return tuple(_span(source, start, end) for start, end in merged)


def _doc_inputs(documents: Mapping[str, str]) -> tuple[str, str]:
    if not isinstance(documents, Mapping) or len(documents) != 1:
        raise ValueError("the diagnostic accepts exactly one source document")
    key, value = next(iter(documents.items()))
    if type(key) is not str or not key or type(value) is not str:
        raise TypeError("source document key and text must be nonempty str and str")
    return key, value


@dataclass(frozen=True)
class RequestSelectionProjection:
    """Raw-request-only selector input; READY does not mean Goal-ready.

    The source marker is a navigation anchor derived from the same-clause
    patient of one supported content action. It carries no source identity,
    source truth, or permission to realize a Goal.
    """

    status: Literal["READY", "HOLD"]
    reason: str
    raw_sha256: str = ""
    action: str = ""
    action_span: Span | None = None
    action_clause_id: str = ""
    action_frame_id: str = ""
    target: str = ""
    target_kind: str = ""
    target_span: Span | None = None
    selector_query: str = ""
    query_terms: tuple[str, ...] = ()
    unread_spans: tuple[Span, ...] = ()
    selection_scope: Literal["single_event", "all_matching_events"] = "single_event"
    event_scope_span: Span | None = None
    required_sentence_count: int | None = None
    quantity_span: Span | None = None

    def as_dict(self) -> dict:
        def span_record(span: Span | None) -> dict | None:
            if span is None:
                return None
            return {"source": span.source, "start": span.start,
                    "end": span.end, "sha256": span.sha256}

        return {
            "status": self.status,
            "reason": self.reason,
            "raw_sha256": self.raw_sha256,
            "action": self.action,
            "action_span": span_record(self.action_span),
            "action_clause_id": self.action_clause_id,
            "action_frame_id": self.action_frame_id,
            "target": self.target,
            "target_kind": self.target_kind,
            "target_span": span_record(self.target_span),
            "selector_query": self.selector_query,
            "query_terms": list(self.query_terms),
            "unread_spans": [span_record(span) for span in self.unread_spans],
            "selection_scope": self.selection_scope,
            "event_scope_span": span_record(self.event_scope_span),
            "required_sentence_count": self.required_sentence_count,
            "quantity_span": span_record(self.quantity_span),
        }


def _derive_request_selection_projection(
    raw_request: str, *, all_matching_events: bool,
) -> RequestSelectionProjection:
    """Derive a bounded candidate-search query from a fully covered raw Goal.

    This deliberately handles only one explicit source-event target attached
    as the unique local patient of one positive restate/explain Frame. It uses
    the existing Query, Frame, FrameEvidence, and action-patient binder. Any
    quote, negation, ambiguous/unread span, source-content target, extra action,
    unsupported role, or unbound quantity returns HOLD with no selector query.
    """
    if type(raw_request) is not str:
        return RequestSelectionProjection("HOLD", "raw request must be exact str")
    try:
        raw_sha = hashlib.sha256(raw_request.encode("utf-8")).hexdigest()
    except UnicodeEncodeError:
        return RequestSelectionProjection("HOLD", "raw request is not valid UTF-8")

    request_source = Source("request", raw_request, family="user", purpose="instruction")

    def hold(reason: str, *, action: str = "", action_span: Span | None = None,
             target: str = "", target_kind: str = "", target_span: Span | None = None,
             unread: tuple[Span, ...] = (), event_scope_span: Span | None = None,
             sentence_count: int | None = None) -> RequestSelectionProjection:
        return RequestSelectionProjection(
            "HOLD", reason, raw_sha, action, action_span,
            target=target, target_kind=target_kind, target_span=target_span,
            unread_spans=unread,
            selection_scope=("all_matching_events" if all_matching_events else "single_event"),
            event_scope_span=event_scope_span,
            required_sentence_count=sentence_count,
        )

    quote_spans, unclosed_quotes = _quote_data(raw_request, request_source)
    if quote_spans or unclosed_quotes:
        return hold("quoted request data has no selector-scope binding",
                    unread=tuple(sorted((*quote_spans, *unclosed_quotes),
                                        key=lambda span: span.start)))

    masked = content_reader.outside_quotes(raw_request)
    located = _located_tokens(masked)
    alignment_errors = tuple(
        _span(request_source, item.start, item.end)
        for item in located if not item.aligned
    )
    if alignment_errors:
        return hold("tokenizer output cannot be aligned to raw request spans",
                    unread=alignment_errors)

    try:
        evidence = read_frame_evidence("request", raw_request)
    except (TypeError, ValueError):
        return hold("FrameEvidence cannot cover the exact raw request",
                    unread=(_span(request_source, 0, len(raw_request)),)
                    if raw_request else ())
    if (evidence.source_id != "request" or evidence.source_text != raw_request
            or evidence.source_coverage_status not in ("EXACT", "WHITESPACE_ONLY")
            or evidence.alignment_status != "ALIGNED_BY_READER_ORDER"
            or evidence.reader_order_alignment_status != "ALIGNED_BY_READER_ORDER"
            or evidence.source_sha256 != raw_sha
            or not evidence.token_positions_complete or evidence.unmatched_frames
            or any(gap.classification != "WHITESPACE" for gap in evidence.source_gaps)):
        return hold("FrameEvidence request coverage or alignment is unresolved",
                    unread=tuple(_span(request_source, gap.span.start, gap.span.end)
                                 for gap in evidence.source_gaps if gap.span is not None
                                 and gap.classification != "WHITESPACE"))

    negative_spans = tuple(
        _span(request_source, item.start, item.end)
        for item in located if item.token.surface in _NEGATION_MARKERS
    )
    try:
        frames = tuple(read_all(masked))
    except (ImportError, ModuleNotFoundError):
        return hold("Frame reader is unavailable for raw request selection",
                    unread=(_span(request_source, 0, len(raw_request)),)
                    if raw_request else ())
    frame_records = _frame_records(frames, located, request_source)
    if negative_spans or any(record.frame.negated for record in frame_records):
        return hold("negative action scope is not licensed for selector projection",
                    unread=negative_spans)
    if any(record.frame.ambiguous or record.span is None for record in frame_records):
        return hold("Frame action alignment or ambiguity is unresolved",
                    unread=tuple(record.span for record in frame_records
                                 if record.span is not None))
    if any(clause.quote_status != "UNQUOTED"
           or clause.scope_status != "KNOWN"
           or clause.polarity != "POSITIVE"
           or clause.local_scope_status != "KNOWN"
           or clause.local_polarity != "POSITIVE"
           for clause in evidence.clauses):
        return hold("FrameEvidence quote, scope, or polarity is unresolved")

    action_records = [
        record for record in frame_records
        if record.frame.predicate in _CONTENT_ACTIONS or
        record.frame.predicate in _SIDE_EFFECT_ACTIONS
    ]
    if len(action_records) != 1:
        return hold("selector requires exactly one supported content action",
                    unread=tuple(record.span for record in action_records
                                 if record.span is not None))
    action_record = action_records[0]
    action_category = (_CONTENT_ACTIONS.get(action_record.frame.predicate)
                       or _SIDE_EFFECT_ACTIONS.get(action_record.frame.predicate))
    if all_matching_events:
        if action_category != "unsupported_summary":
            return hold("all-event selection requires one explicit summary action",
                        action_span=action_record.span)
        action = "summarize_events"
    elif action_category not in ("restate", "explain"):
        return hold("action is outside the source-event selector subset",
                    action_span=action_record.span)
    else:
        action = action_category
    if action_record.span is None or not action_record.token_indices:
        return hold("action Frame has no unique raw source span")

    markers = _source_markers(located, request_source)
    if len(markers) != 1:
        return hold("selector requires exactly one explicit source marker",
                    action=action, action_span=action_record.span,
                    unread=markers)
    target = action_record.frame.patient
    if type(target) is not str or not target:
        return hold("action Frame has no explicit patient target",
                    action=action, action_span=action_record.span,
                    unread=(markers[0],))
    target_kind = _target_kind(target)
    target_binding = bind_action_patient(
        raw_request, evidence, action_record.frame, action_record.span, target,
    )
    if target_binding.status != "BOUND" or target_binding.argument_span is None:
        return hold("action patient lacks unique same-owner case/span binding: "
                    + target_binding.reason,
                    action=action, action_span=action_record.span, target=target,
                    target_kind=target_kind, unread=(markers[0],))
    target_span = _span(request_source, target_binding.argument_span.start,
                        target_binding.argument_span.end)
    if target_kind != "source_event":
        return hold("source-content or unknown target is not a single-event selector",
                    action=action, action_span=action_record.span, target=target,
                    target_kind=target_kind, target_span=target_span,
                    unread=(target_span,))
    if (markers[0].start != target_span.start
            or markers[0].end > target_span.end
            or raw_request[target_span.start:target_span.end] != target):
        return hold("source marker is not the start of the bound action target",
                    action=action, action_span=action_record.span, target=target,
                    target_kind=target_kind, target_span=target_span,
                    unread=(markers[0], target_span))

    marker = raw_request[markers[0].start:markers[0].end]
    if marker not in _SOURCE_MARKERS:
        return hold("target anchor is outside the explicit source-marker set",
                    action=action, action_span=action_record.span, target=target,
                    target_kind=target_kind, target_span=target_span,
                    unread=(markers[0],))

    event_scope_spans = tuple(
        _span(request_source, item.start, item.end)
        for item in located if item.token.surface in {"すべて", "全て", "全部"}
    )
    event_scope_span = None
    if all_matching_events:
        if len(event_scope_spans) != 1:
            return hold("all-event selection needs one explicit all-scope marker",
                        action=action, action_span=action_record.span, target=target,
                        target_kind=target_kind, target_span=target_span,
                        unread=event_scope_spans)
        event_scope_span = event_scope_spans[0]
        if (target_binding.particle_span is None
                or not target_binding.particle_span.end <= event_scope_span.start
                or event_scope_span.end > action_record.span.start):
            return hold("all-scope marker is not locally attached after the target",
                        action=action, action_span=action_record.span, target=target,
                        target_kind=target_kind, target_span=target_span,
                        unread=(event_scope_span,))
    elif event_scope_spans:
        return hold("all-event scope is outside the single-event selector subset",
                    action=action, action_span=action_record.span, target=target,
                    target_kind=target_kind, target_span=target_span,
                    unread=event_scope_spans)

    role_readings, _role_indices = _role_readings(located, request_source)
    if role_readings:
        return hold("participant-role requirements are outside this selector projection",
                    action=action, action_span=action_record.span, target=target,
                    target_kind=target_kind, target_span=target_span,
                    unread=tuple(span for _role, span in role_readings))

    quantity_readings, quantity_indices = _quantity_readings(located, request_source)
    if any(kind != "exact_sentences" for kind, _number, _span in quantity_readings):
        return hold("only exact sentence-count constraints can be attached",
                    action=action, action_span=action_record.span, target=target,
                    target_kind=target_kind, target_span=target_span,
                    unread=tuple(span for kind, _number, span in quantity_readings
                                 if kind != "exact_sentences"))
    if all_matching_events and (
            len(quantity_readings) != 1
            or quantity_readings[0][0] != "exact_sentences"
            or quantity_readings[0][1] != 2):
        return hold("all-event summary requires an exact two-sentence output quantity",
                    action=action, action_span=action_record.span, target=target,
                    target_kind=target_kind, target_span=target_span,
                    event_scope_span=event_scope_span,
                    unread=tuple(span for _kind, _number, span in quantity_readings))
    quantity_bindings = []
    for _kind, _number, quantity_span in quantity_readings:
        attachment = bind_action_quantity(
            raw_request, evidence, action_record.frame, action_record.span,
            quantity_span, raw_request[quantity_span.start:quantity_span.end],
        )
        if attachment.status != "BOUND":
            return hold("sentence quantity does not bind to the action Frame: "
                        + attachment.reason,
                        action=action, action_span=action_record.span, target=target,
                        target_kind=target_kind, target_span=target_span,
                        unread=(quantity_span,))
        quantity_bindings.append(attachment)

    known_indices: set[int] = set(action_record.token_indices)
    for index, item in enumerate(located):
        if target_span.start <= item.start and item.end <= target_span.end:
            known_indices.add(index)
        if markers[0].start <= item.start and item.end <= markers[0].end:
            known_indices.add(index)
        if (event_scope_span is not None
                and event_scope_span.start <= item.start and item.end <= event_scope_span.end):
            known_indices.add(index)
        if any(span.start <= item.start and item.end <= span.end
               for _kind, _number, span in quantity_readings):
            known_indices.add(index)
        if (target_binding.particle_span is not None
                and item.start == target_binding.particle_span.start
                and item.end == target_binding.particle_span.end):
            known_indices.add(index)
        if item.token.surface in _PUNCTUATION | _POLITE:
            known_indices.add(index)
    for attachment in quantity_bindings:
        particle_span = attachment.particle_span
        if particle_span is not None:
            for index, item in enumerate(located):
                if item.start == particle_span.start and item.end == particle_span.end:
                    known_indices.add(index)
    action_te_indices = {
        index for index, item in enumerate(located)
        if item.token.surface == "て" and item.start == action_record.span.end
        and index + 1 < len(located)
        and located[index + 1].token.surface in _POLITE
    }
    unknown_spans = tuple(
        _span(request_source, item.start, item.end)
        for index, item in enumerate(located)
        if index not in known_indices and index not in action_te_indices
    )
    if unknown_spans:
        return hold("raw request has unrepresented selector meaning",
                    action=action, action_span=action_record.span, target=target,
                    target_kind=target_kind, target_span=target_span,
                    unread=unknown_spans, event_scope_span=event_scope_span)

    return RequestSelectionProjection(
        status="READY",
        reason=("one positive summary is bound to all matching source events"
                if all_matching_events else
                "one positive action is bound to one explicit source-event target"),
        raw_sha256=raw_sha,
        action=action,
        action_span=action_record.span,
        action_clause_id=target_binding.clause_id,
        action_frame_id=target_binding.frame_id,
        target=target,
        target_kind=target_kind,
        target_span=target_span,
        selector_query=marker,
        query_terms=(marker,),
        selection_scope=("all_matching_events" if all_matching_events else "single_event"),
        event_scope_span=event_scope_span,
        required_sentence_count=(2 if all_matching_events else None),
        quantity_span=(quantity_readings[0][2] if quantity_readings else None),
    )


def derive_request_selection_projection(raw_request: str) -> RequestSelectionProjection:
    """Project one explicitly requested source event for bounded navigation."""
    return _derive_request_selection_projection(raw_request, all_matching_events=False)


def derive_request_event_set_projection(raw_request: str) -> RequestSelectionProjection:
    """Read an explicit all-events summary Goal with an exact two-sentence output.

    READY describes only the raw request projection. Source event enumeration,
    completeness, realization, and full Goal satisfaction remain separate.
    """
    return _derive_request_selection_projection(raw_request, all_matching_events=True)


def is_event_set_request_attempt(raw_request: str) -> bool:
    """Route summary requests over a source-event target into the strict reader.

    This is only a router hint. It does not accept or fulfill the Goal; the
    raw producer and downstream evidence binder still decide READY/HOLD.
    """
    if type(raw_request) is not str or not raw_request:
        return False
    try:
        masked = content_reader.outside_quotes(raw_request)
        frames = tuple(read_all(masked))
    except (TypeError, ValueError, ImportError, ModuleNotFoundError):
        return False
    return any(
        frame.predicate in _CONTENT_ACTIONS
        and _CONTENT_ACTIONS[frame.predicate] == "unsupported_summary"
        and type(frame.patient) is str
        and any(head in frame.patient for head in _TARGET_HEADS)
        and any(marker in raw_request for marker in _SOURCE_MARKERS)
        for frame in frames
    )


def _signature(action: str, target: str, target_kind: str, event_predicate: str,
               source_id: str, source_sha: str, required_roles: tuple[str, ...],
               quantities: tuple[tuple[str, int], ...], prohibitions: tuple[str, ...],
               unverified_prohibitions: tuple[str, ...],
               negation_spans: tuple[tuple[int, int, str], ...],
               reason_required: bool) -> str:
    return digest({
        "version": VERSION,
        "action": action,
        "target": target,
        "target_kind": target_kind,
        "event_predicate": event_predicate,
        "source_id": source_id,
        "source_sha256": source_sha,
        "required_roles": required_roles,
        "quantities": quantities,
        "prohibitions": prohibitions,
        "unverified_prohibitions": unverified_prohibitions,
        "negation_spans": negation_spans,
        "reason_required": reason_required,
    })


def produce_goal(documents: Mapping[str, str], raw_request: str) -> GoalDraft:
    """Compose one explicit raw request with exactly one source assertion.

    API boundary: ``documents`` must be a one-entry Mapping[str, str], and
    ``raw_request`` an exact str. Unsupported structures are held in the
    returned draft. Invalid Python API types raise before any parse is run.
    """
    if type(raw_request) is not str:
        raise TypeError("raw_request must be str")
    document_id, document_text = _doc_inputs(documents)
    request_source = Source("request", raw_request, family="user", purpose="instruction")
    material = Source("document:" + document_id, document_text,
                      family="document", purpose="evidence", independent="user-supplied-document")
    held: list[str] = []
    ambiguities: list[Span] = []
    unread_candidates: list[Span] = []
    obligations: list[Obligation] = []

    def add(kind: str, span: Span, *, value: str = "", number: int = 0) -> None:
        obligations.append(Obligation("g" + str(len(obligations) + 1), kind, span,
                                       value=value, number=number))

    query = read_question(raw_request)
    quote_data, unclosed_quotes = _quote_data(raw_request, request_source)
    if quote_data:
        unread_candidates.extend(quote_data)
        held.append("quoted request span has no supported action or target binding")
    if unclosed_quotes:
        ambiguities.extend(unclosed_quotes)
        unread_candidates.extend(unclosed_quotes)
        held.append("unclosed quoted data")
    masked = content_reader.outside_quotes(raw_request)
    located = _located_tokens(masked)
    alignment_errors = [item for item in located if not item.aligned]
    if alignment_errors:
        held.append("tokenizer output could not be aligned to original request offsets")
        unread_candidates.append(_span(request_source, min(item.start for item in alignment_errors), len(raw_request)))
    frames = tuple(read_all(masked))
    frame_records = _frame_records(frames, located, request_source)
    known_token_indices: set[int] = set()

    # Sidecar input is the exact unmasked raw request. In particular, quoted
    # material stays visible to its quote gate and is never rewritten into a
    # user action by this producer. The full immutable result is retained in
    # GoalDraft so evaluate_candidate can rederive and compare every field.
    frame_evidence: FrameEvidenceDocument | None
    try:
        frame_evidence = read_frame_evidence("request", raw_request)
    except (TypeError, ValueError):
        frame_evidence = None
        held.append("FrameEvidence could not cover the exact raw request")
        if raw_request:
            unread_candidates.append(_span(request_source, 0, len(raw_request)))
    if frame_evidence is not None:
        if (frame_evidence.source_coverage_status not in ("EXACT", "WHITESPACE_ONLY")
                or frame_evidence.alignment_status != "ALIGNED_BY_READER_ORDER"
                or frame_evidence.unmatched_frames):
            held.append("FrameEvidence source alignment or coverage is unresolved")
        for gap in frame_evidence.source_gaps:
            if gap.classification != "WHITESPACE" and gap.span is not None:
                unread_candidates.append(_span(request_source, gap.span.start, gap.span.end))

    # FrameEvidence polarity is proposition-level, not instruction-level
    # authority. Until a separate Goal rule licenses the negative construction
    # as a user prohibition, keep its exact span unread and do not create a
    # confirmed prohibition obligation from a HOLD draft.
    negative_marker_spans = [
        _span(request_source, item.start, item.end)
        for item in located if item.token.surface in _NEGATION_MARKERS
    ]
    sidecar_unquoted_negative_spans = tuple(
        span
        for clause in (frame_evidence.clauses if frame_evidence is not None else ())
        if clause.quote_status == "UNQUOTED"
        for span in clause.negation_spans
        if _valid_evidence_span(raw_request, span)
    )
    raw_negative_coordinates = tuple(sorted((span.start, span.end)
                                            for span in negative_marker_spans))
    sidecar_negative_coordinates = tuple(sorted((span.start, span.end)
                                                for span in sidecar_unquoted_negative_spans))
    has_negative_frame = any(record.frame.negated for record in frame_records)
    negation_alignment_status = "NO_NEGATION"
    if not raw_negative_coordinates and not sidecar_negative_coordinates:
        negation_alignment_status = ("RAW_SPAN_COUNT_OR_OFFSETS_MISMATCH" if has_negative_frame
                                     else "NO_NEGATION")
        if has_negative_frame:
            held.append("negative Frame has no exact raw auxiliary span in FrameEvidence")
    elif raw_negative_coordinates == sidecar_negative_coordinates:
        known_scopes = all(
            clause.scope_status == "KNOWN"
            for clause in (frame_evidence.clauses if frame_evidence is not None else ())
            if clause.negation_spans and clause.quote_status == "UNQUOTED"
        )
        negation_alignment_status = ("RAW_SPANS_MATCH_SCOPE_KNOWN" if known_scopes
                                     else "RAW_SPANS_MATCH_SCOPE_UNKNOWN")
    else:
        negation_alignment_status = "RAW_SPAN_COUNT_OR_OFFSETS_MISMATCH"
        held.append("raw negative-marker count/spans differ from unquoted FrameEvidence")
        unread_candidates.extend(negative_marker_spans)
        unread_candidates.extend(
            _span(request_source, span.start, span.end)
            for span in sidecar_unquoted_negative_spans
        )
        ambiguities.extend(negative_marker_spans)
        ambiguities.extend(
            _span(request_source, span.start, span.end)
            for span in sidecar_unquoted_negative_spans
        )
    if negative_marker_spans or any(record.frame.negated for record in frame_records):
        held.append("negative construction remains unverified as an instruction-level prohibition")
        ambiguities.extend(negative_marker_spans)
        unread_candidates.extend(negative_marker_spans)
        ambiguities.extend(
            record.negation_span or record.span
            for record in frame_records if record.frame.negated and (record.negation_span or record.span)
        )
        if frame_evidence is not None:
            for clause in frame_evidence.clauses:
                if clause.quote_status != "UNQUOTED":
                    continue
                for span in clause.negation_spans:
                    if _valid_evidence_span(raw_request, span):
                        evidence_negation = _span(request_source, span.start, span.end)
                        unread_candidates.append(evidence_negation)
                        ambiguities.append(evidence_negation)
            if any(clause.scope_status != "KNOWN" for clause in frame_evidence.clauses
                   if clause.negation_spans and clause.quote_status == "UNQUOTED"):
                held.append("FrameEvidence negative scope remains UNKNOWN")

    # A quote is source data. Its contents never participate in action or
    # prohibition classification. Other unparsed quotation relations still
    # appear as unread outside-quote material and keep the Goal held.
    marker_spans = _source_markers(located, request_source)
    if not marker_spans:
        held.append("request does not explicitly bind to a source marker")
    elif len(marker_spans) > 1 and len({s.start for s in marker_spans}) > 1:
        held.append("multiple source mentions require source-binding review")
        ambiguities.extend(marker_spans)
    else:
        add("source_policy", marker_spans[0], value="one-source-one-assertion-evidence-only")
        for index, item in enumerate(located):
            if item.start == marker_spans[0].start:
                known_token_indices.add(index)

    try:
        source_event = bridge_source_event(document_view({document_id: document_text}))
    except (BridgeError, ContentError) as exc:
        source_event = None
        held.append("source is not one bridge-licensed assertion event: " + str(getattr(exc, "reason", exc)))

    quantity_readings, quantity_indices = _quantity_readings(located, request_source)
    known_token_indices.update(quantity_indices)
    quantities = tuple(sorted({(kind, number) for kind, number, _ in quantity_readings}))
    for kind, number, span in quantity_readings:
        add(kind, span, number=number)
    exacts = {number for kind, number in quantities if kind == "exact_sentences"}
    maxima = {number for kind, number in quantities if kind == "max_sentences"}
    if len(exacts) > 1 or (exacts and maxima and min(maxima) < max(exacts)):
        conflicting = [span for kind, _, span in quantity_readings if kind in ("exact_sentences", "max_sentences")]
        ambiguities.extend(conflicting)
        held.append("sentence-count constraints conflict")

    role_readings, role_indices = _role_readings(located, request_source)
    # ``誰にも`` is a negative-polarity/universal expression, not the explicit
    # WH recipient slot ``誰に``. This subset cannot resolve its scope, so keep
    # the whole phrase unread and do not turn it into a required recipient.
    filtered_role_readings = []
    filtered_role_indices: set[int] = set()
    for role, role_span in role_readings:
        matched_npi = None
        for index in range(len(located) - 2):
            if (_ROLE_WORDS.get((located[index].token.surface,
                                 located[index + 1].token.surface)) == role
                    and located[index + 2].token.surface == "も"
                    and located[index].start == role_span.start):
                matched_npi = index
                break
        if matched_npi is None:
            filtered_role_readings.append((role, role_span))
            for index, item in enumerate(located):
                if role_span.start <= item.start and item.end <= role_span.end:
                    filtered_role_indices.add(index)
        else:
            index = matched_npi
            npi_span = _span(request_source, located[index].start, located[index + 2].end)
            unread_candidates.append(npi_span)
            ambiguities.append(npi_span)
            held.append("WH plus も role phrase is unresolved; recipient requirement was not inferred")
    role_readings = tuple(filtered_role_readings)
    role_indices = filtered_role_indices
    known_token_indices.update(role_indices)
    known_token_indices.update(quantity_indices)
    required_roles = tuple(role for role in _ROLE_ORDER if any(found == role for found, _ in role_readings))
    for role, span in role_readings:
        add("required_role", span, value=role)

    content_frames: list[tuple[str, _FrameRecord]] = []
    prohibited: list[tuple[str, _FrameRecord]] = []
    wh_start = min((span.start for _, span in role_readings), default=-1)
    positive_action_starts = [
        record.span.start for record in frame_records
        if record.span and not record.frame.negated
        and _CONTENT_ACTIONS.get(record.frame.predicate) in ("restate", "explain")
    ]
    target_event_record = None
    if required_roles and positive_action_starts:
        action_start = min(positive_action_starts)
        possible_events = [
            record for record in frame_records
            if record.span and wh_start < record.span.start < action_start
            and record.frame.predicate not in ("分かる", "ある")
            and record.frame.predicate not in _CONTENT_ACTIONS
            and record.frame.predicate not in _SIDE_EFFECT_ACTIONS
        ]
        if possible_events:
            target_event_record = possible_events[0]

    for index, record in enumerate(frame_records):
        frame = record.frame
        pred = frame.predicate
        category = _CONTENT_ACTIONS.get(pred) or _SIDE_EFFECT_ACTIONS.get(pred)
        if record.span is None:
            held.append("Frame predicate could not be mapped to an original request span: " + pred)
            unread_candidates.append(_span(request_source, 0, len(raw_request)))
            continue
        if record is target_event_record:
            known_token_indices.update(record.token_indices)
            add("target_event_predicate", record.span, value=pred)
        elif category:
            known_token_indices.update(record.token_indices)
            if frame.negated:
                # Preserve the negation suffix as unread/unverified below; a
                # negative Frame is not yet an instruction obligation.
                if not record.negation_span:
                    ambiguities.append(record.span)
                    held.append("Frame negation could not be aligned to an original suffix span")
                prohibited.append((category, record))
                if category == "unsupported_summary":
                    held.append("summary prohibition is outside this Goal subset")
            elif category in ("restate", "explain"):
                content_frames.append((category, record))
                add("action", record.span, value=category)
            elif category == "unsupported_summary":
                held.append("summary action is recognized but outside this Goal subset")
                add("unsupported_action", record.span, value=category)
            else:
                held.append("positive external side-effect action is outside this text-only consumer")
                add("unsupported_action", record.span, value=category)
        elif pred == "する" or pred == "くれる":
            known_token_indices.update(record.token_indices)
        elif pred == "分かる" and wh_start >= 0 and record.span.start > wh_start:
            # The requested role slots are retained below, but the broader
            # readability demand is not measured by this consumer.
            unread_candidates.append(record.span)
            held.append("readability demand is not represented by typed role obligations")
        else:
            unread_candidates.append(record.span)
            held.append("unsupported predicate meaning remains unread: " + pred)
        if frame.ambiguous:
            ambiguities.append(record.span)
            held.append("Frame marked this clause ambiguous")

    if len(content_frames) != 1:
        if len(content_frames) > 1:
            ambiguities.extend(record.span for _, record in content_frames if record.span)
            held.append("multiple positive content actions have no supported composition order")
        else:
            held.append("no supported positive paraphrase or explanation action")
    action = content_frames[0][0] if len(content_frames) == 1 else ""
    action_record = content_frames[0][1] if len(content_frames) == 1 else None

    prohibitions: tuple[str, ...] = ()
    unverified_prohibitions = tuple(sorted({category for category, _ in prohibited}))
    raw_negation_spans = tuple(negative_marker_spans)
    unverified_span_candidates = [
        record.negation_span for _, record in prohibited if record.negation_span is not None
    ]
    negative_predicate_ranges = {
        (record.span.start, record.span.end)
        for _, record in prohibited if record.span is not None
    }
    if frame_evidence is not None and unverified_prohibitions:
        unverified_span_candidates.extend(
            _span(request_source, span.start, span.end)
            for clause in frame_evidence.clauses
            if clause.predicate_span is not None
            and (clause.predicate_span.start, clause.predicate_span.end) in negative_predicate_ranges
            for span in clause.negation_spans
            if _valid_evidence_span(raw_request, span)
        )
    unverified_prohibition_spans = _merge_unread(unverified_span_candidates, request_source)
    if unverified_prohibitions:
        held.append("one or more negative predicates are unverified, not confirmed prohibitions")
    if action and action in unverified_prohibitions:
        matching = [record.span for category, record in prohibited if category == action and record.span]
        if action_record and action_record.span:
            ambiguities.append(action_record.span)
        ambiguities.extend(matching)
        held.append("the requested action conflicts with an unverified negative predicate")

    # Bind target only from the positive content-action Frame itself. A
    # patient attached to another predicate cannot be borrowed, even when its
    # string is the only/first patient in the request.
    target = ""
    target_candidate = action_record.frame.patient if action_record else ""
    target_binding: BindingDecision | None = None
    target_span: Span | None = None
    target_kind = ""
    if action_record is not None and frame_evidence is not None and target_candidate:
        target_binding = bind_action_patient(
            raw_request, frame_evidence, action_record.frame,
            action_record.span, target_candidate,
        )
        if target_binding.status == "BOUND":
            target = target_candidate
            assert target_binding.argument_span is not None
            target_span = _span(request_source,
                                target_binding.argument_span.start,
                                target_binding.argument_span.end)
            if not any(marker.start >= target_span.start and marker.end <= target_span.end
                       for marker in marker_spans):
                held.append("action-local target is not compositionally linked to the named source")
                unread_candidates.append(target_span)
            else:
                target_kind = _target_kind(target)
                if not target_kind:
                    unread_candidates.append(target_span)
                    held.append("target head is outside the represented source-event/content subset")
                elif target_kind != "source_event":
                    unread_candidates.append(target_span)
                    held.append("source_content completeness is not verified by the single-event projection")
                else:
                    add("target", target_span, value=target_kind)
                    for index, item in enumerate(located):
                        if target_span.start <= item.start and item.end <= target_span.end:
                            known_token_indices.add(index)
                    if target_binding.particle_span is not None:
                        for index, item in enumerate(located):
                            if (item.start == target_binding.particle_span.start
                                    and item.end == target_binding.particle_span.end):
                                known_token_indices.add(index)
        else:
            held.append("action target binding held: " + target_binding.reason)
            for index, item in enumerate(located):
                if item.token.surface == target_candidate:
                    unread_candidates.append(_span(request_source, item.start, item.end))
    else:
        held.append("positive content action has no explicit same-clause patient target")

    # Quantity is read from the raw morphology above, then its ``で`` phrase is
    # attached to the same action clause using the sidecar's local UNKNOWN
    # argument record. That record never becomes a semantic role or fact.
    quantity_bindings: list[QuantityAttachment] = []
    quantity_particle_indices: set[int] = set()
    if quantity_readings:
        if action_record is None or frame_evidence is None:
            held.append("quantity phrase has no verified content-action clause")
        else:
            for kind, _number, quantity_span in quantity_readings:
                if kind != "exact_sentences":
                    held.append("non-exact sentence bound is outside the attached quantity subset")
                    unread_candidates.append(quantity_span)
                    continue
                value = raw_request[quantity_span.start:quantity_span.end]
                binding = bind_action_quantity(
                    raw_request, frame_evidence, action_record.frame,
                    action_record.span, quantity_span, value,
                )
                quantity_bindings.append(binding)
                if binding.status != "BOUND":
                    held.append("quantity-to-action binding held: " + binding.reason)
                    unread_candidates.append(quantity_span)
                    continue
                if binding.particle_span is not None:
                    for index, item in enumerate(located):
                        if (item.start == binding.particle_span.start
                                and item.end == binding.particle_span.end):
                            quantity_particle_indices.add(index)
    known_token_indices.update(quantity_particle_indices)

    target_predicate = target_event_record.frame.predicate if target_event_record else ""
    if required_roles:
        if target_event_record:
            if source_event and target_predicate != source_event.projection.predicate:
                held.append("requested event predicate differs from the single source event")
                ambiguities.append(target_event_record.span)
        else:
            held.append("required participant roles have no uniquely parsed target event")
            ambiguities.extend(span for _, span in role_readings)

    reason_required = action == "explain"
    if reason_required:
        action_span = action_record.span if action_record else _span(request_source, 0, len(raw_request))
        add("reason_evidence", action_span, value="source-grounded-reason-required")
        held.append("single assertion evidence does not provide a reason or causal relation")

    # Cover ordinary Japanese request grammar. Any remaining unquoted token
    # becomes an unread span. This is the central no-drop rule.
    action_te_indices: set[int] = set()
    if action_record is not None:
        for index, item in enumerate(located):
            if item.token.surface != "て" or item.start != action_record.span.end:
                continue
            if (index + 1 < len(located)
                    and located[index + 1].token.surface in _POLITE):
                action_te_indices.add(index)
    for index, item in enumerate(located):
        if index in known_token_indices:
            continue
        token = item.token
        surface = token.surface
        if surface in _PUNCTUATION or surface in _POLITE or index in action_te_indices:
            known_token_indices.add(index)
            continue
        unread_candidates.append(_span(request_source, item.start, item.end))

    unread = _merge_unread(unread_candidates, request_source)
    if unread:
        held.append("one or more raw request spans remain unread")
    ambiguity_spans = _merge_unread(ambiguities, request_source)
    if ambiguity_spans:
        held.append("one or more readings are ambiguous")

    if len(marker_spans) and source_event is not None:
        source_id = document_id
        source_policy = "one-source-one-assertion-evidence-only"
    else:
        source_id = ""
        source_policy = ""
    if source_event:
        role_names = {name for name, _ in source_event.projection.roles}
        missing_roles = set(required_roles) - role_names
        if missing_roles:
            held.append("source event lacks required participant roles: " + ",".join(sorted(missing_roles)))
            ambiguities.extend(span for role, span in role_readings if role in missing_roles)
            ambiguity_spans = _merge_unread(ambiguities, request_source)

    signature = _signature(
        action, target, target_kind, target_predicate, source_id,
        material.sha256, required_roles, quantities, prohibitions,
        unverified_prohibitions,
        tuple((span.start, span.end, raw_request[span.start:span.end])
              for span in raw_negation_spans),
        reason_required,
    )
    ledger = Ledger(
        brief=request_source,
        materials=(material,),
        obligations=tuple(obligations),
        unread=unread,
        mode="diagnostic_source_bound",
    )
    unique_held = tuple(dict.fromkeys(held))
    status = "READY" if not unique_held and not unread and source_event is not None else "HOLD"
    return GoalDraft(
        query=query,
        ledger=ledger,
        status=status,
        action=action,
        target=target,
        target_kind=target_kind,
        target_span=target_span,
        target_predicate=target_predicate,
        source_event=source_event,
        source_id=source_id,
        source_policy=source_policy,
        required_roles=required_roles,
        quantities=quantities,
        prohibitions=prohibitions,
        unverified_prohibitions=unverified_prohibitions,
        unverified_prohibition_spans=unverified_prohibition_spans,
        raw_negation_spans=raw_negation_spans,
        negation_alignment_status=negation_alignment_status,
        reason_required=reason_required,
        quote_data=quote_data,
        ambiguity_spans=ambiguity_spans,
        hold_reasons=unique_held,
        semantic_signature=signature,
        frame_evidence=frame_evidence,
        target_binding=target_binding,
        quantity_bindings=tuple(quantity_bindings),
    )


def _sentence_count(text: str) -> int:
    count = 0
    in_sentence = False
    for char in text:
        if char in "。！？!?\n":
            if in_sentence:
                count += 1
                in_sentence = False
        elif not char.isspace():
            in_sentence = True
    if in_sentence:
        count += 1
    return count


def _mismatch_paths(actual: Any, expected: Any, path: str) -> list[str]:
    """Compare every typed field, including nested metadata and container types."""
    if type(actual) is not type(expected):
        return [path]
    if is_dataclass(expected) and not isinstance(expected, type):
        mismatches: list[str] = []
        for item in fields(expected):
            child = f"{path}.{item.name}" if path else item.name
            mismatches.extend(_mismatch_paths(getattr(actual, item.name), getattr(expected, item.name), child))
        return mismatches
    if type(expected) in (tuple, list):
        if len(actual) != len(expected):
            return [path]
        mismatches = []
        for index, (left, right) in enumerate(zip(actual, expected)):
            mismatches.extend(_mismatch_paths(left, right, f"{path}[{index}]"))
        return mismatches
    if type(expected) is dict:
        if actual.keys() != expected.keys():
            return [path + ".keys"]
        mismatches = []
        for key in expected:
            mismatches.extend(_mismatch_paths(actual[key], expected[key], f"{path}[{key!r}]"))
        return mismatches
    try:
        equal = actual == expected
        return [] if type(equal) is bool and equal else [path]
    except (TypeError, ValueError, AttributeError, RecursionError):
        return [path]


def _normalized_event_prototype(
    envelope: SourceEventEnvelope | None,
    document_id: str,
    document_text: str,
) -> tuple[str | None, bool]:
    """Return typed event content with only telemetry timing normalized.

    document_view embeds nondeterministic ``ingest_ms`` telemetry in its
    reversible snapshot. Validate each envelope's own byte hash, confirm the
    actual source pair is inside the snapshot, then normalize that one field
    so producer reruns can compare the complete event content.
    """
    if envelope is None:
        return None, True
    if type(envelope) is not SourceEventEnvelope or type(envelope.prototype) is not str:
        return None, False
    raw = envelope.prototype
    try:
        # Reuse the bridge's strict typed decoder before the JSON view below
        # is normalized. Its object_pairs_hook rejects duplicate fields at
        # every depth, and its decoder rejects non-finite numbers and invalid
        # tagged/type shapes. Without this boundary, json.loads would silently
        # keep one of two conflicting keys before comparison.
        restored_view = restore_source_event(envelope)
        if (type(restored_view.sources) is not dict
                or restored_view.sources.get(document_id) != document_text):
            return None, False
        hash_valid = hashlib.sha256(raw.encode("utf-8")).hexdigest() == envelope.prototype_sha256
        value = json.loads(raw)
        if type(value) is not dict or value.get("type") != "View" or type(value.get("fields")) is not dict:
            return None, False
        view_fields = value["fields"]
        source_map = view_fields.get("sources")
        source_pairs = source_map.get("dict") if type(source_map) is dict else None
        if type(source_pairs) is not list or [document_id, document_text] not in source_pairs:
            return None, False
        if "ingest_ms" in view_fields:
            view_fields["ingest_ms"] = 0.0
        normalized = json.dumps(value, ensure_ascii=False, sort_keys=True,
                                separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, KeyError, RecursionError):
        return None, False
    return normalized, hash_valid


def _source_event_matches(
    actual: SourceEventEnvelope | None,
    expected: SourceEventEnvelope | None,
    document_id: str,
    document_text: str,
) -> tuple[bool, bool]:
    actual_prototype, actual_hash_valid = _normalized_event_prototype(actual, document_id, document_text)
    expected_prototype, expected_hash_valid = _normalized_event_prototype(expected, document_id, document_text)
    hashes_valid = actual_hash_valid and expected_hash_valid
    if actual is None or expected is None:
        return actual is expected, hashes_valid
    if type(actual) is not SourceEventEnvelope or type(expected) is not SourceEventEnvelope:
        return False, False
    if not hashes_valid or actual_prototype is None or expected_prototype is None:
        return False, False
    if actual_prototype != expected_prototype:
        return False, True
    ignored = {"prototype", "prototype_sha256"}
    for item in fields(SourceEventEnvelope):
        if item.name in ignored:
            continue
        if _mismatch_paths(getattr(actual, item.name), getattr(expected, item.name), item.name):
            return False, True
    return True, True


def _draft_mismatch_paths(
    actual: GoalDraft,
    expected: GoalDraft,
    document_id: str,
    document_text: str,
) -> list[str]:
    if type(actual) is not GoalDraft or type(expected) is not GoalDraft:
        return ["draft"]
    mismatches: list[str] = []
    for item in fields(GoalDraft):
        if item.name == "source_event":
            matches, _ = _source_event_matches(
                actual.source_event, expected.source_event, document_id, document_text
            )
            if not matches:
                mismatches.append("draft.source_event")
            continue
        mismatches.extend(_mismatch_paths(
            getattr(actual, item.name), getattr(expected, item.name), "draft." + item.name
        ))
    return mismatches


def _hold_evaluation(
    reason: str,
    *,
    integrity_status: Literal["verified", "unverified", "invalid"],
    checks: tuple[tuple[str, bool | None], ...],
    verified_requirements: tuple[str, ...] = (),
    unverified_requirements: tuple[str, ...] = (),
    failed_requirements: tuple[str, ...] = (),
    evidence: tuple[tuple[str, str], ...] = (),
) -> GoalEvaluation:
    return GoalEvaluation(
        "HOLD", None, None, None,
        represented_requirements_satisfied=None,
        checks=checks,
        unmet=(reason,),
        evidence=evidence,
        integrity_status=integrity_status,
        verified_requirements=verified_requirements,
        unverified_requirements=unverified_requirements or (reason,),
        failed_requirements=failed_requirements,
        success_count_eligible=False,
    )


def _source_event_sha256_for_evidence(value: Any) -> str:
    """Return a diagnostic digest only from the exact supported envelope type."""
    if type(value) is not SourceEventEnvelope:
        return ""
    prototype_sha256 = value.prototype_sha256
    return prototype_sha256 if type(prototype_sha256) is str else ""


def _source_hash_matches(ledger: Ledger, document_id: str, document_text: str) -> bool:
    if type(ledger) is not Ledger or type(ledger.materials) is not tuple or len(ledger.materials) != 1:
        return False
    material = ledger.materials[0]
    if type(material) is not Source:
        return False
    if any(type(value) is not str for value in (
        material.id, material.text, material.family, material.purpose, material.independent
    )):
        return False
    expected_sha = hashlib.sha256(document_text.encode("utf-8")).hexdigest()
    return (
        material.id == "document:" + document_id
        and material.text == document_text
        and material.sha256 == expected_sha
        and material.family == "document"
        and material.purpose == "evidence"
        and material.independent == "user-supplied-document"
    )


def evaluate_candidate(
    draft: GoalDraft,
    candidate: str,
    *,
    raw_request: str | None = None,
    documents: Mapping[str, str] | None = None,
) -> GoalEvaluation:
    """Re-derive the draft from trusted raw inputs before checking a candidate.

    ``raw_request`` and ``documents`` are mandatory for a verified result.
    The two-argument legacy call is accepted only as an unverified HOLD.
    """
    if type(draft) is not GoalDraft:
        return _hold_evaluation(
            "draft must be an exact GoalDraft instance",
            integrity_status="invalid",
            checks=(("draft_type", False),),
            failed_requirements=("draft_type",),
        )
    if raw_request is None or documents is None:
        return _hold_evaluation(
            "trusted raw_request and documents are required; legacy API call is unverified",
            integrity_status="unverified",
            checks=(("raw_request", None), ("documents", None), ("draft_rederived_from_inputs", None)),
            unverified_requirements=("raw_request", "documents", "draft_rederived_from_inputs"),
        )
    if type(raw_request) is not str:
        return _hold_evaluation(
            "raw_request must be str",
            integrity_status="unverified",
            checks=(("raw_request", False), ("draft_rederived_from_inputs", None)),
            failed_requirements=("raw_request",),
            unverified_requirements=("draft_rederived_from_inputs",),
        )
    try:
        document_id, document_text = _doc_inputs(documents)
    except (TypeError, ValueError) as exc:
        return _hold_evaluation(
            "trusted documents are invalid: " + str(exc),
            integrity_status="unverified",
            checks=(("documents", False), ("draft_rederived_from_inputs", None)),
            failed_requirements=("documents",),
            unverified_requirements=("draft_rederived_from_inputs",),
        )

    # Snapshot the caller's Mapping once, then re-run the exact producer over
    # that concrete input. All draft fields are claims to compare, not inputs.
    trusted_documents = {document_id: document_text}
    expected = produce_goal(trusted_documents, raw_request)
    mismatch_paths = _draft_mismatch_paths(draft, expected, document_id, document_text)
    raw_request_matches = (
        type(draft.ledger) is Ledger
        and type(draft.ledger.brief) is Source
        and type(draft.ledger.brief.text) is str
        and draft.ledger.brief.text == raw_request
    )
    source_hash_matches = _source_hash_matches(draft.ledger, document_id, document_text)
    ledger_matches = _mismatch_paths(draft.ledger, expected.ledger, "ledger") == []
    obligations_match = (
        type(draft.ledger) is Ledger
        and _mismatch_paths(draft.ledger.obligations, expected.ledger.obligations, "ledger.obligations") == []
    )
    source_event_matches, source_event_hashes_valid = _source_event_matches(
        draft.source_event, expected.source_event, document_id, document_text
    )
    source_event_type_valid = (
        draft.source_event is None or type(draft.source_event) is SourceEventEnvelope
    )
    integrity_checks: tuple[tuple[str, bool | None], ...] = (
        ("raw_request_matches", raw_request_matches),
        ("source_document_hash_matches", source_hash_matches),
        ("obligations_rederived", obligations_match),
        ("ledger_rederived", ledger_matches),
        ("source_event_type_valid", source_event_type_valid),
        ("source_event_prototype_hash_valid", source_event_hashes_valid),
        ("source_event_rederived", source_event_matches),
        ("all_draft_fields_rederived", not mismatch_paths),
    )
    if any(value is not True for _, value in integrity_checks):
        paths = tuple(dict.fromkeys(mismatch_paths))
        reasons = [name for name, value in integrity_checks if value is not True]
        if paths:
            reasons.append("draft field mismatch paths: " + ", ".join(paths))
        return _hold_evaluation(
            "draft failed producer revalidation: " + "; ".join(reasons),
            integrity_status="invalid",
            checks=integrity_checks,
            failed_requirements=tuple(name for name, value in integrity_checks if value is False),
            unverified_requirements=paths or tuple(reasons),
            evidence=(("trusted_source_sha256", expected.ledger.materials[0].sha256),
                      ("draft_source_event_sha256", _source_event_sha256_for_evidence(draft.source_event)),
                      ("rederived_source_event_sha256", _source_event_sha256_for_evidence(expected.source_event))),
        )

    if expected.status != "READY":
        reasons = expected.hold_reasons or ("producer did not establish READY",)
        return _hold_evaluation(
            "producer evidence remains held: " + "; ".join(reasons),
            integrity_status="verified",
            checks=integrity_checks + (("producer_ready", False),),
            verified_requirements=(),
            unverified_requirements=tuple("producer_hold: " + reason for reason in reasons),
            evidence=(("trusted_source_sha256", expected.ledger.materials[0].sha256),
                      ("draft_source_event_sha256", _source_event_sha256_for_evidence(draft.source_event)),
                      ("rederived_source_event_sha256", _source_event_sha256_for_evidence(expected.source_event)),
                      ("ledger_hash", expected.ledger.hash)),
        )

    if type(candidate) is not str:
        return _hold_evaluation(
            "candidate must be str",
            integrity_status="verified",
            checks=integrity_checks + (("candidate_input", False),),
            failed_requirements=("candidate_input",),
        )

    # Continue from the freshly derived value, never from caller-owned fields.
    verified_draft = expected
    verification = None
    unmet: list[str] = []
    try:
        verification = verify_event_realization(verified_draft.source_event, candidate)
        projection_ok: bool | None = bool(verification["passed"])
    except BridgeError as exc:
        projection_ok = False
        unmet.append("limited projection mismatch: " + exc.reason)

    projection = verified_draft.source_event.projection
    constraints: list[tuple[str, bool | None]] = list(integrity_checks) + [
        ("request_action_target_binding", bool(
            verified_draft.target_binding is not None
            and verified_draft.target_binding.status == "BOUND"
        )),
        ("request_quantity_binding", all(
            binding.status == "BOUND" for binding in verified_draft.quantity_bindings
        ) and len(verified_draft.quantity_bindings) >= len(verified_draft.quantities)),
        ("limited_projection_equivalent", projection_ok)
    ]
    event_roles = {role for role, _ in projection.roles}
    role_ok = set(verified_draft.required_roles) <= event_roles
    constraints.append(("required_roles", role_ok))
    predicate_ok = not verified_draft.target_predicate or verified_draft.target_predicate == projection.predicate
    constraints.append(("target_event_predicate", predicate_ok))

    actual_sentences = _sentence_count(candidate)
    quantity_checks = []
    for kind, number in verified_draft.quantities:
        quantity_checks.append(actual_sentences == number if kind == "exact_sentences" else actual_sentences <= number)
    quantity_ok = all(quantity_checks) if quantity_checks else True
    constraints.append(("sentence_quantity", quantity_ok))

    if verified_draft.action == "restate":
        original = restore_source_event(verified_draft.source_event)
        source_text = next(iter(original.sources.values()))
        transformed = content_reader.norm(candidate) != content_reader.norm(source_text)
        constraints.append(("surface_differs_from_source", transformed))
        if not transformed:
            unmet.append("restate request returned the source surface unchanged")
    elif verified_draft.action == "explain":
        constraints.append(("reason_evidence", False))
        unmet.append("reason evidence is absent from the licensed one-event source")

    if verified_draft.prohibitions:
        constraints.append(("prohibitions_satisfied", None))
        unmet.append("prohibition scope is outside this text-only event projection")
    else:
        constraints.append(("prohibitions_satisfied", True))

    if verified_draft.ledger.unread or verified_draft.ambiguity_spans:
        constraints.append(("request_interpretation_complete", False))
        unmet.append("raw request has unread or ambiguous meaning")
    else:
        constraints.append(("request_interpretation_complete", True))

    integrity_names = {name for name, _ in integrity_checks}
    requirement_constraints = [(name, value) for name, value in constraints if name not in integrity_names]
    values = [value for _, value in requirement_constraints]
    if False in values:
        represented_satisfied: bool | None = False
    elif None in values:
        represented_satisfied = None
    else:
        represented_satisfied = True
    goal_satisfied: bool | None = False if represented_satisfied is False else None
    if represented_satisfied is None:
        status = "HOLD"
    elif represented_satisfied is False:
        status = "EVALUATED"
    else:
        status = "PARTIAL"

    verified_requirements = tuple(name for name, value in requirement_constraints if value is True)
    failed_requirements = tuple(name for name, value in requirement_constraints if value is False)
    unverified_requirements = tuple(name for name, value in requirement_constraints if value is None)
    success_count_eligible = (
        goal_satisfied is True
        and not unverified_requirements
        and not verified_draft.unrepresented_semantics
    )

    evidence_items = [("trusted_source_sha256", expected.ledger.materials[0].sha256)]
    if verification:
        source = verification.get("source", {})
        evidence_items.extend((
            ("source_sha256", str(source.get("sha256", ""))),
            ("source_clause_id", str(verification.get("original_clause_id", ""))),
        ))
    evidence_items.append(("ledger_hash", verified_draft.ledger.hash))
    return GoalEvaluation(
        status=status,
        limited_projection_equivalent=projection_ok,
        full_semantic_equivalent=None,
        goal_satisfied=goal_satisfied,
        represented_requirements_satisfied=represented_satisfied,
        checks=tuple(constraints),
        unmet=tuple(dict.fromkeys(unmet)),
        evidence=tuple(evidence_items),
        integrity_status="verified",
        verified_requirements=verified_requirements,
        unverified_requirements=unverified_requirements,
        failed_requirements=failed_requirements,
        success_count_eligible=success_count_eligible,
    )
