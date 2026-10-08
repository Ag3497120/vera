"""Narrow raw-request to source-bound Goal diagnostic.

This is deliberately opt-in and is not connected to the normal router.  It
reuses ``question.Query``, ``content_ir.Ledger`` and the existing A/C event
bridge.  It does not create another Goal IR or assign a truth world.
"""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import re
from collections.abc import Mapping

from . import question
from .content_ir import Atom, ContentError, Ledger, Obligation, Source, Span, digest
from .content_reader import read_brief
from .content_realizer import atom_text
from .meaning_bridge import (
    BridgeError, bridge_source_event, pack_source_event,
    restore_source_event, verify_event_realization,
)
from .semantic_reader import document_view


VERSION = "raw-meaning-goal-bridge-v1"
MAX_REQUEST_CHARS = 1200
MAX_SOURCE_CHARS = 4096
MAX_DOCUMENTS = 4

# A tiny anchored grammar covers two source-basis forms, two count forms and
# two distinct action verbs. Near misses stay unread; no similarity threshold
# or comparison to our own output surface is involved.
_REQUEST_PATTERN = re.compile(
    r"(?:資料に基づいて|資料から)\s*(?:一文|1文)\s*で\s*"
    r"(?P<verb>説明して|言い換えて)(?:ください|下さい)。?"
)
_LEDGER_TEMPLATE = "資料に基づいて一文で説明してください。"


def _base(input_kind: str) -> dict:
    return {
        "version": VERSION,
        "experimental": True,
        "adoption_eligible": False,
        "diagnostic_input": input_kind,
        "verdict": "UNKNOWN_MEANING_GOAL",
        "goal_interpreted": False,
        "raw_goal_path_success": False,
        "world_assigned": False,
        "evidence": [],
        "realizations": [],
    }


def _source_inputs(documents: Mapping[str, str]) -> tuple[Source, ...]:
    if not isinstance(documents, Mapping) or not 1 <= len(documents) <= MAX_DOCUMENTS:
        raise ValueError("expected one to four named source documents")
    material = []
    size = 0
    for source_id, text in documents.items():
        if type(source_id) is not str or not source_id or source_id == "brief" or type(text) is not str:
            raise ValueError("source IDs and source documents must be strings")
        source_id.encode("utf-8")
        text.encode("utf-8")
        size += len(source_id) + len(text)
        material.append(Source(source_id, text, family="document", purpose="evidence"))
    if size > MAX_SOURCE_CHARS:
        raise ValueError("source documents exceed the diagnostic size bound")
    return tuple(material)


def _raw_ledger(raw_request: str, template: str, materials: tuple[Source, ...]) -> Ledger:
    if template != _LEDGER_TEMPLATE:
        raise ContentError("UNKNOWN_MEANING_GOAL", "unsupported fixed reader template")
    documents = {source.id: source.text for source in materials}
    envelope = bridge_source_event(document_view(documents))
    restored = restore_source_event(envelope)
    clause = restored.clauses[0]
    source = next((item for item in materials if item.id == clause.span.source), None)
    if source is None:
        raise ContentError("UNKNOWN_MEANING_GOAL", "source event span has no evidence document")

    # C's Reader creates the request Ledger, but it cannot read every surface
    # order licensed by the existing A source-event bridge. Feed C the
    # canonical C surface derived from that independently licensed event, then
    # rebind its event obligation to A's exact original source span. No source
    # event, role, polarity, tense, or other Reader obligation is discarded.
    canonical_text = atom_text(envelope.atom, narrator="") + "。"
    canonical_materials = tuple(
        replace(item, text=canonical_text) if item.id == source.id else item
        for item in materials
    )
    parsed = read_brief(template, materials=canonical_materials)
    expected_atom = replace(envelope.atom, world="actual")
    canonical_source = next(item for item in canonical_materials if item.id == source.id)
    canonical_event_span = Span.of(canonical_source)
    valid, reason = _ledger_contract(
        parsed, expected_event_span=canonical_event_span,
        expected_event_atom=expected_atom, expected_brief_text=template,
        expected_materials=canonical_materials,
    )
    if not valid:
        raise ContentError("UNKNOWN_MEANING_GOAL", "fixed Reader output violated its contract: " + reason)

    # Keep the exact user text as the brief. Only request-side spans move to
    # that text; the evidence event remains attached to its original source.
    brief = Source("brief", raw_request, family="brief", purpose="instruction")
    whole = Span.of(brief)
    original_event_span = Span(source.id, clause.span.start, clause.span.end, source.sha256)
    obligations = []
    for item in parsed.obligations:
        if item.kind in ("mode", "sentences", "source_summary"):
            obligations.append(replace(item, span=whole))
        elif item.kind == "event":
            obligations.append(replace(item, span=original_event_span))
        else:
            raise ContentError("UNKNOWN_MEANING_GOAL",
                               "fixed Reader emitted an obligation outside the supported subset")
    ledger = Ledger(brief, materials, tuple(obligations), parsed.rules, parsed.unread,
                    parsed.mode, parsed.choice)
    valid, reason = _ledger_contract(
        ledger, expected_event_span=original_event_span,
        expected_event_atom=expected_atom, expected_brief_text=raw_request,
        expected_materials=materials,
    )
    if not valid:
        raise ContentError("UNKNOWN_MEANING_GOAL", "raw Reader Ledger failed revalidation: " + reason)
    return ledger


