"""Rule-bound inverse surfaces for the source-bound semantic reader.

The module emits only sentences that pass the independent semantic reader and
the morphological term-lineage check. It never writes a store or evidence.
"""
from __future__ import annotations

import itertools
import re
import unicodedata
from dataclasses import dataclass, replace
from decimal import Decimal
from typing import Any, Iterable

from .realize import conjugate
from .semantic_ir import Clause, Nominal, Quantity, Span, Variable
from .typed_edges import _tagger

MAX_CLAUSES = 64
MAX_CHARS = 2048
SUPPORTED_RULES = frozenset(("frame", "copula", "measure"))
REFUSAL_REASONS = frozenset((
    "UNSUPPORTED_RULE", "UNSUPPORTED_GUARDED", "UNSUPPORTED_MODALITY",
    "ROLE_NOT_REALIZABLE", "CONJUGATION_UNKNOWN", "ROUNDTRIP_MISMATCH",
    "TERM_LINEAGE_MISMATCH", "INVALID_PROVENANCE", "CONFLICT", "BUDGET",
    "NOT_REALIZABLE", "INVALID_STYLE", "NO_ANSWER_RESULT", "NO_SOURCE_VIEW",
))

_CONTENT_POS = frozenset(("名詞", "動詞", "形容詞", "形状詞", "接頭辞", "接尾辞"))
_PARTICLES = frozenset(("は", "が", "を", "に", "で", "から", "へ", "の", "より"))
_AUX_LEMMAS = frozenset(("た", "ます", "ず", "だ", "です", "ない"))
_NEG_AUX_SURFACES = frozenset(("ない", "なかっ", "なく", "ありません"))
_PUNCT = frozenset("。！？!?、,．.")
_ROLE_ORDER = ("recipient", "goal", "patient", "origin", "location")
_ROLE_PARTICLE = {
    "recipient": "に", "goal": "へ", "patient": "を", "origin": "から",
    "location": "で",
}
_SUMMARY_ABOUT = re.compile(r"(.+?)\u306b\u3064\u3044\u3066\u6559\u3048\u3066[。！？?]*$")
_SUMMARY_GATHER = re.compile(r"(.+?)\u3092\u307e\u3068\u3081\u3066[。！？?]*$")


@dataclass(frozen=True)
class Realized:
    text: str
    clause_id: str
    spans: tuple[Span, ...]
    style: str
    derivation: str
    checks: dict[str, Any]
    clause_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.clause_ids:
            object.__setattr__(self, "clause_ids", (self.clause_id,))

    def as_dict(self) -> dict[str, Any]:
        return {
            "text": self.text, "clause_id": self.clause_id,
            "clause_ids": list(self.clause_ids),
            "spans": [_span_data(s) for s in self.spans], "style": self.style,
            "derivation": self.derivation, "checks": self.checks,
        }


@dataclass(frozen=True)
class Refused:
    reason: str
    detail: str
    clause_ids: tuple[str, ...] = ()
    spans: tuple[Span, ...] = ()
    text: str | None = None
    checks: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "reason": self.reason, "detail": self.detail,
            "clause_ids": list(self.clause_ids),
            "spans": [_span_data(s) for s in self.spans], "text": self.text,
            "checks": self.checks or {},
        }


@dataclass(frozen=True)
class RealizedGroup:
    text: str
    sentences: tuple[Realized, ...]

    @property
    def clause_ids(self) -> tuple[str, ...]:
        return tuple(cid for sentence in self.sentences for cid in sentence.clause_ids)

    @property
    def provenance(self) -> list[dict[str, Any]]:
        return [sentence.as_dict() for sentence in self.sentences]

    def as_dict(self) -> dict[str, Any]:
        return {"text": self.text, "clause_ids": list(self.clause_ids),
                "provenance": self.provenance}


def _span_data(span: Span) -> dict[str, Any]:
    return {"source": span.source, "start": span.start, "end": span.end, "text": span.text}


def _fail(reason: str, detail: str, clause: Clause | None = None,
          checks: dict[str, Any] | None = None) -> Refused:
    if reason not in REFUSAL_REASONS:
        reason = "UNSUPPORTED_RULE"
    ids = (clause.id,) if clause is not None and isinstance(clause.id, str) and clause.id else ()
    spans = _source_spans(clause) if clause is not None else ()
    return Refused(reason, detail, ids, spans, checks=checks)


def _source_spans(clause: Clause) -> tuple[Span, ...]:
    spans: list[Span] = [clause.span]
    spans.extend(r.span for r in clause.roles if isinstance(getattr(r, "span", None), Span))
    if isinstance(clause.predicate_span, Span):
        spans.append(clause.predicate_span)
    unique: dict[tuple[str, int, int, str], Span] = {}
    for span in spans:
        unique[(span.source, span.start, span.end, span.text)] = span
    return tuple(unique.values())


