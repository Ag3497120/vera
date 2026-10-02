"""Provenance-carrying, multi-sentence semantic generation.

This adapter only assembles sentences accepted by ``semantic_realize``. It
does not add generated text to a source View, answer proof, or evidence set.
Harvested role-slot templates are loaded from the static realization table;
each instantiated surface is rechecked before it enters generated text.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable

from . import connective_render
from .semantic_realize import (
    MAX_CLAUSES,
    MAX_CHARS,
    Realized,
    RealizedGroup,
    Refused,
    Span,
    projection,
    realize_answer,
    realize_variants,
    summarize_entity,
    summary_entity_from_request,
    verify_sentence,
)


@dataclass(frozen=True)
class GeneratedSentence:
    """One independently checked sentence and its source lineage."""

    text: str
    clause_ids: tuple[str, ...]
    spans: tuple[Span, ...]
    style: str
    projection: tuple[Any, ...]
    checks: dict[str, Any]
    bucket: str = ""
    output_start: int = 0
    output_end: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "clause_ids": list(self.clause_ids),
            "spans": [_span_dict(span) for span in self.spans],
            "style": self.style,
            "projection": self.projection,
            "checks": self.checks,
            "bucket": self.bucket,
            "output_start": self.output_start,
            "output_end": self.output_end,
        }


@dataclass(frozen=True)
class GeneratedQuote:
    """Verbatim source text kept visibly separate from generated sentences."""

    text: str
    source_text: str
    clause_ids: tuple[str, ...]
    spans: tuple[Span, ...]
    output_start: int = 0
    output_end: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "source_text": self.source_text,
            "clause_ids": list(self.clause_ids),
            "spans": [_span_dict(span) for span in self.spans],
            "verbatim": True,
            "output_start": self.output_start,
            "output_end": self.output_end,
        }


@dataclass(frozen=True)
class ConnectiveLicense:
    connective: str
    license: str
    left_clause_ids: tuple[str, ...]
    right_clause_ids: tuple[str, ...]
    output_start: int = 0
    output_end: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "connective": self.connective,
            "license": self.license,
            "left_clause_ids": list(self.left_clause_ids),
            "right_clause_ids": list(self.right_clause_ids),
            "output_start": self.output_start,
            "output_end": self.output_end,
        }


@dataclass(frozen=True)
class GeneratedGroup:
    """A source-bound group, such as one entity in a side-by-side compare."""

    label: str
    sentence_indexes: tuple[int, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"label": self.label, "sentence_indexes": list(self.sentence_indexes)}


@dataclass(frozen=True)
class GeneratedText:
    """Constructed text. This type is never an answer or evidence object."""

    text: str
    sentences: tuple[GeneratedSentence, ...]
    quotes: tuple[GeneratedQuote, ...]
    connectives: tuple[ConnectiveLicense, ...]
    groups: tuple[GeneratedGroup, ...]
    request_kind: str
    style: str
    constructed: bool = True
    kind: str = "constructed"
    verdict: str = "CONSTRUCTED"

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "sentences": [sentence.as_dict() for sentence in self.sentences],
            "quotes": [quote.as_dict() for quote in self.quotes],
            "connectives": [license.as_dict() for license in self.connectives],
            "groups": [group.as_dict() for group in self.groups],
            "request_kind": self.request_kind,
            "style": self.style,
            "constructed": self.constructed,
            "kind": self.kind,
            "verdict": self.verdict,
        }


def _span_dict(span: Span) -> dict[str, Any]:
    return {"source": span.source, "start": span.start, "end": span.end, "text": span.text}


def _source_spans(clause: Any) -> tuple[Span, ...]:
    candidates = [getattr(clause, "span", None)]
    candidates.extend(getattr(role, "span", None) for role in getattr(clause, "roles", ()))
    candidates.append(getattr(clause, "predicate_span", None))
    found: dict[tuple[str, int, int, str], Span] = {}
    for span in candidates:
        if isinstance(span, Span):
            found[(span.source, span.start, span.end, span.text)] = span
    return tuple(found.values())


def _realized_sentences(value: Realized | RealizedGroup) -> tuple[Realized, ...]:
    return value.sentences if isinstance(value, RealizedGroup) else (value,)


def _ids_from_realization(value: Realized | RealizedGroup) -> tuple[str, ...]:
    return tuple(dict.fromkeys(cid for item in _realized_sentences(value) for cid in item.clause_ids))


def _licensed_source_ids(view: Any, clause_ids: Iterable[str]) -> list[Any] | Refused:
    clauses = {getattr(clause, "id", None): clause for clause in getattr(view, "clauses", ())}
    sources = getattr(view, "sources", None)
    selected = []
    for clause_id in dict.fromkeys(clause_ids):
        clause = clauses.get(clause_id)
        if clause is None:
            return Refused("INVALID_PROVENANCE", "generated clause is absent from the supplied View",
                            (str(clause_id),))
        spans = _source_spans(clause)
        if (not isinstance(sources, dict) or not spans
                or any(not span.valid(sources) for span in spans)):
            return Refused("INVALID_PROVENANCE", "source clause spans do not match the supplied View",
                            (str(clause_id),), spans)
        selected.append(clause)
    if not selected:
        return Refused("NOT_REALIZABLE", "no source clause was selected")
    if len(selected) > MAX_CLAUSES:
        return Refused("BUDGET", "generation exceeds the clause budget")
    return selected


def _topic_of(clause: Any, candidate: Realized) -> str:
    role_name = "agent" if getattr(clause, "rule", "") == "frame" else "entity"
    subject = next((role for role in getattr(clause, "roles", ())
                   if role.name == role_name), None)
    if subject is not None:
        for particle in ("は", "が"):
            if candidate.text.startswith(subject.span.text + particle):
                return particle
    return ""


_SURFACE_VARIANT_DATA: dict[str, Any] | None = None


def _surface_variant_data() -> dict[str, Any]:
    global _SURFACE_VARIANT_DATA
    if _SURFACE_VARIANT_DATA is None:
        path = Path(__file__).with_name("data") / "realize_variants.json"
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            loaded = {}
        _SURFACE_VARIANT_DATA = loaded if isinstance(loaded, dict) else {}
    return _SURFACE_VARIANT_DATA


def _variant_key(clause: Any, style: str) -> tuple[Any, ...]:
    return (
        f"{getattr(clause, 'rule', '')}:{getattr(clause, 'predicate', '')}",
        tuple(sorted(str(role.name) for role in getattr(clause, "roles", ()))),
        str(getattr(clause, "polarity", "")),
        str(getattr(clause, "time", "") or "none"),
        style,
    )


def _corpus_variants(clause: Any) -> list[Realized]:
    predicate_class, role_set, polarity, tense, _ = _variant_key(clause, "plain")
    roles = {str(role.name): role for role in getattr(clause, "roles", ())}
    expected = (predicate_class, role_set, polarity, tense)
    result: list[Realized] = []
    for item in _surface_variant_data().get("templates", ()):
        if not isinstance(item, dict):
            continue
        try:
            item_key = (
                str(item["predicate_class"]), tuple(sorted(str(x) for x in item["role_set"])),
                str(item["polarity"]), str(item["tense"]), str(item["register"]),
            )
            count = item["count"]
            template = item["template"]
        except (KeyError, TypeError):
            continue
        if item_key[:4] != expected or item_key[4] not in ("plain", "polite"):
            continue
        if type(count) is not int or count < 1 or not isinstance(template, str):
            continue
        slots = re.findall(r"\{([a-z_]+)\}", template)
        if not slots or sorted(slots) != sorted(roles):
            continue
        text = re.sub(r"\{([a-z_]+)\}", lambda match: roles[match.group(1)].span.text, template)
        if "{" in text or "}" in text:
            continue
        checks = verify_sentence(clause, text)
        if (not checks["roundtrip"]["passed"] or not checks["term_lineage"]["passed"]
                or len(text) > MAX_CHARS):
            continue
        result.append(Realized(
            text, getattr(clause, "id", ""), _source_spans(clause), item_key[4],
            "corpus-template", checks,
        ))
    return result


def _variant(clause: Any, style: str, topic_particle: str | None = None,
             variant_index: int = 0) -> Realized | Refused:
    failures: list[Refused] = []
    candidates: list[Realized] = []
    seen: set[str] = set()
    # Prefer a matching harvested template, then retain the inverse realizer's
    # closed surfaces as a deterministic fallback.
    for candidate in _corpus_variants(clause):
        if (candidate.style == style
                and (topic_particle is None or _topic_of(clause, candidate) == topic_particle)
                and candidate.text not in seen):
            candidates.append(candidate)
            seen.add(candidate.text)
    for candidate in realize_variants(clause):
        if isinstance(candidate, Refused):
            failures.append(candidate)
            continue
        if (candidate.style == style
                and (topic_particle is None or _topic_of(clause, candidate) == topic_particle)
                and candidate.text not in seen):
            candidates.append(candidate)
            seen.add(candidate.text)
    if 0 <= variant_index < len(candidates):
        return candidates[variant_index]
    if candidates:
        return Refused("ROLE_NOT_REALIZABLE", "requested surface variant is not licensed for this clause",
                       (getattr(clause, "id", ""),) if getattr(clause, "id", None) else (),
                       _source_spans(clause))
    return failures[0] if failures else Refused(
        "ROLE_NOT_REALIZABLE", "no verified surface variant matches the requested policy",
        (getattr(clause, "id", ""),) if getattr(clause, "id", None) else (),
        _source_spans(clause),
    )


def _sentences_for_ids(view: Any, clause_ids: Iterable[str], style: str,
                       bucket: str, topic_particle: str | None = None,
                       variant_index: int = 0) -> list[GeneratedSentence] | Refused:
    clauses = _licensed_source_ids(view, clause_ids)
    if isinstance(clauses, Refused):
        return clauses

    out: list[GeneratedSentence] = []
    # Deduplicate only after independently checking the chosen surface against
    # every source clause; equal typed projections alone are not lineage.
    for clause in clauses:
        candidate = _variant(clause, style, topic_particle, variant_index)
        if isinstance(candidate, Refused):
            return candidate
        checks = verify_sentence(clause, candidate.text)
        if not checks["roundtrip"]["passed"]:
            return Refused("ROUNDTRIP_MISMATCH", checks["roundtrip"]["detail"],
                           (clause.id,), _source_spans(clause), checks=checks)
        if not checks["term_lineage"]["passed"]:
            return Refused("TERM_LINEAGE_MISMATCH", checks["term_lineage"]["detail"],
                           (clause.id,), _source_spans(clause), checks=checks)
        current_projection = projection(clause)
        duplicate = next((i for i, item in enumerate(out)
                          if item.projection == current_projection
                          and item.text == candidate.text), None)
        source_spans = _source_spans(clause)
        if duplicate is not None:
            previous = out[duplicate]
            merged_spans = {(s.source, s.start, s.end, s.text): s for s in previous.spans}
            merged_spans.update({(s.source, s.start, s.end, s.text): s for s in source_spans})
            out[duplicate] = GeneratedSentence(
                previous.text,
                tuple(dict.fromkeys((*previous.clause_ids, clause.id))),
                tuple(merged_spans.values()),
                previous.style,
                previous.projection,
                previous.checks,
                bucket,
            )
        else:
            out.append(GeneratedSentence(
                candidate.text, candidate.clause_ids, source_spans,
                candidate.style, current_projection, checks, bucket,
            ))
    return out


def _summary_ids(view: Any, entity: str, limit: int, style: str) -> tuple[str, ...] | Refused:
    gated = summarize_entity(view, entity, limit=limit, style=style)
    if isinstance(gated, Refused):
        return gated
    return _ids_from_realization(gated)


def _span_from_unread(item: Any) -> Span | None:
    raw = item.get("span", item) if isinstance(item, dict) else getattr(item, "span", item)
    if isinstance(raw, Span):
        return raw
    if isinstance(raw, dict):
        try:
            span = Span(str(raw["source"]), int(raw["start"]), int(raw["end"]), str(raw["text"]))
        except (KeyError, TypeError, ValueError):
            return None
        return span if span.end > span.start and span.end - span.start == len(span.text) else None
    return None


def _unread_items(view: Any) -> tuple[GeneratedQuote, ...]:
    unread = getattr(view, "unread", ())
    if isinstance(unread, dict):
        raw_items = []
        for value in unread.values():
            raw_items.extend(value if isinstance(value, (list, tuple)) else (value,))
    else:
        raw_items = list(unread or ())
    sources = getattr(view, "sources", {})
    quotes: list[GeneratedQuote] = []
    seen = set()
    for item in raw_items:
        span = _span_from_unread(item)
        if span is None or not span.valid(sources):
            continue
        key = (span.source, span.start, span.end, span.text)
        if key in seen:
            continue
        seen.add(key)
        raw_id = item.get("clause_id") or item.get("id") if isinstance(item, dict) else getattr(item, "clause_id", None)
        clause_id = str(raw_id) if raw_id else f"unread:{span.source}:{span.start}:{span.end}"
        quotes.append(GeneratedQuote("「" + span.text + "」", span.text, (clause_id,), (span,)))
    return tuple(quotes)


def _assemble(view: Any, sentence_groups: list[tuple[str, list[GeneratedSentence]]],
              style: str, request_kind: str, *, quote_unread: bool = True) -> GeneratedText | Refused:
    sentences: list[GeneratedSentence] = []
    connectives: list[ConnectiveLicense] = []
    groups: list[GeneratedGroup] = []
    chunks: list[str] = []
    for label, group_sentences in sentence_groups:
        indexes = []
        for sentence in group_sentences:
            if not sentence.text or not sentence.clause_ids or not sentence.spans:
                return Refused("INVALID_PROVENANCE", "every generated sentence needs source ids and spans",
                               sentence.clause_ids, sentence.spans)
            if indexes:
                prior = group_sentences[len(indexes) - 1]
                # Legacy connective_render licenses enumeration inside one
                # bucket; it does not license transitions or opposition.
                connective_start = sum(len(chunk) for chunk in chunks)
                connective = connective_render.CONNECTIVE_SOSHITE
                chunks.append(connective)
                connectives.append(ConnectiveLicense(
                    connective,
                    connective_render.LICENSE_WITHIN_BUCKET,
                    prior.clause_ids,
                    sentence.clause_ids,
                    connective_start,
                    connective_start + len(connective),
                ))
            sentence_start = sum(len(chunk) for chunk in chunks)
            emitted_sentence = replace(
                sentence,
                output_start=sentence_start,
                output_end=sentence_start + len(sentence.text),
            )
            indexes.append(len(sentences))
            chunks.append(emitted_sentence.text)
            sentences.append(emitted_sentence)
        if indexes:
            groups.append(GeneratedGroup(label, tuple(indexes)))
    quotes = _unread_items(view) if quote_unread else ()
    positioned_quotes = []
    for quote in quotes:
        start = sum(len(chunk) for chunk in chunks)
        positioned = replace(quote, output_start=start, output_end=start + len(quote.text))
        positioned_quotes.append(positioned)
        chunks.append(positioned.text)
    text = "".join(chunks)
    if len(text) > MAX_CHARS:
        return Refused("BUDGET", "generated output character budget exceeded")
    if not sentences:
        return Refused("NOT_REALIZABLE", "no verified sentence is available")
    return GeneratedText(text, tuple(sentences), tuple(positioned_quotes), tuple(connectives), tuple(groups),
                         request_kind, style)


def _generate_summary(view: Any, entity: str, limit: int, style: str,
                      *, topic_particle: str | None = None,
                      variant_index: int = 0,
                      quote_unread: bool = True) -> GeneratedText | Refused:
    ids = _summary_ids(view, entity, limit, style)
    if isinstance(ids, Refused):
        return ids
    sentences = _sentences_for_ids(view, ids, style, entity, topic_particle, variant_index)
    if isinstance(sentences, Refused):
        return sentences
    return _assemble(view, [(entity, sentences)], style, "summary", quote_unread=quote_unread)


def _generate_answer(view: Any, answer_result: Any, style: str,
                     topic_particle: str | None = None,
                     variant_index: int = 0) -> GeneratedText | Refused:
    realized = realize_answer(view, answer_result, style)
    if isinstance(realized, Refused):
        return realized
    ids = _ids_from_realization(realized)
    sentences = _sentences_for_ids(view, ids, style, "answer-support", topic_particle, variant_index)
    if isinstance(sentences, Refused):
        return sentences
    return _assemble(view, [("answer-support", sentences)], style, "answer")


def _generate_compare(view: Any, entities: Iterable[Any], limit: int,
                      style: str, topic_particle: str | None = None,
                      variant_index: int = 0) -> GeneratedText | Refused:
    names = list(entities)
    if len(names) != 2 or any(not isinstance(name, str) or not name for name in names) or names[0] == names[1]:
        return Refused("NOT_REALIZABLE", "comparison needs two distinct exact entity strings")
    sentence_groups: list[tuple[str, list[GeneratedSentence]]] = []
    for entity in names:
        ids = _summary_ids(view, entity, limit, style)
        if isinstance(ids, Refused):
            return ids
        sentences = _sentences_for_ids(view, ids, style, entity, topic_particle, variant_index)
        if isinstance(sentences, Refused):
            return sentences
        sentence_groups.append((entity, sentences))
    # Entity buckets remain side by side. No only-A/only-B diff, absence,
    # shared-fact, or opposition license is inferred from mere clause order.
    return _assemble(view, sentence_groups, style, "compare")


def generate(view: Any, request: Any, style: str = "plain") -> GeneratedText | Refused:
    """Generate checked source sentences for a summary, answer, or compare.

    ``request`` may be a Japanese entity-summary request, a mapping with
    ``kind`` equal to ``summary``/``compare``/``answer``, or a verified public
    semantic ANSWER result. Summary mappings use ``entity`` and an optional
    ``limit``. Compare mappings use exactly two names in ``entities``. Answer
    mappings carry the upstream result in ``result``. ``variant_index`` selects
    one member of the independently verified surface set, starting at zero.
    """
    if style not in ("plain", "polite"):
        return Refused("INVALID_STYLE", "style must be plain or polite")
    if view is None or not hasattr(view, "clauses") or not hasattr(view, "sources"):
        return Refused("NO_SOURCE_VIEW", "semantic source View is unavailable")
    if isinstance(request, str):
        entity = summary_entity_from_request(request)
        if entity is None:
            return Refused("NOT_REALIZABLE", "request is not a supported entity-summary form")
        return _generate_summary(view, entity, 8, style)
    if not isinstance(request, dict):
        return Refused("NOT_REALIZABLE", "generation request must be a mapping or verified answer result")
    policy = request.get("surface_policy") or request.get("surface") or {}
    variant_index = request.get("variant_index", 0)
    if type(variant_index) is not int or not 0 <= variant_index <= 255:
        return Refused("INVALID_STYLE", "variant_index must be an integer from 0 to 255")
    topic_particle = (request.get("topic_particle")
                      or (policy.get("topic_particle") if isinstance(policy, dict) else None))
    if topic_particle not in (None, "は", "が"):
        return Refused("INVALID_STYLE", "topic_particle must be は or が")
    semantic = request.get("semantic")
    if (request.get("verdict") == "ANSWER"
            or isinstance(semantic, dict) and semantic.get("verified") is True):
        return _generate_answer(view, request, style, topic_particle, variant_index)
    kind = request.get("kind") or request.get("type")
    if kind in ("summary", "entity-summary"):
        entity = request.get("entity")
        limit = request.get("limit", 8)
        if not isinstance(entity, str) or not entity:
            return Refused("ROLE_NOT_REALIZABLE", "summary entity must be exact source text")
        if type(limit) is not int or limit < 1 or limit > MAX_CLAUSES:
            return Refused("BUDGET", "summary limit must be an integer from 1 to 64")
        return _generate_summary(view, entity, limit, style, topic_particle=topic_particle,
                                 variant_index=variant_index)
    if kind == "compare":
        limit = request.get("limit", 8)
        if type(limit) is not int or limit < 1 or limit > MAX_CLAUSES:
            return Refused("BUDGET", "comparison limit must be an integer from 1 to 64")
        return _generate_compare(view, request.get("entities", ()), limit, style,
                                 topic_particle, variant_index)
    if kind == "answer":
        return _generate_answer(view, request.get("result"), style, topic_particle, variant_index)
    return Refused("NOT_REALIZABLE", "unsupported generation request kind")


__all__ = [
    "ConnectiveLicense", "GeneratedGroup", "GeneratedQuote", "GeneratedSentence",
    "GeneratedText", "generate",
]
