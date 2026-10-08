"""Experimental source-event A/C diagnostic, never a user Goal or an ANSWER.

Only one source-licensed assertion event can cross this bridge. The C Atom is
an expression carrier: an empty world adds no actual/fiction world, and C's
``present`` names the nonpast conjugation switch, not an occurrence time.
The full A View travels beside it, including source/event identity and fields
outside the common projection. No network, subprocess, corpus or model access.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
from decimal import Decimal
import hashlib
import json
import math

from . import semantic_ir as a
from .content_ir import Atom, ContentError
from .content_realizer import atom_text
from .semantic_reader import document_view
from .semantic_verify import Rejected, license_clause
from .typed_edges import _tagger

VERSION = "source-event-bridge-v1"
MAX_DOCUMENTS = 4
MAX_SOURCE_CHARS = 4096
MAX_ENVELOPE_CHARS = 262144
MAX_DEPTH = 32
ROLES = frozenset(("agent", "patient", "recipient"))


class BridgeError(ValueError):
    def __init__(self, verdict: str, reason: str):
        super().__init__(reason)
        self.verdict, self.reason = verdict, reason


@dataclass(frozen=True)
class EventProjection:
    predicate: str
    roles: tuple[tuple[str, str], ...]
    polarity: str
    time: str
    modality: str = "assert"


@dataclass(frozen=True)
class SourceEventEnvelope:
    prototype: str
    prototype_sha256: str
    clause_id: str
    projection: EventProjection
    atom: Atom
    version: str = VERSION
    experimental: bool = True
    adoption_eligible: bool = False


_TYPES = {cls.__name__: cls for cls in (
    a.View, a.Clause, a.Variable, a.Span, a.Role, a.Pattern, a.Quantity,
    a.Nominal, a.EventValue, a.Unread, Atom, EventProjection, SourceEventEnvelope,
)}


def _fail(reason, verdict="UNKNOWN_MEANING_SUBSET"):
    raise BridgeError(verdict, reason)


def _utf8(text):
    if type(text) is not str:
        _fail("expected a text field", "UNKNOWN_MEANING_TYPE")
    try:
        return text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise BridgeError("UNKNOWN_MEANING_UTF8", "text contains a non-UTF8 surrogate") from exc


def _encode(value, depth=0):
    """Tagged, non-executable snapshot; tuples/dict keys/metadata stay typed."""
    if depth > MAX_DEPTH:
        _fail("prototype nesting exceeds diagnostic bound", "UNKNOWN_MEANING_BUDGET")
    enc = lambda x: _encode(x, depth + 1)
    if type(value) is str:
        _utf8(value)
        return value
    if value is None or type(value) in (int, bool):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if isinstance(value, Decimal) and value.is_finite():
        return {"decimal": str(value)}
    if is_dataclass(value) and _TYPES.get(type(value).__name__) is type(value):
        return {"type": type(value).__name__,
                "fields": {f.name: enc(getattr(value, f.name)) for f in fields(value)}}
    if type(value) in (tuple, list):
        return {"tuple" if type(value) is tuple else "list": [enc(x) for x in value]}
    if type(value) is dict:
        return {"dict": [[enc(k), enc(v)] for k, v in value.items()]}
    _fail("prototype contains an unrepresented type", "UNKNOWN_MEANING_CODEC")


def _decode(value, depth=0):
    if depth > MAX_DEPTH:
        _fail("prototype nesting exceeds diagnostic bound", "UNKNOWN_MEANING_BUDGET")
    dec = lambda x: _decode(x, depth + 1)
    if type(value) is str:
        _utf8(value)
        return value
    if value is None or type(value) in (int, bool):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if type(value) is not dict:
        _fail("invalid prototype encoding", "UNKNOWN_MEANING_CODEC")
    if set(value) == {"decimal"}:
        number = Decimal(value["decimal"])
        if not number.is_finite():
            _fail("nonfinite prototype quantity", "UNKNOWN_MEANING_CODEC")
        return number
    for kind, constructor in (("tuple", tuple), ("list", list)):
        if set(value) == {kind} and type(value[kind]) is list:
            return constructor(dec(x) for x in value[kind])
    if set(value) == {"dict"} and type(value["dict"]) is list:
        result = {}
        for pair in value["dict"]:
            if type(pair) is not list or len(pair) != 2:
                _fail("invalid prototype dictionary entry", "UNKNOWN_MEANING_CODEC")
            k, v = map(dec, pair)
            if k in result:
                _fail("duplicate prototype dictionary key", "UNKNOWN_MEANING_CODEC")
            result[k] = v
        return result
    if set(value) == {"type", "fields"} and value["type"] in _TYPES:
        cls = _TYPES[value["type"]]
        if type(value["fields"]) is not dict or set(value["fields"]) != {f.name for f in fields(cls)}:
            _fail("prototype field coverage mismatch", "UNKNOWN_MEANING_CODEC")
        args = {f.name: dec(value["fields"][f.name]) for f in fields(cls) if f.init}
        result = cls(**args)
        if _encode(result) != value:
            _fail("derived View metadata or field changed on restoration", "UNKNOWN_MEANING_CODEC")
        return result
    _fail("unknown prototype type tag", "UNKNOWN_MEANING_CODEC")


def _dumps(value):
    try:
        raw = json.dumps(_encode(value), ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except BridgeError:
        raise
    except (ValueError, TypeError, ArithmeticError, RecursionError) as exc:
        raise BridgeError("UNKNOWN_MEANING_CODEC", "invalid typed prototype encoding") from exc
    if len(raw) > MAX_ENVELOPE_CHARS:
        _fail("prototype exceeds diagnostic bound", "UNKNOWN_MEANING_BUDGET")
    return raw


def _loads(raw):
    if type(raw) is not str or len(raw) > MAX_ENVELOPE_CHARS:
        _fail("prototype size/type exceeds diagnostic bound", "UNKNOWN_MEANING_BUDGET")
    try:
        def unique_fields(pairs):
            result = dict(pairs)
            if len(result) != len(pairs):
                _fail("duplicate JSON object field", "UNKNOWN_MEANING_CODEC")
            return result
        return _decode(json.loads(raw, object_pairs_hook=unique_fields))
    except BridgeError:
        raise
    except (ValueError, TypeError, KeyError, AttributeError, ArithmeticError, RecursionError) as exc:
        raise BridgeError("UNKNOWN_MEANING_CODEC", "invalid typed prototype: " + str(exc)) from exc


def _source_bounds(documents):
    if not isinstance(documents, Mapping) or not 1 <= len(documents) <= MAX_DOCUMENTS:
        _fail("expected a bounded raw document mapping", "UNKNOWN_MEANING_INPUT")
    if any(type(k) is not str or not k or type(v) is not str for k, v in documents.items()):
        _fail("source IDs and raw documents must be strings", "UNKNOWN_MEANING_INPUT")
    if sum(len(k) + len(v) for k, v in documents.items()) > MAX_SOURCE_CHARS:
        _fail("raw sources and source IDs exceed diagnostic bound", "UNKNOWN_MEANING_BUDGET")
    for key, raw in documents.items():
        _utf8(key)
        _utf8(raw)


def _view_shape_and_coverage(view):
    """Validate before A's checker; independently cover every raw character.

    Only whitespace may exist outside the sole Clause.span or in other sources.
    This is a bounded raw span scan, not trust in reader-produced unread flags
    and not a whole-document reparse. The A license still replays clause meaning.
    """
    if type(view) is not a.View or type(view.sources) is not dict:
        _fail("expected an A View with a source dictionary", "UNKNOWN_MEANING_TYPE")
    _source_bounds(view.sources)
    if (any(type(v) is not tuple for v in (view.clauses, view.unread, view.invalid))
            or any(type(v) is not dict for v in (view.by_id, view.by_predicate, view.by_sovereign))
            or type(view.ingest_ms) not in (int, float)
            or (type(view.ingest_ms) is float and not math.isfinite(view.ingest_ms))):
        _fail("invalid View container or metadata type", "UNKNOWN_MEANING_TYPE")
    if view.invalid or view.unread or len(view.clauses) != 1:
        _fail("one complete event with no invalid/unread source is required")
    clause = view.clauses[0]
    if type(clause) is not a.Clause:
        _fail("expected a typed source Clause", "UNKNOWN_MEANING_TYPE")
    for text in (clause.id, clause.predicate, clause.polarity, clause.modality, clause.time,
                 clause.exception_of, clause.rule, clause.sovereign, clause.family):
        _utf8(text)
    if (type(clause.event) is not a.Variable or type(clause.event.name) is not str
            or not clause.event.name or clause.event.sort != "event"):
        _fail("source event must be a named event Variable", "UNKNOWN_MEANING_TYPE")
    _utf8(clause.event.name)
    if any(type(v) is not tuple for v in (clause.roles, clause.conditions, clause.condition_spans,
                                         clause.exceptions, clause.exception_spans, clause.unsupported)):
        _fail("invalid source Clause collection type", "UNKNOWN_MEANING_TYPE")
    spans = [clause.span, clause.predicate_span]
    if clause.body_span is not None:
        spans.append(clause.body_span)
    for role in clause.roles:
        if type(role) is not a.Role:
            _fail("expected a typed source Role", "UNKNOWN_MEANING_TYPE")
        for text in (role.name, role.term, role.rule):
            _utf8(text)
        spans.append(role.span)
    for span in spans:
        if type(span) is not a.Span or not span.valid(view.sources):
            _fail("invalid source Span type or bounds", "UNKNOWN_MEANING_TYPE")
        _utf8(span.source)
        _utf8(span.text)
    for key, raw in view.sources.items():
        outside = raw[:clause.span.start] + raw[clause.span.end:] if key == clause.span.source else raw
        if outside.strip():
            _fail("non-whitespace source text is outside the sole licensed event", "UNKNOWN_MEANING_COVERAGE")


def _projection(view):
    _view_shape_and_coverage(view)
    clause = view.clauses[0]
    if clause.rule != "frame" or clause.family != "document" or clause.modality != "assert":
        _fail("only document assertion events have a shared mapping; no world is assigned")
    if (clause.conditions or clause.condition_spans or clause.exceptions or clause.exception_spans
            or clause.exception_of or clause.unsupported):
        _fail("conditions/exceptions/unsupported information cannot be projected away")
    if clause.time not in ("past", "nonpast") or clause.polarity not in ("+", "-"):
        _fail("an explicit grammatical time and polarity are required")
    roles = {r.name: r.term for r in clause.roles}
    if (len(roles) != len(clause.roles) or not set(roles) <= ROLES or not roles.get("agent")
            or any(type(v) is not str or not v for v in roles.values())):
        _fail("only string agent/patient/recipient roles have a shared mapping")
    try:
        license_clause(clause, view)
    except Rejected as exc:
        raise BridgeError("UNKNOWN_MEANING_SOURCE_LICENSE", str(exc)) from exc
    # Common projection represents only plain polarity/tense endings, not
    # aspect, auxiliary predicates, voice, politeness or discourse particles.
    # Check token structure against the licensed predicate boundary; do not
    # whitelist fixture words or compare to C's generated surface.
    body = clause.body_span or clause.span
    raw = body.text
    cursor, endings, ending_forms, punctuation, predicate_form = 0, [], [], False, None
    for token in _tagger()(raw):
        at = raw.find(token.surface, cursor)
        if at < 0:
            _fail("unlocated predicate morphology", "UNKNOWN_MEANING_MORPHOLOGY")
        cursor = at + len(token.surface)
        if (body.start + at, body.start + cursor) == (clause.predicate_span.start, clause.predicate_span.end):
            predicate_form = str(token.feature.cForm)
        if body.start + at < clause.predicate_span.end:
            if body.start + cursor > clause.predicate_span.end:
                _fail("predicate boundary cuts morphology", "UNKNOWN_MEANING_MORPHOLOGY")
            continue
        kind = str(token.feature.cType)
        if (not punctuation and token.feature.pos1 == "助動詞"
                and kind in ("助動詞-ナイ", "助動詞-タ")):
            endings.append(kind)
            ending_forms.append(str(token.feature.cForm))
        elif token.feature.pos1 == "補助記号" and token.feature.pos2 == "句点":
            punctuation = True
        else:
            _fail("predicate suffix has unrepresented morphology", "UNKNOWN_MEANING_MORPHOLOGY")
    if tuple(endings) not in ((), ("助動詞-タ",), ("助動詞-ナイ",), ("助動詞-ナイ", "助動詞-タ")):
        _fail("predicate ending sequence has no shared mapping", "UNKNOWN_MEANING_MORPHOLOGY")
    required_form = "未然形" if "助動詞-ナイ" in endings else "連用形" if endings else "終止形"
    if predicate_form is None or not predicate_form.startswith(required_form + "-"):
        _fail("predicate conjugation is outside the plain assertion subset", "UNKNOWN_MEANING_MORPHOLOGY")
    for index, form in enumerate(ending_forms):
        required_ending = "終止形" if index == len(ending_forms) - 1 else "連用形"
        if not form.startswith(required_ending + "-"):
            _fail("auxiliary conjugation is outside the plain assertion subset", "UNKNOWN_MEANING_MORPHOLOGY")
    if (clause.polarity == "-") != ("助動詞-ナイ" in endings):
        _fail("source morphological polarity differs from projection", "UNKNOWN_MEANING_MORPHOLOGY")
    # Voiced past has orthBase=だ but cType=助動詞-タ; an A omission is refused.
    past = "助動詞-タ" in endings
    if (clause.time == "past") != past:
        _fail("source grammatical tense differs from the A projection", "UNKNOWN_MEANING_TENSE")
    return EventProjection(clause.predicate, tuple(sorted(roles.items())), clause.polarity, clause.time)


def _atom_projection(atom):
    if (type(atom) is not Atom or atom.kind != "event" or atom.world != "" or atom.fluent != ""
            or atom.value != "" or atom.quote != "" or atom.condition != () or type(atom.negated) is not bool
            or atom.tense not in ("past", "present") or not atom.agent
            or any(type(v) is not str for v in (atom.predicate, atom.agent, atom.patient, atom.recipient))):
        _fail("C Atom contains unmapped scope, values, world or tense", "UNKNOWN_MEANING_MAPPING")
    return EventProjection(atom.predicate,
                           tuple(sorted((k, getattr(atom, k)) for k in ROLES if getattr(atom, k))),
                           "-" if atom.negated else "+", "past" if atom.tense == "past" else "nonpast")


def bridge_source_event(view: a.View) -> SourceEventEnvelope:
    """License raw A fields before mapping; keep every field in the envelope."""
    if type(view) is not a.View:
        _fail("expected an A View", "UNKNOWN_MEANING_INPUT")
    _projection(view)  # bounded semantic shape before serialising metadata
    canonical = a.View(dict(view.sources), view.clauses, view.unread, view.ingest_ms)
    if (view.by_id != canonical.by_id or view.by_predicate != canonical.by_predicate
            or view.by_sovereign != canonical.by_sovereign or view.invalid != canonical.invalid):
        _fail("View indexes disagree with their source clauses", "UNKNOWN_MEANING_CODEC")
    prototype = _dumps(view)
    restored = _loads(prototype)  # derived indexes must be reproducible too
    projection = _projection(restored)
    roles = dict(projection.roles)
    atom = Atom(predicate=projection.predicate, agent=roles["agent"],
                patient=roles.get("patient", ""), recipient=roles.get("recipient", ""),
                negated=projection.polarity == "-", tense="past" if projection.time == "past" else "present",
                world="")
    if _atom_projection(atom) != projection:
        _fail("A to C mapping lost meaning", "UNKNOWN_MEANING_MAPPING")
    return SourceEventEnvelope(prototype, hashlib.sha256(_utf8(prototype)).hexdigest(),
                               restored.clauses[0].id, projection, atom)


def restore_source_event(envelope: SourceEventEnvelope, *, atom: Atom | None = None) -> a.View:
    """C back to A is lossless only together with its original licensed View."""
    if type(envelope) is not SourceEventEnvelope or envelope.version != VERSION:
        _fail("unknown envelope version", "UNKNOWN_MEANING_CODEC")
    if envelope.experimental is not True or envelope.adoption_eligible is not False:
        _fail("diagnostic envelope cannot grant adoption", "UNKNOWN_MEANING_CODEC")
    if (type(envelope.prototype) is not str or len(envelope.prototype) > MAX_ENVELOPE_CHARS
            or type(envelope.prototype_sha256) is not str or type(envelope.clause_id) is not str):
        _fail("invalid envelope field type or size", "UNKNOWN_MEANING_CODEC")
    if hashlib.sha256(_utf8(envelope.prototype)).hexdigest() != envelope.prototype_sha256:
        _fail("original prototype hash mismatch", "UNKNOWN_MEANING_CODEC")
    view = _loads(envelope.prototype)
    if type(view) is not a.View:
        _fail("prototype is not an A View", "UNKNOWN_MEANING_CODEC")
    projection = _projection(view)
    if view.clauses[0].id != envelope.clause_id or projection != envelope.projection:
        _fail("envelope projection differs from source", "UNKNOWN_MEANING_MAPPING")
    if _atom_projection(envelope.atom) != projection or (atom is not None and _atom_projection(atom) != projection):
        _fail("C to A mapping changed source meaning", "UNKNOWN_MEANING_MAPPING")
    return view


def pack_source_event(envelope: SourceEventEnvelope) -> str:
    restore_source_event(envelope)
    return _dumps(envelope)


def unpack_source_event(raw: str) -> SourceEventEnvelope:
    envelope = _loads(raw)
    restore_source_event(envelope)
    return envelope


def verify_event_realization(envelope: SourceEventEnvelope, text: str) -> dict:
    """Independent A source licensing and projected equivalence, not C shapes."""
    original = restore_source_event(envelope)
    if type(text) is not str or len(text) > MAX_SOURCE_CHARS:
        _fail("realization size/type exceeds diagnostic bound", "UNKNOWN_MEANING_BUDGET")
    _utf8(text)
    emitted = document_view({"diagnostic-output": text})
    projection = _projection(emitted)
    if projection != envelope.projection:
        _fail("realization changed roles, polarity, predicate or grammatical time", "UNKNOWN_MEANING_EQUIVALENCE")
    clause = original.clauses[0]
    source_id = clause.span.source
    raw = original.sources[source_id]
    source_hash = hashlib.sha256(_utf8(raw)).hexdigest()
    def span_record(span):
        return {"source": span.source, "start": span.start, "end": span.end, "text": span.text}
    evidence = {"clause_id": clause.id, "event": _encode(clause.event),
                "sovereign": clause.sovereign, "family": clause.family,
                "span": span_record(clause.span), "predicate_span": span_record(clause.predicate_span),
                "role_spans": {r.name: span_record(r.span) for r in clause.roles},
                "source_sha256": source_hash,
                "scope": "source-attributed assertion; no claim of actual-world truth"}
    return {"passed": True, "experimental": True, "adoption_eligible": False,
            "contract": "single source-assertion event projection",
            "source_license": "semantic_verify.license_clause",
            "output_license": "semantic_verify.license_clause",
            "original_clause_id": envelope.clause_id, "output_clause_id": emitted.clauses[0].id,
            "source_event_identity": _encode(original.clauses[0].event),
            "source": {"id": source_id, "text": raw, "sha256": source_hash}, "evidence": evidence,
            "scope": "expression only; no user Goal, event occurrence or world assignment"}


def source_event_realizations(documents: Mapping[str, str]) -> dict:
    """Bounded raw-document diagnostic. Never returns ANSWER/CREATED."""
    result = {"experimental": True, "adoption_eligible": False, "version": VERSION,
              "goal_interpreted": False, "world_assigned": False,
              "sources": [], "evidence": [], "realizations": []}
    try:
        _source_bounds(documents)
        view = document_view(dict(documents))
        result["original_view"] = _dumps(view)  # retain refusal input/metadata too
        envelope = bridge_source_event(view)
        text = atom_text(envelope.atom, narrator="") + "。"
        verification = verify_event_realization(envelope, text)
        result.update(verdict="DIAGNOSTIC_REALIZATION", envelope=pack_source_event(envelope),
                      sources=[verification["source"]], evidence=[verification["evidence"]],
                      realizations=[{"text": text, "verification": verification}],
                      subset="one source-licensed plain assert event; string agent/patient/recipient; +/-; past/nonpast; restricted predicate morphology")
    except (BridgeError, ContentError) as exc:
        result.update(verdict=exc.verdict, reason=exc.reason)
    return result