def _has_lineage(clause: Clause) -> tuple[bool, str]:
    if not isinstance(clause, Clause) or not isinstance(clause.id, str) or not clause.id:
        return False, "source clause id is missing"
    span = getattr(clause, "span", None)
    if (not isinstance(span, Span) or not span.source or not span.text
            or span.start < 0 or span.end <= span.start or span.end - span.start != len(span.text)):
        return False, "source clause span is missing or malformed"
    bounded = [getattr(clause, "predicate_span", None), *(getattr(r, "span", None) for r in clause.roles)]
    for item in bounded:
        if not isinstance(item, Span):
            return False, "a source role or predicate has no span"
        if (item.source != span.source or item.start < span.start or item.end > span.end
                or item.end <= item.start or item.end - item.start != len(item.text)):
            return False, "a source role or predicate lies outside its clause span"
        lo, hi = item.start - span.start, item.end - span.start
        if span.text[lo:hi] != item.text:
            return False, "a source span does not match its clause text"
    return True, "source clause, role, and predicate spans are present"


def _lemma(token: Any) -> str:
    feat = token.feature
    return (getattr(feat, "lemma", None) or getattr(feat, "orthBase", None)
            or token.surface)


def check_term_lineage(clause: Clause, sentence: str) -> dict[str, Any]:
    """Check content lemmas against source span text without using the reader."""
    valid, detail = _has_lineage(clause)
    if not valid:
        return {"passed": False, "detail": detail, "extra_lemmas": [], "unexpected_tokens": []}
    tagger = _tagger()
    source_words = list(tagger(clause.span.text))
    licensed = {_lemma(w) for w in source_words if w.feature.pos1 in _CONTENT_POS}
    extra: list[tuple[str, str]] = []
    unexpected: list[str] = []
    for token in tagger(sentence):
        pos = token.feature.pos1
        if pos in _CONTENT_POS:
            if token.surface in _NEG_AUX_SURFACES and pos in ("形容詞", "助動詞"):
                continue
            if (clause.rule == "copula" and token.surface in ("ある", "あり")
                    and _lemma(token) in ("有る", "ある")):
                continue
            lemma = _lemma(token)
            if lemma not in licensed:
                extra.append((token.surface, lemma))
        elif pos == "助詞" and token.surface in _PARTICLES:
            continue
        elif pos == "助動詞" and _lemma(token) in _AUX_LEMMAS:
            continue
        elif (pos == "補助記号" and token.surface
              and all(ch in _PUNCT or unicodedata.category(ch).startswith("P") for ch in token.surface)):
            continue
        else:
            unexpected.append(token.surface)
    passed = not extra and not unexpected
    return {
        "passed": passed,
        "detail": "all content lemmas have source lineage" if passed else "content or function token is unlicensed",
        "extra_lemmas": [{"surface": surface, "lemma": lemma} for surface, lemma in extra],
        "unexpected_tokens": unexpected,
    }


def _term(value: Any) -> Any:
    if isinstance(value, Quantity):
        amount = format(value.amount, "f")
        if "." in amount:
            amount = amount.rstrip("0").rstrip(".")
        return ("quantity", amount, value.unit)
    if isinstance(value, Nominal):
        return ("nominal", value.head, _term(value.term))
    if isinstance(value, Decimal):
        return ("decimal", format(value, "f"))
    if isinstance(value, Variable):
        return ("variable", value.sort, value.name)
    return value


def projection(clause: Clause) -> tuple[Any, ...]:
    roles = tuple(sorted((r.name, _term(r.term)) for r in clause.roles))
    return (clause.rule, clause.predicate, roles, clause.polarity, clause.modality, clause.time)


def check_round_trip(clause: Clause, sentence: str) -> dict[str, Any]:
    """Read the sentence alone and require one supported, projection-equal clause."""
    from .semantic_reader import document_view

    try:
        view = document_view({"gen": sentence})
    except Exception as exc:
        return {"passed": False, "detail": "reader raised " + type(exc).__name__, "clauses": 0, "unread": 0}
    if view.unread:
        return {"passed": False, "detail": "generated text contains unread material",
                "clauses": len(view.clauses), "unread": len(view.unread)}
    if len(view.clauses) != 1:
        return {"passed": False, "detail": "generated text did not read as exactly one clause",
                "clauses": len(view.clauses), "unread": 0}
    candidate = view.clauses[0]
    if candidate.unsupported:
        return {"passed": False, "detail": "generated clause is unsupported: " + "; ".join(candidate.unsupported),
                "clauses": 1, "unread": 0}
    expected, actual = projection(clause), projection(candidate)
    if actual != expected:
        return {"passed": False, "detail": "generated projection differs from source clause",
                "clauses": 1, "unread": 0, "expected": repr(expected), "actual": repr(actual)}
    return {"passed": True, "detail": "single-clause projection matches", "clauses": 1, "unread": 0}


