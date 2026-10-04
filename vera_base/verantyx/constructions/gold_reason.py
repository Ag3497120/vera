"""Read explicit Japanese reason clauses with independently checked scope."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import unicodedata

from ..semantic_ir import Clause, Role, Span, Variable
from . import Construction, ConstructionContext, Reading, register


_TRIM_LEFT = frozenset(" \t\r\n、，,;；")
_TRIM_RIGHT = frozenset(" \t\r\n、，,;；")
_MARKERS = ("ので", "から")
_HONORIFICS = ("さん", "氏", "くん", "ちゃん", "様", "先生", "選手")


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start] in _TRIM_LEFT:
        start += 1
    while end > start and text[end - 1] in _TRIM_RIGHT:
        end -= 1
    return start, end


def _relation_spans(text: str) -> tuple[int, int, int, str, int, int] | None:
    found = [(text.find(marker), marker) for marker in _MARKERS]
    found = [(start, marker) for start, marker in found if start >= 0]
    if len(found) != 1:
        return None
    marker, marker_text = found[0]
    if text.find(marker_text, marker + len(marker_text)) >= 0:
        return None
    cause_start, cause_end = _trim(text, 0, marker)
    effect_start, effect_end = _trim(text, marker + len(marker_text), len(text))
    if cause_start >= cause_end or effect_start >= effect_end:
        return None
    return cause_start, cause_end, marker, marker_text, effect_start, effect_end


def _local_frame_license(clause: Clause, body: Span) -> bool:
    """Recheck one isolated frame with the native source licensor."""
    if clause.span.source != body.source or body.start < clause.span.start or body.end > clause.span.end:
        return False
    local_source = "gold_reason_local"

    def local_span(span: Span) -> Span | None:
        if (span.source != body.source or span.start < body.start or span.end > body.end
                or span.end <= span.start):
            return None
        local_start = span.start - body.start
        local_end = span.end - body.start
        if body.text[local_start:local_end] != span.text:
            return None
        return Span(local_source, local_start, local_end, span.text)

    predicate_span = local_span(clause.predicate_span)
    if predicate_span is None:
        return False
    roles: list[Role] = []
    for role in clause.roles:
        span = local_span(role.span)
        if span is None:
            return False
        roles.append(replace(role, span=span))
    condition_spans = tuple(local_span(span) for span in clause.condition_spans)
    exception_spans = tuple(local_span(span) for span in clause.exception_spans)
    if any(span is None for span in condition_spans + exception_spans):
        return False
    local_body = Span(local_source, 0, len(body.text), body.text)
    local_clause = replace(
        clause,
        predicate_span=predicate_span,
        roles=tuple(roles),
        span=local_body,
        body_span=local_body,
        condition_spans=condition_spans,
        exception_spans=exception_spans,
        rule="frame",
        unsupported=(),
    )
    from ..semantic_ir import View
    from ..semantic_verify import Rejected, license_clause

    view = View({local_source: body.text}, (local_clause,))
    try:
        result = license_clause(local_clause, view)
    except Rejected:
        return False
    return result is not False


def _local_body(clause: Clause, source_text: str) -> Span | None:
    parts = _relation_spans(source_text)
    if parts is None:
        return None
    cause_start, cause_end, _, _, effect_start, effect_end = parts
    scope_start, scope_end = cause_start, cause_end
    if clause.predicate_span.start >= clause.span.start + effect_start:
        scope_start, scope_end = effect_start, effect_end
    return Span(clause.span.source, clause.span.start + scope_start,
                clause.span.start + scope_end, source_text[scope_start:scope_end])


def _stable_role_heads(clause: Clause, sentence: str, sentence_start: int) -> bool:
    for role in clause.roles:
        if role.name not in ("agent", "patient", "recipient") or not isinstance(role.term, str):
            continue
        if role.term != role.span.text:
            return False
        if role.term.endswith("の"):
            return False
        end = role.span.end - sentence_start
        if end < 0 or end > len(sentence):
            return False
        tail = sentence[end:]
        if tail.startswith(_HONORIFICS):
            return False
        if tail and unicodedata.name(tail[0], "").startswith(
                ("CJK UNIFIED IDEOGRAPH", "CJK COMPATIBILITY IDEOGRAPH")):
            return False
    return True


def reads(ctx: ConstructionContext) -> Reading | None:
    if len(ctx.tokens) > ctx.budget.max_tokens or len(ctx.clauses) > ctx.budget.max_clauses:
        return None
    parts = _relation_spans(ctx.sentence_text)
    if parts is None:
        return None
    cause_start, cause_end, marker, marker_text, effect_start, effect_end = parts
    sentence_start = ctx.sentence_span.start
    marker_start = sentence_start + marker
    marker_end = marker_start + len(marker_text)
    effect_abs_start = sentence_start + effect_start
    native: list[Clause] = []
    for clause in ctx.clauses:
        pred = clause.predicate_span
        if (pred.source == ctx.sentence_span.source
                and pred.start >= sentence_start and pred.end <= ctx.sentence_span.end
                and clause.rule == "frame"):
            native.append(clause)
    if not native:
        return None
    left = [c for c in native if c.predicate_span.end <= marker_start]
    right = [c for c in native if c.predicate_span.start >= marker_end]
    if len(right) != 1 or len(left) + len(right) != len(native):
        return None
    if marker_text == "から" and not left:
        return None

    source = ctx.sentence_span.source
    sentence_span = ctx.sentence_span
    cause_span = Span(source, sentence_start + cause_start, sentence_start + cause_end,
                      ctx.sentence_text[cause_start:cause_end])
    effect_span = Span(source, sentence_start + effect_start, sentence_start + effect_end,
                       ctx.sentence_text[effect_start:effect_end])
    retyped: list[Clause] = []
    for clause in native:
        is_cause = clause in left
        if is_cause:
            continue
        body = cause_span if is_cause else effect_span
        if (not _stable_role_heads(clause, ctx.sentence_text, sentence_start)
                or not _local_frame_license(clause, body)):
            continue
        retyped.append(replace(clause, id="gold_reason:scope:" + clause.id,
                               body_span=sentence_span, rule="gold_reason", unsupported=()))
    if not any(clause.predicate_span.start >= effect_span.start for clause in retyped):
        return None

    marker_span = Span(source, marker_start, marker_end, marker_text)
    digest = sha256((source + ":" + str(sentence_start) + ":" + ctx.sentence_text).encode(
        "utf-8")).hexdigest()[:16]
    relation = Clause(
        id="gold_reason:relation:" + digest,
        event=Variable("reason_" + digest, "event"),
        predicate="cause",
        predicate_span=marker_span,
        roles=(Role("cause", cause_span.text, cause_span, "literal"),
               Role("effect", effect_span.text, effect_span, "literal")),
        span=sentence_span,
        body_span=sentence_span,
        rule="gold_reason",
    )
    return Reading(tuple(retyped) + (relation,), (sentence_span,))


def licenses(clause: Clause, source: str) -> bool:
    if clause.rule != "gold_reason":
        return False
    sentence_span = clause.span
    if (sentence_span.start < 0 or sentence_span.end > len(source)
            or sentence_span.end <= sentence_span.start
            or source[sentence_span.start:sentence_span.end] != sentence_span.text):
        return False
    parts = _relation_spans(sentence_span.text)
    if parts is None:
        return False
    cause_start, cause_end, marker, marker_text, effect_start, effect_end = parts
    expected_marker = Span(sentence_span.source, sentence_span.start + marker,
                           sentence_span.start + marker + len(marker_text), marker_text)
    if clause.predicate == "cause":
        if (clause.polarity != "+" or clause.modality != "assert"
                or clause.body_span != sentence_span or clause.predicate_span != expected_marker
                or len(clause.roles) != 2 or clause.event.sort != "event"):
            return False
        expected_roles = (
            ("cause", sentence_span.text[cause_start:cause_end], cause_start, cause_end),
            ("effect", sentence_span.text[effect_start:effect_end], effect_start, effect_end),
        )
        for role, expected in zip(clause.roles, expected_roles):
            name, value, start, end = expected
            expected_span = Span(sentence_span.source, sentence_span.start + start,
                                 sentence_span.start + end, value)
            if (role.name != name or role.term != value or role.span != expected_span
                    or role.rule != "literal"):
                return False
        return True

    body = _local_body(clause, sentence_span.text)
    return (body is not None and clause.body_span == sentence_span
            and clause.event.sort == "event"
            and _stable_role_heads(clause, sentence_span.text, sentence_span.start)
            and clause.predicate_span.start >= body.start
            and clause.predicate_span.end <= body.end
            and all(body.start <= role.span.start and role.span.end <= body.end
                    for role in clause.roles)
            and _local_frame_license(clause, body))


register(Construction(name="gold_reason", priority=46, reads=reads,
                      licenses=licenses, refines=("connective_rel",)))
