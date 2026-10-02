"""Source-bounded parenthetical glosses attached to identity subjects."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import re
import unicodedata

from ..semantic_ir import Clause, Span
from . import Construction, ConstructionContext, Reading, TypedNote, register


NAME = "paren_gloss"
_OPEN = {"（": "）", "(": ")"}
_CLOSE = frozenset(_OPEN.values())
_UNSUPPORTED_PAREN = "unsupported source quantifier/exception/time"


def _gloss_parts(text: str) -> tuple[tuple[int, int, str], ...] | None:
    """Return top-level balanced parenthetical spans in a subject literal."""
    stack: list[tuple[str, int]] = []
    parts: list[tuple[int, int, str]] = []
    begin = -1
    for i, char in enumerate(text):
        if char in _OPEN:
            if not stack:
                begin = i
            stack.append((_OPEN[char], i))
        elif char in _CLOSE:
            if not stack or stack[-1][0] != char:
                return None
            stack.pop()
            if not stack:
                parts.append((begin, i + 1, text[begin + 1:i]))
    if stack or not parts or not text[:parts[0][0]].strip() or text[parts[-1][1]:].strip():
        return None
    return tuple(parts)


def _gloss_type(content: str) -> str:
    stack: list[str] = []
    pieces: list[str] = []
    start = 0
    for pos, char in enumerate(content):
        if char in _OPEN:
            stack.append(_OPEN[char])
        elif char in _CLOSE and stack and stack[-1] == char:
            stack.pop()
        elif char in "、，," and not stack:
            pieces.append(content[start:pos])
            start = pos + 1
    pieces.append(content[start:])
    types: list[str] = []
    for piece in pieces:
        kind = _single_gloss_type(piece)
        if kind not in types:
            types.append(kind)
    return "+".join(types)


def _single_gloss_type(content: str) -> str:
    value = content.strip()
    if any(ch.isdigit() for ch in value) and ("年" in value or ("月" in value and "日" in value)):
        return "dates"
    if (any("LATIN" in unicodedata.name(ch, "") for ch in value)
            and not any("HIRAGANA" in unicodedata.name(ch, "") or
                        "KATAKANA" in unicodedata.name(ch, "") for ch in value)):
        return "foreign_name"
    if (re.fullmatch(r"[\u3040-\u30ffー・･\s、，,]*", value)
            and any("HIRAGANA" in unicodedata.name(ch, "") or
                    "KATAKANA" in unicodedata.name(ch, "") for ch in value)):
        return "reading"
    if re.match(r"^(?:別名|別称|通称|旧名|旧称|本名)\s*[:：]?", value):
        return "alias"
    return "note"


def _native_identity(clause: Clause, source_span: Span, sentence: str) -> bool:
    if (clause.rule != "copula" or clause.predicate != "identity" or
            clause.span != source_span or clause.span.text != sentence or
            clause.body_span != clause.span or clause.unsupported != (_UNSUPPORTED_PAREN,) or
            clause.polarity != "+" or clause.modality != "assert" or clause.time or
            clause.conditions or clause.condition_spans or clause.exceptions or
            clause.exception_spans or clause.exception_of or
            getattr(clause.event, "sort", None) != "event" or len(clause.roles) != 2):
        return False
    roles = {role.name: role for role in clause.roles}
    if set(roles) != {"entity", "value"}:
        return False
    entity, value = roles["entity"], roles["value"]
    if (entity.rule != "literal" or value.rule != "literal" or
            not isinstance(entity.term, str) or not isinstance(value.term, str) or
            entity.term != entity.span.text or value.term != value.span.text or
            entity.span.source != clause.span.source or value.span.source != clause.span.source or
            entity.span.start != clause.span.start or entity.span.end > value.span.start or
            clause.predicate_span != value.span or "（" not in entity.span.text and "(" not in entity.span.text or
            any(char in value.span.text for char in "（）()")):
        return False
    if not _gloss_parts(entity.span.text):
        return False
    between = sentence[entity.span.end - clause.span.start:value.span.start - clause.span.start]
    if not re.fullmatch(r"\s*(?:とは|は)\s*", between):
        return False
    ending = sentence[value.span.end - clause.span.start:]
    return bool(re.fullmatch(r"(?:である)?(?:。|．|\.|!|！|\?|？)\s*", ending))


def reads(ctx: ConstructionContext) -> Reading | None:
    """Repackage one unsupported literal identity and preserve its asides."""
    if (len(ctx.tokens) > ctx.budget.max_tokens or
            len(ctx.sentence_text) + 3 * len(ctx.tokens) > ctx.budget.max_steps):
        return None
    # Native clauses for this sentence are appended last; inspect only the
    # bounded tail because the supplied history may span many documents.
    if ctx.budget.max_clauses <= 0:
        return None
    window = ctx.clauses[-ctx.budget.max_clauses:]
    local = tuple(c for c in window if c.span == ctx.sentence_span)
    if len(local) != 1:
        return None
    clause = local[0]
    if not _native_identity(clause, ctx.sentence_span, ctx.sentence_text):
        return None
    entity = next(role for role in clause.roles if role.name == "entity")
    parts = _gloss_parts(entity.span.text)
    if parts is None:
        return None
    notes = tuple(
        TypedNote("gloss", Span(entity.span.source,
                                 entity.span.start + start,
                                 entity.span.start + end,
                                 entity.span.text[start:end]),
                  "entity:" + _gloss_type(content) + ":" + content)
        for start, end, content in parts
    )
    if len(notes) + 2 + len(clause.roles) > ctx.budget.max_steps:
        return None
    digest = hashlib.sha256((clause.id + ":" + NAME).encode("utf-8")).hexdigest()[:24]
    updated = replace(clause, id=digest,
                      event=replace(clause.event, name="event_" + digest),
                      rule=NAME, unsupported=())
    return Reading((updated,), (clause.span,), notes)


def _licenses_source(clause: Clause, source: str) -> bool:
    """Independently check the exact identity grammar and its attached aside."""
    if (clause.rule != NAME or clause.predicate != "identity" or
            clause.polarity != "+" or clause.modality != "assert" or clause.time or
            clause.conditions or clause.condition_spans or clause.exceptions or
            clause.exception_spans or clause.exception_of or clause.unsupported or
            clause.body_span != clause.span or getattr(clause.event, "sort", None) != "event" or
            len(clause.roles) != 2):
        return False
    if (not isinstance(source, str) or clause.span.start < 0 or clause.span.end > len(source) or
            clause.span.start >= clause.span.end or
            source[clause.span.start:clause.span.end] != clause.span.text):
        return False
    by_name = {r.name: r for r in clause.roles}
    if set(by_name) != {"entity", "value"}:
        return False
    subject, description = by_name["entity"], by_name["value"]
    for role in (subject, description):
        if (role.rule != "literal" or not isinstance(role.term, str) or
                role.term != role.span.text or role.span.source != clause.span.source or
                role.span.start < clause.span.start or role.span.end > clause.span.end or
                source[role.span.start:role.span.end] != role.span.text):
            return False
    if (subject.span.start != clause.span.start or subject.span.end > description.span.start or
            clause.predicate_span != description.span or
            "（" not in subject.span.text and "(" not in subject.span.text or
            any(c in description.span.text for c in "（）()")):
        return False

    # This scan is deliberately separate from the reader's parenthetical splitter.
    stack: list[str] = []
    outer: list[tuple[int, int]] = []
    mark = -1
    for pos, char in enumerate(subject.span.text):
        if char == "（" or char == "(":
            if not stack:
                mark = pos
            stack.append("）" if char == "（" else ")")
        elif char == "）" or char == ")":
            if not stack or stack.pop() != char:
                return False
            if not stack:
                outer.append((mark, pos + 1))
    if (stack or not outer or not subject.span.text[:outer[0][0]].strip() or
            subject.span.text[outer[-1][1]:].strip()):
        return False

    left = subject.span.end
    right = description.span.start
    seam = source[left:right]
    if not re.fullmatch(r"\s*(?:とは|は)\s*", seam):
        return False
    if description.span.end < clause.span.start:
        return False
    tail = source[description.span.end:clause.span.end]
    if not re.fullmatch(r"(?:である)?(?:。|．|\.|!|！|\?|？)\s*", tail):
        return False
    # The subject, copular marker, description, and terminal mark exhaust the span.
    return (source[clause.span.start:subject.span.end] == subject.span.text and
            source[description.span.start:description.span.end] == description.span.text and
            subject.span.end <= description.span.start)


register(Construction(name=NAME, priority=30, reads=reads, licenses=_licenses_source))