def verify_sentence(clause: Clause, sentence: str) -> dict[str, Any]:
    """Run both independent acceptance checks and report them separately."""
    return {
        "roundtrip": check_round_trip(clause, sentence),
        "term_lineage": check_term_lineage(clause, sentence),
    }


def _role_map(clause: Clause) -> dict[str, Any]:
    out = {}
    for role in clause.roles:
        if role.name in out:
            raise ValueError("duplicate role: " + role.name)
        out[role.name] = role
    return out


def _surface(role: Any, overrides: dict[str, str] | None = None) -> str:
    if overrides and role.name in overrides:
        return overrides[role.name]
    return role.span.text


def _ordered_frame_roles(roles: dict[str, Any], order: Iterable[str] | None = None) -> list[str]:
    names = [name for name in roles if name != "agent"]
    if order is not None:
        return list(order)
    index = {name: i for i, name in enumerate(_ROLE_ORDER)}
    return sorted(names, key=lambda name: (index.get(name, len(index)), name))


def _surface_text(clause: Clause, style: str, *, topic: str = "は",
                  role_order: Iterable[str] | None = None,
                  overrides: dict[str, str] | None = None,
                  polarity: str | None = None, time: str | None = None) -> tuple[str | None, str]:
    roles = _role_map(clause)
    pol = polarity if polarity is not None else clause.polarity
    if clause.rule == "frame":
        supported = {"agent", "patient", "recipient", "origin", "location", "goal"}
        if set(roles) - supported or "agent" not in roles:
            return None, "frame needs a supported agent/case role set"
        if topic not in ("は", "が"):
            return None, "agent particle is outside the closed set"
        ordered = _ordered_frame_roles(roles, role_order)
        if set(ordered) != set(roles) - {"agent"} or len(ordered) != len(roles) - 1:
            return None, "role-order variant does not preserve all roles"
        try:
            verb = conjugate(clause.predicate, past=(time or clause.time) == "past",
                             neg=pol == "-", polite=style == "polite")
        except Exception:
            verb = None
        if not verb:
            return None, "conjugation returned no supported form"
        text = _surface(roles["agent"], overrides) + topic
        for name in ordered:
            particle = _ROLE_PARTICLE.get(name)
            if not particle:
                return None, "role has no licensed particle"
            text += _surface(roles[name], overrides) + particle
        return text + verb + "。", ""
    if clause.rule == "copula":
        if clause.predicate not in ("identity", "property"):
            return None, "copula predicate is outside the closed set"
        required = {"entity", "value"} | ({"attribute"} if clause.predicate == "property" else set())
        if set(roles) != required:
            return None, "copula role set is outside the closed set"
        entity = _surface(roles["entity"], overrides)
        value = _surface(roles["value"], overrides)
        attr = _surface(roles["attribute"], overrides) if "attribute" in roles else ""
        value_tokens = list(_tagger()(roles["value"].span.text))
        value_is_adjective = any(t.feature.pos1 in ("形容詞", "形状詞") for t in value_tokens)
        if pol == "-" and value_is_adjective:
            return None, "reader has no projection-preserving negative adjective copula"
        if style == "polite":
            ending = "ではありません" if pol == "-" else "です"
        elif pol == "-":
            ending = "ではない"
        elif value_is_adjective:
            ending = ""
        else:
            source_lemmas = {_lemma(t) for t in _tagger()(clause.span.text)
                             if t.feature.pos1 in _CONTENT_POS}
            ending = "である" if "有る" in source_lemmas or "ある" in source_lemmas else "だ"
        # The attribute's source span already includes its nominal surface.
        head = entity + ("の" + attr if attr else "")
        return head + "は" + value + ending + "。", ""
    if clause.rule == "measure":
        if clause.predicate.split(".", 1)[0] != "measure" or not {"entity", "value"} <= set(roles):
            return None, "measure needs entity and value roles"
        if set(roles) - {"entity", "kind", "label", "value", "substance"}:
            return None, "measure role set is outside the closed set"
        value = roles["value"]
        if not isinstance(value.term, Quantity):
            return None, "measure value is not a typed quantity"
        label = _surface(roles["entity"], overrides)
        text = label + "は" + _surface(value, overrides)
        if "substance" in roles:
            text += "の" + _surface(roles["substance"], overrides)
        return text + ("です。" if style == "polite" else "だ。"), ""
    return None, "rule is outside the closed v1 set"