def _ledger_contract(ledger: Ledger, *, expected_event_span: Span,
                     expected_event_atom: Atom, expected_brief_text: str,
                     expected_materials: tuple[Source, ...] | list[Source]) -> tuple[bool, str]:
    if type(ledger) is not Ledger:
        return False, "expected existing content_ir.Ledger"
    # Ledger's contract is a finite sequence. Check before iterating so malformed
    # typed API inputs become a deliberate hold, not a leaked TypeError.
    if type(ledger.materials) not in (tuple, list):
        return False, "Ledger.materials must be a tuple or list"
    if any(type(item) is not Source for item in ledger.materials):
        return False, "Ledger.materials must contain exact Source values"
    if type(ledger.brief) is not Source:
        return False, "Ledger.brief must be an exact Source value"
    if (_source_authority_record(ledger.brief) is None
            or (ledger.brief.id, ledger.brief.family, ledger.brief.purpose, ledger.brief.independent)
            != ("brief", "brief", "instruction", "")):
        return False, "Ledger brief authority or identity is invalid"
    if (ledger.brief.text != expected_brief_text
            or type(expected_brief_text) is not str):
        return False, "Ledger brief differs from the trusted request text"
    if type(ledger.obligations) is not tuple:
        return False, "Ledger.obligations must be the Reader's finite tuple"
    if type(ledger.unread) is not tuple or type(ledger.rules) is not tuple or type(ledger.choice) is not tuple:
        return False, "Ledger rules, unread spans, and choices must use the Reader's tuple contract"
    if ledger.unread or ledger.rules or ledger.choice or ledger.mode != "actual":
        return False, "Goal must be fully read, evidence-only, and rule-free"
    expected_records = [_source_authority_record(item) for item in expected_materials]
    actual_records = [_source_authority_record(item) for item in ledger.materials]
    if (None in expected_records or None in actual_records
            or len(expected_records) != len(actual_records)
            or set(expected_records) != set(actual_records)):
        return False, "Ledger source identity or authority metadata differs from separate evidence input"
    if (type(expected_event_span) is not Span or type(expected_event_atom) is not Atom
            or type(ledger.obligations) is not tuple or len(ledger.obligations) != 4):
        return False, "Goal requires one explicit source event and exactly three request obligations"
    if any(type(item) is not Obligation for item in ledger.obligations):
        return False, "Ledger obligations must be exact content_ir.Obligation values"
    if any(type(item.id) is not str or not item.id or type(item.kind) is not str
           or type(item.value) is not str or type(item.number) is not int
           or type(item.relation) is not tuple for item in ledger.obligations):
        return False, "Ledger obligation fields violate the Reader type contract"
    if len({item.id for item in ledger.obligations}) != len(ledger.obligations):
        return False, "Ledger obligation IDs must be unique"
    by_kind = {}
    for item in ledger.obligations:
        by_kind.setdefault(item.kind, []).append(item)
    if set(by_kind) != {"mode", "sentences", "source_summary", "event"}:
        return False, "Goal contains missing or unsupported Reader obligations"
    if any(len(by_kind[kind]) != 1 for kind in by_kind):
        return False, "Goal requires exactly one of each supported Reader obligation"
    request_span = Span.of(ledger.brief)
    for kind in ("mode", "sentences", "source_summary"):
        item = by_kind[kind][0]
        if (type(item.span) is not Span or item.span != request_span
                or item.atom is not None or item.state is not None or item.relation != ()):
            return False, "request obligation span or payload differs from the trusted brief"
    mode_item = by_kind["mode"][0]
    sentence_item = by_kind["sentences"][0]
    summary_item = by_kind["source_summary"][0]
    if ((mode_item.value, mode_item.number) != ("actual", 0)
            or (sentence_item.value, sentence_item.number) != ("", 1)
            or (summary_item.value, summary_item.number) != ("", 0)):
        return False, "Goal requires evidence-only mode, one sentence, and source-summary intent"
    event_item = by_kind["event"][0]
    if (event_item.value != "material_evidence" or event_item.number != 0
            or event_item.span != expected_event_span or event_item.atom != expected_event_atom
            or event_item.state is not None or event_item.relation != ()):
        return False, "source event obligation differs from independently licensed event and span"
    return True, ""


