"""A narrow colloquial double-negative extension composed over negation."""
from __future__ import annotations

import hashlib
from dataclasses import replace

from ..semantic_ir import Clause, Span
from . import Construction, ConstructionContext, Reading, register
from . import negation as _negation


_FORM = "なくない"
_INSERT = "なくはない"
_CANONICAL_DOUBLE = (
    "なくはない", "なくもない", "ないわけではない", "ないわけじゃない",
    "ないことはない", "ないこともない",
)
_PAST_TO_PRESENT = (
    ("ないわけじゃなかった", "ないわけじゃない"),
    ("ないことはなかった", "ないことはない"),
    ("ないこともなかった", "ないこともない"),
    ("なくはなかった", "なくはない"),
    ("なくもなかった", "なくもない"),
)


def _source_form(text: str):
    """Locate a terminal double-negative form before sentence punctuation."""
    end = len(text.rstrip(_negation._PUNCT))
    core = text[:end]
    if core.endswith(_FORM):
        start = end - len(_FORM)
        if start > 0 and core[start:start + 2] == "なく":
            return "insert", (start, end, _INSERT), "nonpast"
    for past, present in _PAST_TO_PRESENT:
        if core.endswith(past):
            start = end - len(past)
            return "past", (start, end, present), "past"
    match = _negation._DOUBLE.search(core)
    if match and match.end() == end:
        return "direct", None, ""
    return None


def _original_point(point: int, sentence_start: int, edit, *, right: bool) -> int:
    if edit is None:
        return point
    start, end, replacement = edit
    local = point - sentence_start
    new_end = start + len(replacement)
    delta = end - start - len(replacement)
    if local <= start:
        return point
    if local >= new_end:
        return point + delta
    return sentence_start + start + (end - start if right else 0)


def _original_span(span: Span, sentence_span: Span, sentence: str,
                   edit) -> Span:
    start = _original_point(span.start, sentence_span.start, edit, right=False)
    end = _original_point(span.end, sentence_span.start, edit, right=True)
    left, right = start - sentence_span.start, end - sentence_span.start
    return Span(span.source, start, end, sentence[left:right])


def reads(ctx: ConstructionContext) -> Reading | None:
    if (len(ctx.tokens) >= ctx.budget.max_tokens or len(ctx.clauses) >= ctx.budget.max_clauses
            or len(ctx.sentence_text) >= 4096):
        return None
    suffix = _source_form(ctx.sentence_text)
    if suffix is None:
        return None

    # Normalize only the terminal form, then reuse negation's event frame,
    # exact role, and complete source-coverage checks.
    _, edit, time_override = suffix
    if edit is None:
        normalized = ctx.sentence_text
        normalized_ctx = ctx
    else:
        edit_start, edit_end, replacement = edit
        normalized = (ctx.sentence_text[:edit_start] + replacement
                      + ctx.sentence_text[edit_end:])
        normalized_span = Span(ctx.sentence_span.source, ctx.sentence_span.start,
                               ctx.sentence_span.end + len(normalized) - len(ctx.sentence_text),
                               normalized)
        normalized_ctx = replace(ctx, sentence_text=normalized,
                                 sentence_span=normalized_span)
    body_start = _negation._body_start(normalized)
    parsed = _negation._event_reading(normalized_ctx, body_start,
                                      normalized[body_start:])
    if parsed is None:
        return None
    clause, notes, consumed = parsed
    roles = tuple(replace(role, span=_original_span(role.span, ctx.sentence_span,
                                                     ctx.sentence_text, edit))
                  for role in clause.roles)
    clause_span = _original_span(clause.span, ctx.sentence_span, ctx.sentence_text,
                                 edit)
    predicate_span = _original_span(clause.predicate_span, ctx.sentence_span,
                                    ctx.sentence_text, edit)
    body_span = (_original_span(clause.body_span, ctx.sentence_span,
                                ctx.sentence_text, edit)
                 if clause.body_span is not None else None)
    ident = hashlib.sha256(
        f"gold_double_neg:{ctx.document_id}:{ctx.sentence_span.start}:"
        f"{ctx.sentence_span.end}:{clause.predicate_span.start}".encode("utf-8")
    ).hexdigest()[:24]
    clause = replace(clause, id=ident, span=clause_span,
                     predicate_span=predicate_span, body_span=body_span,
                     roles=roles, rule="gold_double_neg", modality="assert",
                     time=time_override or clause.time)
    mapped_notes = tuple(replace(note, span=_original_span(note.span,
                                                          ctx.sentence_span,
                                                          ctx.sentence_text,
                                                          edit))
                         if note.span is not None else note for note in notes)
    mapped_consumed = (_original_span(consumed, ctx.sentence_span,
                                      ctx.sentence_text, edit),)
    return Reading((clause,), mapped_consumed, mapped_notes)


def licenses(clause: Clause, source: str) -> bool:
    """Verify the original form, then delegate the normalized grammar check."""
    if (clause.rule != "gold_double_neg" or clause.unsupported
            or not isinstance(source, str)
            or clause.span.end > len(source) or clause.span.start < 0
            or source[clause.span.start:clause.span.end] != clause.span.text
            or clause.body_span is None or clause.body_span.source != clause.span.source
            or clause.body_span.end != clause.span.end
            or clause.polarity != "+"
            or clause.modality != "assert"
            or clause.conditions or clause.exceptions
            or clause.condition_spans or clause.exception_spans or clause.exception_of):
        return False

    text = source[clause.span.start:clause.span.end]
    end = len(text.rstrip(_negation._PUNCT))
    core = text[:end]
    edit = None
    expected_time = "nonpast"
    if core.endswith("なくない"):
        form_start = end - len("なくない")
        if form_start <= 0 or core[form_start:form_start + 2] != "なく":
            return False
        edit = (form_start + 2, form_start + 2, "は")
    else:
        past = next(((form, present) for form, present in _PAST_TO_PRESENT
                     if core.endswith(form)), None)
        if past is not None:
            form, present = past
            edit = (end - len(form), end, present)
            expected_time = "past"
        elif not any(core.endswith(form) for form in _CANONICAL_DOUBLE):
            return False
    if clause.time != expected_time:
        return False
    normalized_source = source
    edit_absolute = None
    if edit is not None:
        local_start, local_end, replacement = edit
        edit_absolute = clause.span.start + local_start
        normalized_source = (source[:edit_absolute] + replacement
                             + source[clause.span.start + local_end:])

    def expanded_point(point: int, *, right: bool) -> int:
        if edit is None or edit_absolute is None:
            return point
        local_start, local_end, replacement = edit
        edit_end = clause.span.start + local_end
        new_end = edit_absolute + len(replacement)
        delta = len(replacement) - (local_end - local_start)
        if point <= edit_absolute:
            return point
        if point >= edit_end:
            return point + delta
        return edit_absolute + (len(replacement) if right else 0)

    def expanded(span: Span) -> Span:
        start = expanded_point(span.start, right=False)
        finish = expanded_point(span.end, right=True)
        return Span(span.source, start, finish, normalized_source[start:finish])

    normalized_roles = tuple(replace(role, span=expanded(role.span))
                             for role in clause.roles)
    normalized_clause = replace(
        clause, rule="negation", modality=_negation._AFFIRMATIVE_DOUBLE,
        time="nonpast", span=expanded(clause.span),
        predicate_span=expanded(clause.predicate_span),
        body_span=expanded(clause.body_span), roles=normalized_roles,
    )
    return _negation._licenses_event(normalized_clause, normalized_source)


register(Construction(name="gold_double_neg", priority=45, reads=reads,
                      licenses=licenses, refines=("negation",)))