def realize_clause(clause: Clause, style: str = "plain") -> Realized | Refused:
    if style not in ("plain", "polite"):
        return _fail("INVALID_STYLE", "style must be plain or polite", clause if isinstance(clause, Clause) else None)
    if not isinstance(clause, Clause):
        return _fail("INVALID_PROVENANCE", "a source Clause is required")
    valid, detail = _has_lineage(clause)
    if not valid:
        return _fail("INVALID_PROVENANCE", detail, clause)
    if clause.conditions or clause.condition_spans or clause.exceptions or clause.exception_spans or clause.exception_of:
        return _fail("UNSUPPORTED_GUARDED", "conditions and exceptions remain in scope", clause)
    if clause.unsupported:
        return _fail("UNSUPPORTED_RULE", "source clause is marked unsupported: " + "; ".join(clause.unsupported), clause)
    if clause.rule not in SUPPORTED_RULES:
        return _fail("UNSUPPORTED_RULE", "rule is outside the closed v1 set", clause)
    if clause.modality != "assert":
        return _fail("UNSUPPORTED_MODALITY", "only asserted clauses are realized", clause)
    if clause.polarity not in ("+", "-"):
        return _fail("ROLE_NOT_REALIZABLE", "polarity is outside the closed set", clause)
    if clause.rule == "frame" and clause.time not in ("past", "nonpast"):
        return _fail("ROLE_NOT_REALIZABLE", "frame time is outside the closed set", clause)
    if clause.rule != "frame" and clause.time:
        return _fail("ROLE_NOT_REALIZABLE", "copula/measure time is not represented by the reader", clause)
    sentence, detail = _surface_text(clause, style)
    if sentence is None:
        reason = "CONJUGATION_UNKNOWN" if clause.rule == "frame" and "conjugation" in detail else "ROLE_NOT_REALIZABLE"
        return _fail(reason, detail, clause)
    checks = verify_sentence(clause, sentence)
    if not checks["roundtrip"]["passed"]:
        return _fail("ROUNDTRIP_MISMATCH", checks["roundtrip"]["detail"], clause, checks)
    if not checks["term_lineage"]["passed"]:
        return _fail("TERM_LINEAGE_MISMATCH", checks["term_lineage"]["detail"], clause, checks)
    if len(sentence) > MAX_CHARS:
        return _fail("BUDGET", "output character budget exceeded", clause, checks)
    return Realized(sentence, clause.id, _source_spans(clause), style, "inverse-reader", checks)


def realize_variants(clause: Clause) -> tuple[Realized | Refused, ...]:
    """Return verified plain/polite, は/が and role-order surfaces."""
    if not isinstance(clause, Clause):
        return (_fail("INVALID_PROVENANCE", "a source Clause is required"),)
    try:
        roles = _role_map(clause)
    except ValueError as exc:
        return (_fail("ROLE_NOT_REALIZABLE", str(exc), clause),)
    non_agent = list(roles) if clause.rule != "frame" else [r for r in roles if r != "agent"]
    orderings: list[tuple[str, ...] | None] = [None]
    if clause.rule == "frame" and len(non_agent) >= 2:
        first = tuple(_ordered_frame_roles(roles))
        reversed_order = tuple(reversed(first))
        orderings = [first, reversed_order] if first != reversed_order else [first]
    particles = ("は", "が") if clause.rule == "frame" and "agent" in roles else ("は",)
    results: list[Realized | Refused] = []
    seen: set[str] = set()
    for style, topic, order in itertools.product(("plain", "polite"), particles, orderings):
        sentence, detail = _surface_text(clause, style, topic=topic, role_order=order)
        if sentence is None:
            results.append(_fail("ROLE_NOT_REALIZABLE", detail, clause))
            continue
        if sentence in seen:
            continue
        seen.add(sentence)
        checks = verify_sentence(clause, sentence)
        if not checks["roundtrip"]["passed"]:
            results.append(_fail("ROUNDTRIP_MISMATCH", checks["roundtrip"]["detail"], clause, checks))
        elif not checks["term_lineage"]["passed"]:
            results.append(_fail("TERM_LINEAGE_MISMATCH", checks["term_lineage"]["detail"], clause, checks))
        elif len(sentence) > MAX_CHARS:
            results.append(_fail("BUDGET", "output character budget exceeded", clause, checks))
        else:
            results.append(Realized(sentence, clause.id, _source_spans(clause), style, "inverse-reader", checks))
    total_chars = sum(len(item.text) for item in results if isinstance(item, Realized))
    if total_chars > MAX_CHARS:
        return (_fail("BUDGET", "surface-variant output character budget exceeded", clause),)
    return tuple(results)


def summary_entity_from_request(text: str) -> str | None:
    """Return the entity only for the two closed public summary request forms."""
    if not isinstance(text, str):
        return None
    for pattern in (_SUMMARY_ABOUT, _SUMMARY_GATHER):
        match = pattern.fullmatch(text.strip())
        if match and match.group(1).strip():
            return match.group(1).strip()
    return None


def _is_unguarded_supported(clause: Clause) -> bool:
    return (clause.rule in SUPPORTED_RULES and not clause.unsupported
            and not clause.conditions and not clause.condition_spans
            and not clause.exceptions and not clause.exception_spans and not clause.exception_of
            and clause.modality == "assert")


def _view_licenses_clause(view: Any, clause: Clause) -> bool:
    sources = getattr(view, "sources", None)
    return (isinstance(sources, dict)
            and all(span.valid(sources) for span in _source_spans(clause)))


