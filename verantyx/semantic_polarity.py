"""Source-bound polarity diagnostics for the semantic reader.

Observed negation can answer a closed predicate-polarity question only when
the semantic reader has independently licensed the same predicate and the
written negation attaches to that clause.  Antonym hits stay within the old
closed vocabulary and are usable only when one supported property clause
licenses the exact entity and value.  Neither path creates semantic clauses.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Tuple

from . import polarity as _polarity
from .semantic_reader import document_view

ANSWER = "ANSWER"
UNKNOWN_NO_EVIDENCE = "UNKNOWN_NO_EVIDENCE"
UNKNOWN_UNSUPPORTED_EVIDENCE = "UNKNOWN_UNSUPPORTED_EVIDENCE"
UNKNOWN_AMBIGUOUS = "UNKNOWN_AMBIGUOUS"
POLARITY_UNDECIDED = _polarity.POLARITY_UNDECIDED

ObservedNegation = _polarity.ObservedNegation
InferredNegation = _polarity.InferredNegation


@dataclass(frozen=True)
class SourceSpan:
    source: str
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class ObservedWitness:
    observation: ObservedNegation
    span: SourceSpan


@dataclass(frozen=True)
class PolarityEvidence:
    clause_id: str
    predicate: str
    polarity: str
    clause_span: SourceSpan
    predicate_span: SourceSpan
    observation: Optional[ObservedWitness] = None
    aspect: Optional[str] = None
    value: Optional[str] = None


@dataclass(frozen=True)
class PolarityRefusal:
    code: str
    reason: str
    spans: Tuple[SourceSpan, ...] = ()


@dataclass(frozen=True)
class PolarityAnswer:
    status: str
    value: Optional[bool] = None
    evidence: Tuple[PolarityEvidence, ...] = ()
    inferred: Optional[InferredNegation] = None
    refusal: Optional[PolarityRefusal] = None


def _answer(status: str, *, value: Optional[bool] = None,
            evidence: Tuple[PolarityEvidence, ...] = (),
            inferred: Optional[InferredNegation] = None,
            reason: str = "", spans: Tuple[SourceSpan, ...] = ()) -> PolarityAnswer:
    refusal = PolarityRefusal(status, reason, spans) if status != ANSWER else None
    return PolarityAnswer(status, value, evidence, inferred, refusal)


def _source_span(span: Any, sources: Mapping[str, str]) -> Optional[SourceSpan]:
    source = getattr(span, "source", None)
    start = getattr(span, "start", None)
    end = getattr(span, "end", None)
    text = getattr(span, "text", None)
    if (not isinstance(source, str) or source not in sources
            or not isinstance(start, int) or not isinstance(end, int)
            or start < 0 or end < start or end > len(sources[source])
            or not isinstance(text, str) or sources[source][start:end] != text):
        return None
    return SourceSpan(source, start, end, text)


def _view(documents: Mapping[str, str], family: str):
    sources = dict(documents)
    return sources, document_view(sources, family=family)


def _is_supported(clause: Any, sources: Mapping[str, str]):
    clause_span = _source_span(getattr(clause, "span", None), sources)
    predicate_span = _source_span(getattr(clause, "predicate_span", None), sources)
    body = getattr(clause, "body_span", getattr(clause, "body", None))
    body_span = _source_span(body, sources)
    if not clause_span or not predicate_span or not body_span:
        return None
    if not (clause_span.start <= body_span.start <= body_span.end <= clause_span.end
            and clause_span.start <= predicate_span.start <= predicate_span.end <= clause_span.end):
        return None
    if getattr(clause, "unsupported", ()):
        return None
    if getattr(clause, "modality", "assert") != "assert":
        return None
    if getattr(clause, "conditions", ()) or getattr(clause, "exceptions", ()):
        return None
    for role in getattr(clause, "roles", ()):
        if _source_span(getattr(role, "span", None), sources) is None:
            return None
    return clause_span, predicate_span, body_span


def _sentence_spans(view: Any, sources: Mapping[str, str]):
    found = {}
    for clause in view.clauses:
        span = _source_span(getattr(clause, "span", None), sources)
        if span:
            found[(span.source, span.start, span.end)] = span
    for unread in view.unread:
        span = _source_span(getattr(unread, "span", None), sources)
        if span:
            found[(span.source, span.start, span.end)] = span
    return tuple(found.values())


def _undecided_spans(view: Any, sources: Mapping[str, str]):
    spans = []
    for span in _sentence_spans(view, sources):
        reading = _polarity.observe_negation(span.text)
        if reading.verdict == POLARITY_UNDECIDED:
            spans.append(span)
    return tuple(spans)


def _witnesses(clause: Any, clause_span: SourceSpan,
               predicate_span: SourceSpan, sentence_reading: Any,
               sources: Mapping[str, str], lemma: str):
    matches = []
    for observation in sentence_reading.observed:
        if observation.lemma != lemma:
            continue
        start = clause_span.start + observation.span[0]
        end = clause_span.start + observation.span[1]
        if (observation.span[0] < 0 or observation.span[1] < observation.span[0]
                or end > clause_span.end or start < predicate_span.end
                or sources[clause_span.source][start:end] != observation.surface):
            continue
        matches.append(ObservedWitness(
            observation, SourceSpan(clause_span.source, start, end,
                                    sources[clause_span.source][start:end])))
    return tuple(matches)


def answer_negation(documents: Mapping[str, str], lemma: str, *,
                    family: str = "document") -> PolarityAnswer:
    """Answer whether one explicitly parsed predicate is negated.

    A positive answer needs both semantic clause polarity and a matching
    ``ObservedNegation``. A negative answer needs one explicit positive
    clause. No matching clause yields UNKNOWN with an ``InferredNegation``
    testimony type and no Boolean value; inferred absence is never stored.
    """
    if not isinstance(lemma, str) or not lemma.strip() or lemma != lemma.strip():
        return _answer(UNKNOWN_UNSUPPORTED_EVIDENCE,
                       reason="predicate lemma must be one exact non-empty string")
    sources, view = _view(documents, family)
    undecided = _undecided_spans(view, sources)
    if undecided:
        return _answer(POLARITY_UNDECIDED,
                       reason="written polarity has an unfoldable scope or modality",
                       spans=undecided)

    candidates = []
    unsupported = []
    for clause in view.clauses:
        if getattr(clause, "predicate", None) != lemma:
            continue
        checked = _is_supported(clause, sources)
        if checked is None:
            raw_span = _source_span(getattr(clause, "span", None), sources)
            if raw_span:
                unsupported.append(raw_span)
            continue
        clause_span, predicate_span, _body_span = checked
        reading = _polarity.observe_negation(clause_span.text)
        matches = _witnesses(clause, clause_span, predicate_span,
                             reading, sources, lemma)
        clause_polarity = getattr(clause, "polarity", "+")
        if clause_polarity == "-":
            if len(matches) != 1:
                unsupported.append(clause_span)
                continue
            evidence = PolarityEvidence(
                str(getattr(clause, "id", "")), lemma, "-", clause_span,
                predicate_span, matches[0])
            candidates.append((True, evidence))
        elif clause_polarity == "+":
            # An observed negation of this lemma elsewhere in the same
            # sentence is embedded until the semantic reader attaches it.
            if matches:
                unsupported.append(clause_span)
                continue
            evidence = PolarityEvidence(
                str(getattr(clause, "id", "")), lemma, "+", clause_span,
                predicate_span)
            candidates.append((False, evidence))
        else:
            unsupported.append(clause_span)

    if unsupported:
        return _answer(UNKNOWN_UNSUPPORTED_EVIDENCE,
                       reason="polarity could not be attached to one licensed clause",
                       spans=tuple(unsupported))
    if not candidates:
        return _answer(UNKNOWN_NO_EVIDENCE,
                       inferred=_polarity.inferred_from_absence(lemma),
                       reason="no explicit clause for this predicate")
    if len(candidates) != 1:
        return _answer(UNKNOWN_AMBIGUOUS,
                       reason="more than one source clause matches this predicate",
                       spans=tuple(row[1].clause_span for row in candidates))
    value, evidence = candidates[0]
    return _answer(ANSWER, value=value, evidence=(evidence,))


def _role_with_source_text(clause: Any, name: str, expected: str,
                           sources: Mapping[str, str]):
    matches = []
    for role in getattr(clause, "roles", ()):
        if getattr(role, "name", None) != name:
            continue
        span = _source_span(getattr(role, "span", None), sources)
        if span and span.text == expected:
            matches.append((role, span))
    return matches


def answer_antonym(documents: Mapping[str, str], entity: str, term: str, *,
                   family: str = "document") -> PolarityAnswer:
    """Answer one closed Japanese antonym query from one licensed clause.

    The old detector supplies only an aspect candidate. The semantic reader
    must independently license a single property clause, exact entity role,
    and exact value span before that candidate can answer. Other cases abstain.
    """
    if (not isinstance(entity, str) or not entity.strip()
            or entity != entity.strip() or not isinstance(term, str)
            or not term.strip() or term != term.strip()):
        return _answer(UNKNOWN_UNSUPPORTED_EVIDENCE,
                       reason="entity and antonym term must be exact non-empty strings")
    query_hits = _polarity.detect_ja(term)
    if len(query_hits) != 1:
        return _answer(POLARITY_UNDECIDED,
                       reason="query term is not one closed Japanese aspect value")
    query_aspect, _query_value, query_polarity = query_hits[0]
    sources, view = _view(documents, family)
    undecided = _undecided_spans(view, sources)
    if undecided:
        return _answer(POLARITY_UNDECIDED,
                       reason="source contains unfoldable negation scope",
                       spans=undecided)

    candidates = []
    unsupported = []
    for clause in view.clauses:
        checked = _is_supported(clause, sources)
        if checked is None:
            continue
        clause_span, predicate_span, _body_span = checked
        sentence_clauses = [c for c in view.clauses
                            if getattr(c, "span", None) is not None
                            and getattr(c.span, "source", None) == clause_span.source
                            and getattr(c.span, "start", None) == clause_span.start
                            and getattr(c.span, "end", None) == clause_span.end]
        if len(sentence_clauses) != 1:
            continue
        if getattr(clause, "predicate", None) not in ("property", "identity"):
            continue
        if not _role_with_source_text(clause, "entity", entity, sources):
            continue
        hits = [hit for hit in _polarity.detect_ja(clause_span.text)
                if hit[0] == query_aspect]
        if len(hits) != 1:
            if len(hits) > 1:
                unsupported.append(clause_span)
            continue
        aspect, source_value, source_polarity = hits[0]
        surface = source_value[5:] if source_value.startswith("not_") else source_value
        occurrences = []
        at = clause_span.text.find(surface)
        while at >= 0:
            occurrences.append((at, at + len(surface)))
            at = clause_span.text.find(surface, at + 1)
        if len(occurrences) != 1:
            unsupported.append(clause_span)
            continue
        value_spans = [span for role_name in ("value", "attribute")
                       for _role, span in _role_with_source_text(
                           clause, role_name, surface, sources)]
        if len(value_spans) != 1:
            unsupported.append(clause_span)
            continue
        value_span = value_spans[0]
        expected_start = clause_span.start + occurrences[0][0]
        expected_end = clause_span.start + occurrences[0][1]
        if (value_span.start, value_span.end) != (expected_start, expected_end):
            unsupported.append(clause_span)
            continue
        value = source_polarity == query_polarity
        evidence = PolarityEvidence(
            str(getattr(clause, "id", "")), str(getattr(clause, "predicate", "")),
            getattr(clause, "polarity", "+"), clause_span, predicate_span,
            aspect=aspect, value=source_value)
        candidates.append((value, evidence))

    if unsupported:
        return _answer(UNKNOWN_UNSUPPORTED_EVIDENCE,
                       reason="aspect candidate lacks unique source and role alignment",
                       spans=tuple(unsupported))
    if not candidates:
        return _answer(UNKNOWN_NO_EVIDENCE,
                       reason="no source clause licenses this entity and aspect")
    if len(candidates) != 1:
        return _answer(UNKNOWN_AMBIGUOUS,
                       reason="multiple clauses match this entity and aspect",
                       spans=tuple(row[1].clause_span for row in candidates))
    value, evidence = candidates[0]
    return _answer(ANSWER, value=value, evidence=(evidence,))
