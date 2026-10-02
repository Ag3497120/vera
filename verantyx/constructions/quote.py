"""Source-bounded quotation and naming/meaning frames."""
from __future__ import annotations

from ..semantic_ir import Clause, Role, Span, Variable
from . import Construction, ConstructionContext, Reading, register


_QUOTES = (("「", "」"), ("『", "』"))
_NAMING_AFTER = ("と呼ばれる", "と称する", "とも言う", "という")
_MEANING_AFTER = "を意味する"
_PREFIX_NAME = "という"
_TERMINAL = "。！？!?"


def _span(ctx: ConstructionContext, start: int, end: int) -> Span:
    return Span(ctx.sentence_span.source, ctx.sentence_span.start + start,
                ctx.sentence_span.start + end, ctx.sentence_text[start:end])


def _quote_pairs(text: str):
    """Return only one-level, properly paired Japanese quote spans."""
    pairs = []
    opening = None
    for i, char in enumerate(text):
        if opening is None:
            if char in ("」", "』"):
                return None
            for left, right in _QUOTES:
                if char == left:
                    opening = (i, left, right)
                    break
        elif char in ("「", "『"):
            return None
        elif char == opening[2]:
            pairs.append((opening[0], i + 1, i, opening[1], char))
            opening = None
    if opening is not None:
        return None
    return pairs


def _subject(text: str, anchor: int):
    prefix = text[:anchor]
    import re
    match = re.search(r"(?P<subject>.+)(?P<topic>とは|は|が)[、,，\s]*\Z", prefix)
    if match:
        start, end = match.span("subject")
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        return (start, end, match.group("topic")) if start < end else None
    return None


def _marker(text: str, qend: int, qstart: int):
    after = [(_MEANING_AFTER, "meaning", "meaning")]
    after.extend((phrase, "identity", "name") for phrase in _NAMING_AFTER)
    matches = [(qend, phrase, pred, role) for phrase, pred, role in after
               if text.startswith(phrase, qend)]
    if text[:qstart].endswith(_PREFIX_NAME):
        matches.append((qstart - len(_PREFIX_NAME), _PREFIX_NAME, "identity", "name"))
    return matches[0] if len(matches) == 1 else None


def _strict_relation(ctx: ConstructionContext, pair):
    text = ctx.sentence_text
    qstart, qend, qclose, _, _ = pair
    marker = _marker(text, qend, qstart)
    if marker is None:
        return None
    marker_start, marker_text, predicate, value_role = marker
    subject = _subject(text, marker_start if marker_start < qstart else qstart)
    if subject is None and marker_text == _PREFIX_NAME:
        raw = text[:marker_start]
        if raw and not any(ch in raw for ch in "、,。！？\nはが"):
            left = len(raw) - len(raw.lstrip())
            right = len(raw.rstrip())
            if left < right:
                subject = (left, right, "")
    if subject is None:
        return None
    sstart, send, topic = subject
    before = text[:sstart]
    between = text[send:qstart]
    after = text[marker_start + len(marker_text):]
    terminal = after in ("", "。", "！", "？", "!", "?")
    if before.strip() or not terminal:
        return None
    if marker_start < qstart:
        if predicate != "identity" or between != _PREFIX_NAME:
            return None
    elif between not in ("は", "が", "とは", "は、", "が、", "とは、", "は,", "が,", "とは,"):
        return None
    value_start, value_end = qstart + 1, qclose
    if value_start >= value_end:
        return None
    roles = (
        Role("entity", text[sstart:send], _span(ctx, sstart, send), "literal"),
        Role("quotation" if value_role == "name" else "meaning",
             text[value_start:value_end], _span(ctx, value_start, value_end), "literal"),
    )
    return Clause(
        id=f"quote:{ctx.document_id}:{ctx.sentence_span.start}",
        event=Variable(f"e_quote_{ctx.sentence_span.start}", "event"),
        predicate=predicate,
        predicate_span=_span(ctx, marker_start, marker_start + len(marker_text)),
        roles=roles,
        span=ctx.sentence_span,
        body_span=ctx.sentence_span,
        polarity="+",
        modality="assert",
        rule="quote",
        sovereign="document",
        family="document",
        unsupported=(),
    )