def _subject_role(clause: Clause):
    name = "agent" if clause.rule == "frame" else "entity"
    return next((r for r in clause.roles if r.name == name), None)


def _projection_key(clause: Clause) -> tuple[Any, ...]:
    return projection(clause)


def _merge_pair(left_clause: Clause, left: Realized,
                right_clause: Clause, right: Realized) -> Realized | None:
    """Try one same-subject connector; keep both lines unless every gate passes."""
    candidate = left.text[:-1] + "また、" + right.text
    if len(candidate) > MAX_CHARS:
        return None
    left_roundtrip = check_round_trip(left_clause, candidate)
    right_roundtrip = check_round_trip(right_clause, candidate)
    left_lineage = check_term_lineage(left_clause, candidate)
    right_lineage = check_term_lineage(right_clause, candidate)
    if not all(x["passed"] for x in (left_roundtrip, right_roundtrip, left_lineage, right_lineage)):
        return None
    spans = {(s.source, s.start, s.end, s.text): s for s in (*left.spans, *right.spans)}
    ids = tuple(dict.fromkeys((*left.clause_ids, *right.clause_ids)))
    return Realized(
        candidate, ids[0], tuple(spans.values()), left.style, "inverse-reader",
        {"roundtrip": {"passed": True, "detail": "both source projections match"},
         "term_lineage": {"passed": True, "detail": "both source lineages match"}}, ids,
    )


def summarize_entity(view: Any, entity: str, limit: int = 8,
                     style: str = "plain") -> Realized | RealizedGroup | Refused:
    if style not in ("plain", "polite"):
        return _fail("INVALID_STYLE", "style must be plain or polite")
    if view is None or not hasattr(view, "clauses") or not hasattr(view, "sources"):
        return _fail("NO_SOURCE_VIEW", "semantic source View is unavailable")
    if type(limit) is not int or limit < 0 or limit > MAX_CLAUSES:
        return _fail("BUDGET", "summary clause limit must be between 0 and 64")
    if not isinstance(entity, str) or not entity:
        return _fail("ROLE_NOT_REALIZABLE", "entity must be exact source text")
    selected = []
    for clause in view.clauses:
        if not _is_unguarded_supported(clause):
            continue
        subject = _subject_role(clause)
        if subject is not None and subject.term == entity:
            if not _view_licenses_clause(view, clause):
                return _fail("INVALID_PROVENANCE", "source clause spans do not match the View", clause)
            selected.append(clause)
    if len(selected) > min(limit, MAX_CLAUSES):
        return _fail("BUDGET", "summary would exceed its clause budget",
                     selected[0] if selected else None)
    if not selected:
        return _fail("NOT_REALIZABLE", "no supported, unguarded exact-subject clause is available")
    by_key: dict[tuple[Any, ...], list[Clause]] = {}
    conflict_pairs: list[tuple[str, str]] = []
    for i, clause in enumerate(selected):
        current_roles = tuple(sorted((r.name, _term(r.term)) for r in clause.roles))
        for other in selected[:i]:
            if (other.predicate == clause.predicate
                    and tuple(sorted((r.name, _term(r.term)) for r in other.roles)) == current_roles
                    and other.polarity != clause.polarity):
                conflict_pairs.append((other.id, clause.id))
        by_key.setdefault(_projection_key(clause), []).append(clause)
    if conflict_pairs:
        ids = tuple(dict.fromkeys(cid for pair in conflict_pairs for cid in pair))
        spans = tuple(span for clause in selected if clause.id in ids for span in _source_spans(clause))
        return Refused("CONFLICT", "opposite polarity for the same predicate and roles: " + ", ".join(ids),
                       ids, spans)
    entries: list[tuple[Realized, Clause]] = []
    for duplicates in by_key.values():
        first = duplicates[0]
        realized = realize_clause(first, style)
        if isinstance(realized, Refused):
            return realized
        spans: dict[tuple[str, int, int, str], Span] = {
            (s.source, s.start, s.end, s.text): s for s in realized.spans
        }
        ids = []
        for duplicate in duplicates:
            ids.append(duplicate.id)
            spans.update({(s.source, s.start, s.end, s.text): s for s in _source_spans(duplicate)})
        entries.append((replace(realized, clause_ids=tuple(ids), spans=tuple(spans.values())), first))
    sentences: list[Realized] = []
    index = 0
    while index < len(entries):
        current, current_clause = entries[index]
        if index + 1 < len(entries):
            following, following_clause = entries[index + 1]
            left_subject, right_subject = _subject_role(current_clause), _subject_role(following_clause)
            if (left_subject is not None and right_subject is not None
                    and left_subject.term == entity and right_subject.term == entity):
                merged = _merge_pair(current_clause, current, following_clause, following)
                if merged is not None:
                    sentences.append(merged)
                    index += 2
                    continue
        sentences.append(current)
        index += 1
    if len(sentences) > MAX_CLAUSES:
        return _fail("BUDGET", "summary sentence budget exceeded")
    text = "".join(sentence.text for sentence in sentences)
    if len(text) > MAX_CHARS:
        return _fail("BUDGET", "summary character budget exceeded", selected[0])
    if len(sentences) == 1:
        return sentences[0]
    return RealizedGroup(text, tuple(sentences))