def _source_authority_record(source: Source) -> tuple | None:
    """Return the full typed source identity, including its authority fields."""
    if type(source) is not Source:
        return None
    values = (source.id, source.text, source.family, source.purpose, source.independent)
    if any(type(value) is not str for value in values):
        return None
    try:
        for value in values:
            value.encode("utf-8")
    except UnicodeError:
        return None
    return (source.id, source.text, source.sha256, source.family,
            source.purpose, source.independent)


def _bound_diagnostic(documents: Mapping[str, str], ledger: Ledger, action: str,
                      input_kind: str, *, raw_request: str = "", query=None) -> dict:
    result = _base(input_kind)
    if raw_request:
        result["raw_request"] = raw_request
    if action not in ("explain", "paraphrase"):
        result.update(verdict="UNKNOWN_MEANING_GOAL", reason="unsupported request action")
        return result
    try:
        materials = _source_inputs(documents)
        result["source_inputs"] = [
            {"id": item.id, "text": item.text, "sha256": item.sha256}
            for item in materials
        ]
        if type(ledger) is not Ledger:
            result.update(verdict="UNKNOWN_MEANING_GOAL",
                          reason="expected existing content_ir.Ledger")
            return result
        if type(ledger.materials) not in (tuple, list):
            result.update(verdict="UNKNOWN_MEANING_GOAL",
                          reason="Ledger.materials must be a tuple or list")
            return result
        expected = {_source_authority_record(source) for source in materials}
        ledger_records = [_source_authority_record(source) for source in ledger.materials]
        if (None in expected or None in ledger_records
                or len(ledger_records) != len(materials)
                or set(ledger_records) != expected):
            result.update(verdict="UNKNOWN_MEANING_GOAL",
                          reason="Ledger source identity or authority metadata differs from separate evidence input")
            return result

        view = document_view(dict(documents))
        envelope = bridge_source_event(view)
        restored = restore_source_event(envelope)
        clause = restored.clauses[0]
        source = next((item for item in materials if item.id == clause.span.source), None)
        if source is None:
            result.update(verdict="UNKNOWN_MEANING_GOAL",
                          reason="licensed event span has no supplied evidence document")
            return result
        expected_event_span = Span(source.id, clause.span.start, clause.span.end, source.sha256)
        expected_event_atom = replace(envelope.atom, world="actual")
        if input_kind == "typed_goal":
            if type(ledger.brief) is not Source or type(ledger.brief.text) is not str:
                result.update(verdict="UNKNOWN_MEANING_GOAL",
                              reason="typed Goal must retain its raw request brief")
                return result
            typed_request = _REQUEST_PATTERN.fullmatch(ledger.brief.text.strip())
            typed_action = ("explain" if typed_request and typed_request.group("verb") == "説明して"
                            else "paraphrase" if typed_request else None)
            if typed_action != action:
                result.update(verdict="UNKNOWN_MEANING_GOAL",
                              reason="typed request action differs from its raw brief")
                return result
        ok, reason = _ledger_contract(
            ledger, expected_event_span=expected_event_span,
            expected_event_atom=expected_event_atom,
            expected_brief_text=ledger.brief.text,
            expected_materials=materials,
        )
        if not ok:
            result.update(verdict="UNKNOWN_MEANING_GOAL", reason=reason)
            return result
        surface = atom_text(envelope.atom, narrator="") + "。"
        if action == "paraphrase":
            subject = envelope.atom.agent + "が"
            if not surface.startswith(subject):
                result.update(verdict="UNKNOWN_MEANING_SURFACE",
                              reason="licensed agent surface cannot be safely varied")
                return result
            # This single topic-marker variation is the only surface change
            # licensed here. A then checks the resulting proposition itself.
            surface = envelope.atom.agent + "は" + surface[len(subject):]
        verification = verify_event_realization(envelope, surface)
        projection = asdict(envelope.projection)
        source_binding = {
            "source_id": clause.span.source,
            "source_sha256": hashlib.sha256(documents[clause.span.source].encode("utf-8")).hexdigest(),
            "clause_id": clause.id,
            "event_identity": asdict(clause.event),
            "event_projection": projection,
        }
        semantic_goal = {
            "action": action,
            "obligations": sorted((item.kind, item.value, item.number)
                                  for item in ledger.obligations),
            "source_binding": source_binding,
        }
        result.update(
            verdict="DIAGNOSTIC_RAW_GOAL_BOUND" if input_kind == "raw_request" else "DIAGNOSTIC_TYPED_GOAL_BOUND",
            goal_interpreted=True,
            raw_goal_path_success=(input_kind == "raw_request"),
            request_goal={
                "components": ["question.Query" if query is not None else "typed_request_action",
                               "content_ir.Ledger", "meaning_bridge.SourceEventEnvelope"],
                "action": action,
                "query": asdict(query) if query is not None else None,
                "ledger": asdict(ledger),
                "binding": source_binding,
                "semantic_signature": digest(semantic_goal),
                "surface_policy": {
                    "explain": "licensed source event stated in one sentence",
                    "paraphrase": "only agent が→は topic-marker variation",
                    "surface_may_change": ["one licensed case/topic marker"],
                    "must_preserve": ["predicate", "agent/patient/recipient roles", "polarity", "grammatical tense"],
                    "conditions_and_exceptions": "must be absent; source bridge refuses rather than dropping them",
                    "scope": "source-attributed expression; no actual-world truth claim",
                },
            },
            packed_source_event=pack_source_event(envelope),
            evidence=[{**verification["evidence"], "source": verification["source"]}],
            source_inputs=[{"id": item.id, "text": item.text, "sha256": item.sha256}
                           for item in materials],
            realizations=[{"text": surface, "verification": verification}],
            scope="one source-bound plain assertion event and one explicit one-sentence request; diagnostic only",
        )
    except (BridgeError, ContentError, ValueError, UnicodeError) as error:
        result.update(verdict=getattr(error, "verdict", "UNKNOWN_MEANING_GOAL"),
                      reason=getattr(error, "reason", str(error)))
        # Even on a held path, retain the user-supplied source and its digest.
        if "source_inputs" not in result:
            try:
                result["source_inputs"] = [
                    {"id": item.id, "text": item.text, "sha256": item.sha256}
                    for item in _source_inputs(documents)
                ]
            except (ValueError, UnicodeError, AttributeError):
                pass
    return result