def reads(ctx: ConstructionContext) -> Reading | None:
    text = ctx.sentence_text
    if (not text or len(ctx.tokens) > ctx.budget.max_tokens
            or len(text) > ctx.budget.max_steps):
        return None
    pairs = _quote_pairs(text)
    if pairs is None or not pairs or len(pairs) > ctx.budget.max_clauses:
        return None
    if ":" in text or "：" in text:
        return None
    recent = ctx.clauses[-ctx.budget.max_clauses:]
    for existing in recent:
        if (existing.span.source == ctx.sentence_span.source
                and existing.span.start < ctx.sentence_span.end
                and existing.span.end > ctx.sentence_span.start):
            if (existing.conditions or existing.condition_spans
                    or existing.exceptions or existing.exception_spans
                    or existing.rule not in ("frame", "quote")
                    or not existing.unsupported):
                return None
    if len(pairs) == 1:
        relation = _strict_relation(ctx, pairs[0])
        if relation is not None:
            return Reading((relation,), (ctx.sentence_span,))
    clauses = []
    for index, (qstart, qend, qclose, _, _) in enumerate(pairs):
        if qclose <= qstart + 1:
            continue
        value = _span(ctx, qstart + 1, qclose)
        outer = _span(ctx, qstart, qend)
        clauses.append(Clause(
            id=f"quote:{ctx.document_id}:{ctx.sentence_span.start}:{index}",
            event=Variable(f"e_quote_{ctx.sentence_span.start}_{index}", "event"),
            predicate="quotation",
            predicate_span=outer,
            roles=(Role("quotation", value.text, value, "literal"),),
            span=ctx.sentence_span,
            body_span=ctx.sentence_span,
            polarity="+",
            modality="quote",
            rule="quote",
            sovereign="document",
            family="document",
            unsupported=(),
        ))
    return Reading(tuple(clauses), (ctx.sentence_span,)) if clauses else None


def _source_slice(span: Span, source: str) -> bool:
    return (span.source and type(span.start) is int and type(span.end) is int
            and 0 <= span.start < span.end <= len(source)
            and source[span.start:span.end] == span.text)


def licenses(clause: Clause, source: str) -> bool:
    """Reparse exact source positions without relying on the construction reader."""
    if (clause.rule != "quote" or clause.unsupported or clause.polarity != "+"
            or clause.conditions or clause.exceptions
            or clause.exception_of or clause.time or not _source_slice(clause.span, source)
            or clause.span.text != source[clause.span.start:clause.span.end]):
        return False
    if (any(role.rule != "literal" or not _source_slice(role.span, source)
            or role.term != role.span.text for role in clause.roles)
            or not isinstance(clause.event, Variable) or clause.event.sort != "event"
            or not _source_slice(clause.predicate_span, source)):
        return False
    sentence = clause.span.text
    pred = clause.predicate_span
    if len(clause.roles) == 1 and clause.predicate == "quotation":
        role = clause.roles[0]
        if role.name != "quotation" or clause.modality != "quote":
            return False
        qstart = role.span.start - clause.span.start - 1
        qend = role.span.end - clause.span.start + 1
        pstart, pend = pred.start - clause.span.start, pred.end - clause.span.start
        if (qstart < 0 or qend > len(sentence) or pstart != qstart or pend != qend
                or sentence[qstart:pstart + 1] not in ("「", "『")
                or sentence[pend - 1:qend] not in ("」", "』")):
            return False
        pairs = _quote_pairs(sentence)
        return (pairs is not None
                and (qstart, qend, qend - 1, sentence[qstart], sentence[qend - 1]) in pairs
                and sentence[qstart + 1:pend - 1] == role.term
                and (sentence[qstart], sentence[pend - 1]) in _QUOTES)
    if (len(clause.roles) != 2 or clause.roles[0].name != "entity"
            or clause.roles[1].name not in ("quotation", "meaning")
            or clause.modality != "assert"):
        return False
    subject, argument = clause.roles
    qstart = argument.span.start - clause.span.start - 1
    qend = argument.span.end - clause.span.start + 1
    pstart, pend = pred.start - clause.span.start, pred.end - clause.span.start
    if (qstart < 0 or qend > len(sentence)
            or (sentence[qstart], sentence[qend - 1]) not in _QUOTES
            or sentence[qstart + 1:qend - 1] != argument.term
            or subject.span.start < clause.span.start or subject.span.end > argument.span.start
            or sentence[pstart:pend] != pred.text):
        return False
    pairs = _quote_pairs(sentence)
    if (pairs is None or len(pairs) != 1
            or (qstart, qend, qend - 1, sentence[qstart], sentence[qend - 1]) not in pairs):
        return False
    prefix = sentence[:subject.span.start - clause.span.start]
    between = sentence[subject.span.end - clause.span.start:qstart]
    suffix = sentence[qend:]
    if prefix.strip() or suffix not in ("", "。", "！", "？", "!", "?"):
        return False
    if clause.predicate == "meaning":
        return (argument.name == "meaning" and pred.text == _MEANING_AFTER
                and pstart == qend and between in ("は", "が", "とは", "は、", "が、", "とは、", "は,", "が,"))
    if clause.predicate == "identity" and argument.name == "quotation":
        if pred.text in _NAMING_AFTER:
            return pstart == qend and between in ("は", "が", "とは", "は、", "が、", "とは、", "は,", "が,", "とは,")
        if pred.text == _PREFIX_NAME:
            return pend == qstart and between == _PREFIX_NAME
    return False


register(Construction(name="quote", priority=0, reads=reads, licenses=licenses,
                      refines=("frame", "copula", "identity", "measure")))