def _unpack_span(raw: Any) -> Span | None:
    if isinstance(raw, Span):
        return raw
    if not isinstance(raw, dict):
        return None
    try:
        span = Span(str(raw["source"]), int(raw["start"]), int(raw["end"]), str(raw["text"]))
    except (KeyError, TypeError, ValueError):
        return None
    return span if span.end > span.start and span.end - span.start == len(span.text) else None


def _term_from_data(raw: Any) -> Any:
    if isinstance(raw, (str, int, float, bool, type(None), Quantity, Nominal, Variable)):
        return raw
    if isinstance(raw, dict) and set(raw) == {"amount", "unit"}:
        try:
            return Quantity(Decimal(str(raw["amount"])), str(raw["unit"]))
        except Exception:
            return raw
    return raw


def _clause_from_data(raw: Any) -> Clause | None:
    if isinstance(raw, Clause):
        return raw
    if not isinstance(raw, dict):
        return None
    try:
        span = _unpack_span(raw["span"])
        predicate_span = _unpack_span(raw["predicate_span"])
        evraw = raw["event"]
        if not span or not predicate_span or not isinstance(evraw, dict):
            return None
        event = Variable(str(evraw["name"]), str(evraw.get("sort", "event")))
        roles = []
        for item in raw["roles"]:
            if not isinstance(item, dict):
                return None
            role_span = _unpack_span(item["span"])
            if role_span is None:
                return None
            roles.append((str(item["name"]), _term_from_data(item.get("term")), role_span,
                          str(item.get("rule", "literal"))))
        from .semantic_ir import Role
        body = _unpack_span(raw.get("body_span")) if raw.get("body_span") else None
        conditions = tuple(_pattern_from_data(x) for x in raw.get("conditions", ()))
        exceptions = tuple(_pattern_from_data(x) for x in raw.get("exceptions", ()))
        if any(x is None for x in (*conditions, *exceptions)):
            return None
        return Clause(
            str(raw["id"]), event, str(raw["predicate"]), predicate_span,
            tuple(Role(n, t, s, rule) for n, t, s, rule in roles), span, body,
            str(raw.get("polarity", "+")), str(raw.get("modality", "assert")),
            str(raw.get("time", "")), conditions,
            tuple(s for x in raw.get("condition_spans", ()) if (s := _unpack_span(x)) is not None),
            exceptions,
            tuple(s for x in raw.get("exception_spans", ()) if (s := _unpack_span(x)) is not None),
            str(raw.get("exception_of", "")), str(raw.get("rule", "frame")),
            str(raw.get("sovereign", "document")), str(raw.get("family", "document")),
            tuple(str(x) for x in raw.get("unsupported", ())),
        )
    except (KeyError, TypeError, ValueError):
        return None


def _pattern_from_data(raw: Any):
    if not isinstance(raw, dict):
        return None
    try:
        from .semantic_ir import Pattern
        return Pattern(str(raw["predicate"]), tuple((str(n), _term_from_data(t)) for n, t in raw["roles"]),
                       str(raw.get("polarity", "+")), str(raw.get("modality", "assert")),
                       str(raw.get("time", "")))
    except (KeyError, TypeError, ValueError):
        return None


def _source_clauses_from_result(result: dict[str, Any], view: Any = None) -> list[Clause]:
    semantic = result.get("semantic") if isinstance(result.get("semantic"), dict) else {}
    proof = semantic.get("proof") if isinstance(semantic.get("proof"), dict) else {}
    nodes = proof.get("nodes", ()) if isinstance(proof, dict) else ()
    clauses: list[Clause] = []
    seen = set()
    for node in nodes if isinstance(nodes, (tuple, list)) else ():
        if not isinstance(node, dict) or node.get("op") != "Source":
            continue
        raw = node.get("clause")
        cid = raw.get("id") if isinstance(raw, dict) else getattr(raw, "id", None)
        clause = view.by_id.get(cid) if view is not None and cid in getattr(view, "by_id", {}) else _clause_from_data(raw)
        if isinstance(clause, Clause) and clause.id not in seen:
            seen.add(clause.id)
            clauses.append(clause)
    return clauses


def _plan_has_operation(result: dict[str, Any], op: str) -> bool:
    semantic = result.get("semantic") if isinstance(result.get("semantic"), dict) else {}
    plan = semantic.get("plan") if isinstance(semantic.get("plan"), dict) else {}
    return any(isinstance(node, dict) and node.get("op") == op for node in plan.get("nodes", ()))