def source_goal_from_request(documents: Mapping[str, str], raw_request: str) -> dict:
    """Interpret the small raw request subset and bind it to one source event.

    ``documents`` are evidence only; only ``raw_request`` is sent to the
    request reader. Unknown, quoted, negated, summary, or conditioned requests
    remain held. The source-event reader independently refuses unread,
    conditional, exceptional, multi-event or instruction-like source text.
    """
    result = _base("raw_request")
    if type(raw_request) is not str:
        result.update(reason="raw request must be text")
        return result
    if len(raw_request) > MAX_REQUEST_CHARS:
        result.update(reason="raw request exceeds the diagnostic size bound")
        return result
    try:
        raw_request.encode("utf-8")
    except UnicodeError:
        result.update(verdict="UNKNOWN_MEANING_UTF8", reason="request contains a non-UTF8 surrogate")
        return result
    result["raw_request"] = raw_request
    # Question.Query remains a typed, source-attributed reading. Its broad
    # classifier is evidence, not an authorization gate or generated-surface test.
    query = question.read(raw_request)
    result["question_reading"] = asdict(query)
    phrase = raw_request.strip()
    match = _REQUEST_PATTERN.fullmatch(phrase)
    if match is None:
        result.update(reason="request is outside the anchored evidence-only one-sentence explain/rephrase grammar",
                      held_request_span={"start": 0, "end": len(raw_request), "text": raw_request})
        return result
    if query.speech_act.value.act not in ("request", "command"):
        result.update(reason="request reader did not identify a user request",
                      held_request_span={"start": 0, "end": len(raw_request), "text": raw_request})
        return result
    action = "explain" if match.group("verb") == "説明して" else "paraphrase"
    try:
        materials = _source_inputs(documents)
        result["source_inputs"] = [
            {"id": item.id, "text": item.text, "sha256": item.sha256}
            for item in materials
        ]
        ledger = _raw_ledger(raw_request, _LEDGER_TEMPLATE, materials)
    except (ContentError, ValueError, UnicodeError) as error:
        result.update(verdict=getattr(error, "verdict", "UNKNOWN_MEANING_GOAL"),
                      reason=getattr(error, "reason", str(error)),
                      held_request_span={"start": 0, "end": len(raw_request), "text": raw_request})
        return result
    result.update(_bound_diagnostic(documents, ledger, action, "raw_request",
                                    raw_request=raw_request, query=query))
    return result


def diagnose_typed_goal(documents: Mapping[str, str], ledger: Ledger, action: str) -> dict:
    """Run a gold/typed Goal diagnostic, never count it as raw interpretation."""
    return _bound_diagnostic(documents, ledger, action, "typed_goal")