def _answer_roles(result: dict[str, Any]) -> set[Any]:
    raw = result.get("answer_values", ())
    values = set()
    for item in raw if isinstance(raw, (list, tuple)) else ():
        if isinstance(item, (list, tuple)) and len(item) == 2:
            values.add(_term(_term_from_data(item[1])))
    if not values:
        for value in result.get("values", ()) if isinstance(result.get("values"), list) else ():
            values.add(_term(value))
    return values


def realize_answer(view: Any, request_text_or_result: Any,
                   style: str = "plain") -> Realized | RealizedGroup | Refused:
    """Realize only source clauses embedded in a verified public ANSWER proof."""
    if style not in ("plain", "polite"):
        return _fail("INVALID_STYLE", "style must be plain or polite")
    if not isinstance(request_text_or_result, dict):
        return _fail("NO_ANSWER_RESULT", "a public Vera.ask result with a proof is required")
    result = request_text_or_result
    semantic = result.get("semantic") if isinstance(result.get("semantic"), dict) else {}
    if result.get("verdict") != "ANSWER" or semantic.get("verified") is not True:
        return realize_refusal(result, view)
    if _plan_has_operation(result, "Sum") or _plan_has_operation(result, "Compare"):
        clauses = _source_clauses_from_result(result, view)
        if len(clauses) > MAX_CLAUSES:
            return _fail("BUDGET", "proof exceeds the realization clause budget")
        ids = tuple(c.id for c in clauses)
        spans = tuple(s for c in clauses for s in _source_spans(c))
        answer_text = str(result.get("text", ""))
        if len(answer_text) > MAX_CHARS:
            return Refused("BUDGET", "existing measure answer exceeds the character budget", ids, spans)
        detail = "computed answer remains in its existing format: " + answer_text
        return Refused("NOT_REALIZABLE", detail, ids, spans, answer_text or None)
    clauses = _source_clauses_from_result(result, view)
    if not clauses:
        return _fail("NOT_REALIZABLE", "verified answer proof contains no source clauses")
    if len(clauses) > MAX_CLAUSES:
        return _fail("BUDGET", "proof exceeds the realization clause budget")
    answer_terms = _answer_roles(result)
    chosen = []
    for clause in clauses:
        role_terms = {_term(role.term) for role in clause.roles}
        if answer_terms and role_terms & answer_terms:
            chosen.append(clause)
    if not chosen:
        # Boolean answers are licensed by the clause polarity; other results
        # with no direct role term remain a typed refusal.
        if any(isinstance(value, bool) for value in answer_terms):
            chosen = clauses[:1]
        else:
            return _fail("NOT_REALIZABLE", "proof roles do not expose the answer term")
    if len(chosen) > MAX_CLAUSES:
        return _fail("BUDGET", "proof exceeds the realization clause budget")
    unique: dict[tuple[Any, ...], list[Clause]] = {}
    for clause in chosen:
        unique.setdefault(projection(clause), []).append(clause)
    realized: list[Realized] = []
    for duplicates in unique.values():
        item = realize_clause(duplicates[0], style)
        if isinstance(item, Refused):
            return item
        all_spans = {(s.source, s.start, s.end, s.text): s for s in item.spans}
        for duplicate in duplicates[1:]:
            all_spans.update({(s.source, s.start, s.end, s.text): s for s in _source_spans(duplicate)})
        realized.append(replace(item, clause_ids=tuple(c.id for c in duplicates), spans=tuple(all_spans.values())))
    text = "".join(item.text for item in realized)
    if len(text) > MAX_CHARS:
        return _fail("BUDGET", "answer output character budget exceeded")
    return realized[0] if len(realized) == 1 else RealizedGroup(text, tuple(realized))


def _serialized_spans(result: dict[str, Any]) -> list[tuple[str, Span, str | None]]:
    found: list[tuple[str, Span, str | None]] = []
    semantic = result.get("semantic") if isinstance(result.get("semantic"), dict) else {}
    values = list(semantic.get("source_unread", ()))
    for trace in result.get("trace", ()) if isinstance(result.get("trace"), list) else ():
        if isinstance(trace, dict):
            values.extend(trace.get("source_unread", ()) if isinstance(trace.get("source_unread"), list) else ())
    request = semantic.get("request") if isinstance(semantic.get("request"), dict) else {}
    values.extend(request.get("unread", ()) if isinstance(request.get("unread"), list) else ())
    seen = set()
    for item in values:
        if not isinstance(item, dict):
            continue
        rawspan = item.get("span", item)
        span = _unpack_span(rawspan)
        if span is None:
            continue
        cid = item.get("clause_id") or item.get("id")
        reason = str(item.get("reason", "unread source text"))
        key = (cid, span.source, span.start, span.end, span.text)
        if key not in seen:
            found.append((reason, span, str(cid) if cid else None)); seen.add(key)
    return found


def _conflict_spans(result: dict[str, Any], view: Any) -> list[tuple[str, Span, str | None]]:
    if view is None or not hasattr(view, "clauses"):
        return []
    semantic = result.get("semantic") if isinstance(result.get("semantic"), dict) else {}
    request = semantic.get("request") if isinstance(semantic.get("request"), dict) else {}
    plans = request.get("plans", ()) if isinstance(request, dict) else ()
    predicates = set()
    for plan in plans if isinstance(plans, (list, tuple)) else ():
        for op in plan.get("nodes", ()) if isinstance(plan, dict) else ():
            pattern = op.get("pattern") if isinstance(op, dict) else None
            if isinstance(pattern, dict) and pattern.get("predicate") not in (None, "*"):
                predicates.add(str(pattern["predicate"]))
    matching = [c for c in view.clauses if not predicates or c.predicate in predicates]
    chosen: dict[str, Clause] = {}
    for i, clause in enumerate(matching):
        roles = tuple(sorted((r.name, _term(r.term)) for r in clause.roles))
        opponent = next((other for other in matching[:i] if other.predicate == clause.predicate
                         and tuple(sorted((r.name, _term(r.term)) for r in other.roles)) == roles
                         and other.polarity != clause.polarity), None)
        if opponent:
            chosen[opponent.id] = opponent; chosen[clause.id] = clause
    return [("conflicting source clause", c.span, c.id) for c in chosen.values()
            if _view_licenses_clause(view, c)]


def _quote_span_valid(span: Span, result: dict[str, Any], view: Any = None) -> bool:
    sources = getattr(view, "sources", None)
    if isinstance(sources, dict) and span.source in sources:
        return span.valid(sources)
    if span.source == "question":
        semantic = result.get("semantic") if isinstance(result.get("semantic"), dict) else {}
        request = semantic.get("request") if isinstance(semantic.get("request"), dict) else {}
        raw = request.get("text")
        return (isinstance(raw, str) and 0 <= span.start < span.end <= len(raw)
                and raw[span.start:span.end] == span.text)
    return True


def realize_refusal(result: dict[str, Any], view: Any = None) -> Refused:
    """Make a verdict line only when an exact blocking span can be cited."""
    if not isinstance(result, dict):
        return Refused("NOT_REALIZABLE", "ask result is unavailable")
    verdict = str(result.get("verdict", "UNKNOWN"))
    if verdict == "ANSWER":
        verdict = "NOT_REALIZABLE"
    quotes = _serialized_spans(result)
    if not quotes and verdict == "CONFLICT":
        quotes = _conflict_spans(result, view)
    if not quotes:
        return Refused(verdict if verdict in REFUSAL_REASONS else "NOT_REALIZABLE",
                       str(result.get("reason", "no source blocker span is available")))
    quotes = [item for item in quotes if _quote_span_valid(item[1], result, view)]
    if not quotes:
        return Refused(verdict if verdict in REFUSAL_REASONS else "NOT_REALIZABLE",
                       "blocking span does not match the available source")
    if len(quotes) > MAX_CLAUSES:
        return Refused("BUDGET", "refusal cites more than 64 blocking spans")
    ids = []
    spans = []
    for reason, span, cid in quotes:
        # The deterministic unread identifier ties a quote to its exact source
        # range when the reader correctly kept it out of the Clause inventory.
        ids.append(cid or f"unread:{span.source}:{span.start}:{span.end}")
        spans.append(span)
    sentence = verdict + "：「" + "」「".join(span.text for span in spans) + "」。"
    if len(sentence) > MAX_CHARS:
        return Refused("BUDGET", "refusal text exceeds the character budget", tuple(ids), tuple(spans))
    return Refused(verdict if verdict in REFUSAL_REASONS else "NOT_REALIZABLE",
                   str(result.get("reason", "typed verdict refusal")), tuple(ids), tuple(spans), sentence)


def refusal_sentence(reason: str, detail: str, clause_ids: Iterable[str],
                     spans: Iterable[Span]) -> Refused:
    """Build a refusal sentence from exact, provenance-bearing source spans."""
    reason = reason if reason in REFUSAL_REASONS else "NOT_REALIZABLE"
    spans = tuple(spans)
    ids = tuple(dict.fromkeys(str(cid) for cid in clause_ids if cid))
    if not spans or not ids:
        return Refused(reason, detail, ids, spans)
    text = reason + "：「" + "」「".join(span.text for span in spans) + "」。"
    if len(text) > MAX_CHARS:
        return Refused("BUDGET", "refusal text exceeds the character budget", ids, spans)
    return Refused(reason, detail, ids, spans, text)


__all__ = [
    "MAX_CLAUSES", "MAX_CHARS", "REFUSAL_REASONS", "Realized", "RealizedGroup", "Refused",
    "check_round_trip", "check_term_lineage", "projection", "realize_answer", "realize_clause",
    "realize_refusal", "realize_variants", "refusal_sentence", "summarize_entity", "summary_entity_from_request",
    "verify_sentence",
]
