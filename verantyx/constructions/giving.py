"""Source-bounded frames for explicit Japanese giving and receiving clauses."""
from __future__ import annotations

import hashlib
import re

from ..semantic_ir import Clause, Role, Span, Variable
from . import Construction, ConstructionContext, Reading, TypedNote, register


_FORMS = (
    ("さしあげました", "さしあげる", "give", True),
    ("くださいました", "くださる", "give", True),
    ("いただきました", "いただく", "receive", True),
    ("もらいました", "もらう", "receive", True),
    ("あげました", "あげる", "give", True),
    ("くれました", "くれる", "give", True),
    ("くださいます", "くださる", "give", False),
    ("いただきます", "いただく", "receive", False),
    ("もらいます", "もらう", "receive", False),
    ("さしあげます", "さしあげる", "give", False),
    ("あげます", "あげる", "give", False),
    ("くれます", "くれる", "give", False),
    ("くださった", "くださる", "give", True),
    ("いただいた", "いただく", "receive", True),
    ("もらった", "もらう", "receive", True),
    ("さしあげた", "さしあげる", "give", True),
    ("あげた", "あげる", "give", True),
    ("くれた", "くれる", "give", True),
    ("くださる", "くださる", "give", False),
    ("いただく", "いただく", "receive", False),
    ("もらう", "もらう", "receive", False),
    ("さしあげる", "さしあげる", "give", False),
    ("あげる", "あげる", "give", False),
    ("くれる", "くれる", "give", False),
)
_PUNCT = "。！？!?"
_MENTION = re.compile(r"(?P<term>[^、。！？!?\s「」『』]+?)(?P<case>から|は|が|に|を)")
_CHECK_FORM_INFO = {
    "さしあげました": ("さしあげる", "give", True),
    "くださいました": ("くださる", "give", True),
    "いただきました": ("いただく", "receive", True),
    "もらいました": ("もらう", "receive", True),
    "あげました": ("あげる", "give", True),
    "くれました": ("くれる", "give", True),
    "くださいます": ("くださる", "give", False),
    "いただきます": ("いただく", "receive", False),
    "もらいます": ("もらう", "receive", False),
    "さしあげます": ("さしあげる", "give", False),
    "あげます": ("あげる", "give", False),
    "くれます": ("くれる", "give", False),
    "くださった": ("くださる", "give", True),
    "いただいた": ("いただく", "receive", True),
    "もらった": ("もらう", "receive", True),
    "さしあげた": ("さしあげる", "give", True),
    "あげた": ("あげる", "give", True),
    "くれた": ("くれる", "give", True),
    "くださる": ("くださる", "give", False),
    "いただく": ("いただく", "receive", False),
    "もらう": ("もらう", "receive", False),
    "さしあげる": ("さしあげる", "give", False),
    "あげる": ("あげる", "give", False),
    "くれる": ("くれる", "give", False),
}
_CHECK_MENTION = re.compile(r"([^、。！？!?\s「」『』]+?)(から|は|が|に|を)")


def _form(text: str) -> dict[str, object] | None:
    """Recognize only a positive finite ending from the closed giving list."""
    end = len(text)
    while end and text[end - 1] in _PUNCT:
        end -= 1
    while end and text[end - 1].isspace():
        end -= 1
    core = text[:end]
    for surface, lemma, direction, past in _FORMS:
        if not core.endswith(surface):
            continue
        start = len(core) - len(surface)
        joined = start > 0 and core[start - 1] in "てで"
        return {
            "surface": surface,
            "lemma": lemma,
            "direction": direction,
            "past": past,
            "start": start,
            "end": end,
            "joined": joined,
        }
    return None


def _mentions(text: str, source_start: int, source: str) -> list[tuple[str, str, Span]]:
    found = []
    for match in _MENTION.finditer(text):
        value = match.group("term")
        if not value:
            continue
        start = source_start + match.start("term")
        end = source_start + match.end("term")
        found.append((value, match.group("case"), Span(source, start, end, value)))
    return found


def _pick_roles(mentions: list[tuple[str, str, Span]], direction: str):
    if len(mentions) != 3:
        return None
    subjects = [m for m in mentions if m[1] in ("は", "が")]
    objects = [m for m in mentions if m[1] == "を"]
    if len(subjects) != 1 or len(objects) != 1:
        return None
    subject = subjects[0]
    patient = objects[0]
    if direction == "give":
        recipients = [m for m in mentions if m[1] == "に"]
        if len(recipients) != 1:
            return None
        donor, recipient = subject, recipients[0]
    else:
        donors = [m for m in mentions if m[1] in ("に", "から")]
        if len(donors) != 1:
            return None
        donor, recipient = donors[0], subject
    if len({donor[2], recipient[2], patient[2]}) != 3:
        return None
    return donor, patient, recipient


def _covered(text: str, mentions, roles, form, predicate_span: Span | None,
             sentence_start: int, joined: bool) -> bool:
    spans: list[tuple[int, int]] = []
    for _, case, span in mentions:
        left, right = span.start - sentence_start, span.end - sentence_start
        spans.append((left, right))
        spans.append((right, right + len(case)))
    if joined:
        if predicate_span is None:
            return False
        left = predicate_span.start - sentence_start
        right = int(form["end"])
        spans.append((left, right))
    else:
        spans.append((int(form["start"]), int(form["end"])))
    spans.sort()
    covered_until = 0
    for left, right in spans:
        if left > covered_until:
            gap = text[covered_until:left]
            if any(not ch.isspace() and ch not in _PUNCT for ch in gap):
                return False
        covered_until = max(covered_until, right)
    tail = text[covered_until:]
    return not any(not ch.isspace() and ch not in _PUNCT for ch in tail)


def _event_id(source: str, start: int, end: int, predicate: str) -> str:
    value = f"{source}\0{start}\0{end}\0{predicate}".encode("utf-8")
    return hashlib.blake2b(value, digest_size=12).hexdigest()


def _checker_form(text: str) -> tuple[str, str, bool, bool, int, int] | None:
    """A separate finite-form scan used only by the independent licensor."""
    stop = len(text)
    while stop and (text[stop - 1].isspace() or text[stop - 1] in "。！？!?"):
        stop -= 1
    stem = text[:stop]
    for ending in sorted(_CHECK_FORM_INFO, key=len, reverse=True):
        if stem.endswith(ending):
            start = len(stem) - len(ending)
            lemma, direction, past = _CHECK_FORM_INFO[ending]
            embedded = start > 0 and stem[start - 1] in "てで"
            return ending, lemma, direction == "give", past, start, stop
    return None


def _checker_mentions(text: str, absolute_start: int):
    result = []
    for match in _CHECK_MENTION.finditer(text):
        result.append((match.group(1), match.group(2),
                       absolute_start + match.start(1), absolute_start + match.end(1)))
    return result


def _checker_roles(mentions, gives: bool):
    if len(mentions) != 3:
        return None
    subjects = [m for m in mentions if m[1] == "は" or m[1] == "が"]
    themes = [m for m in mentions if m[1] == "を"]
    if len(subjects) != 1 or len(themes) != 1:
        return None
    subject, theme = subjects[0], themes[0]
    if gives:
        beneficiaries = [m for m in mentions if m[1] == "に"]
        if len(beneficiaries) != 1:
            return None
        giver, receiver = subject, beneficiaries[0]
    else:
        sources = [m for m in mentions if m[1] == "に" or m[1] == "から"]
        if len(sources) != 1:
            return None
        giver, receiver = sources[0], subject
    if len({(giver[2], giver[3]), (receiver[2], receiver[3]), (theme[2], theme[3])}) != 3:
        return None
    return {"agent": giver, "patient": theme, "recipient": receiver}


def _checker_covers(text: str, mentions, ending_start: int, ending_end: int,
                    predicate_span: Span, absolute_start: int, embedded: bool) -> bool:
    regions = []
    for _, particle, begin, end in mentions:
        regions.extend(((begin - absolute_start, end - absolute_start),
                        (end - absolute_start, end - absolute_start + len(particle))))
    if embedded:
        regions.append((predicate_span.start - absolute_start, ending_end))
    else:
        regions.append((ending_start, ending_end))
    regions.sort()
    edge = 0
    for start, end in regions:
        if start < 0 or end > len(text) or start > end:
            return False
        if start > edge and any(ch not in " \t\r\n　。！？!?" for ch in text[edge:start]):
            return False
        edge = max(edge, end)
    return not any(ch not in " \t\r\n　。！？!?" for ch in text[edge:])


def reads(ctx: ConstructionContext) -> Reading | None:
    """Build one frame only when each participant has an overt case-marked span."""
    if (len(ctx.tokens) > ctx.budget.max_tokens
            or len(ctx.clauses) > ctx.budget.max_clauses
            or len(ctx.sentence_text) > ctx.budget.max_steps):
        return None
    sentence = ctx.sentence_text
    span = ctx.sentence_span
    if sentence != span.text:
        return None
    form = _form(sentence)
    if form is None:
        return None

    native = [c for c in ctx.clauses
              if c.span.source == span.source and c.span.start < span.end and span.start < c.span.end]
    if native and not any(c.unsupported for c in native):
        return None
    if len(native) > 1:
        return Reading((), (span,), (TypedNote("ambiguity", span, "giving frame has multiple native events"),))
    base = native[0] if native else None
    if base and (base.conditions or base.exceptions or base.polarity != "+"
                 or base.modality != "assert"):
        return Reading((), (span,), (TypedNote("ambiguity", span, "giving frame has scoped or non-asserted form"),))
    if bool(form["joined"]) and base is None:
        return Reading((), (span,), (TypedNote("ambiguity", span, "embedded action has no licensed predicate span"),))

    mentions = _mentions(sentence, span.start, span.source)
    rolespec = _pick_roles(mentions, str(form["direction"]))
    if rolespec is None:
        return Reading((), (span,), (TypedNote("ambiguity", span, "donor, recipient, or patient is not explicit"),))
    donor, patient, recipient = rolespec
    if base:
        predicate = base.predicate
        predicate_span = base.predicate_span
        event = base.event
        sovereign, family = base.sovereign, base.family
    else:
        predicate = str(form["lemma"])
        predicate_span = Span(span.source, span.start + int(form["start"]),
                              span.start + int(form["end"]),
                              sentence[int(form["start"]):int(form["end"])])
        identifier = _event_id(span.source, span.start, span.end, predicate)
        event = Variable("event_" + identifier, "event")
        sovereign = family = "document"
    if not form["joined"]:
        predicate_span = Span(span.source, span.start + int(form["start"]),
                              span.start + int(form["end"]),
                              sentence[int(form["start"]):int(form["end"])])
    if not _covered(sentence, mentions, rolespec, form, predicate_span, span.start,
                    bool(form["joined"])):
        return Reading((), (span,), (TypedNote("ambiguity", span, "unparsed material remains in giving clause"),))
    if (not form["joined"] and base is None and predicate != str(form["lemma"])):
        return None

    predicate = str(form["lemma"]) if not form["joined"] else predicate
    identifier = _event_id(span.source, span.start, span.end, predicate)
    clause = Clause(
        id=identifier,
        event=event,
        predicate=predicate,
        predicate_span=predicate_span,
        roles=(Role("agent", donor[0], donor[2], "literal"),
               Role("patient", patient[0], patient[2], "literal"),
               Role("recipient", recipient[0], recipient[2], "literal")),
        span=span,
        body_span=span,
        polarity="+",
        modality="assert",
        time="past" if form["past"] else "",
        rule="giving",
        sovereign=sovereign,
        family=family,
    )
    return Reading((clause,), (span,), ())


def licenses(clause: Clause, full_source: str) -> bool:
    """Check the giving morphology, exact source offsets, and directional roles anew."""
    if clause.rule != "giving" or clause.polarity != "+" or clause.modality != "assert":
        return False
    if clause.conditions or clause.exceptions or clause.exception_of:
        return False
    if (clause.span.start < 0 or clause.span.end > len(full_source)
            or clause.span.start >= clause.span.end
            or full_source[clause.span.start:clause.span.end] != clause.span.text):
        return False
    text = clause.span.text
    form = _checker_form(text)
    if form is None:
        return False
    ending, lemma, gives, past, ending_start, ending_end = form
    if clause.time != ("past" if past else ""):
        return False
    source = clause.span.source
    if clause.body_span != clause.span:
        return False
    roles = {role.name: role for role in clause.roles}
    if set(roles) != {"agent", "patient", "recipient"}:
        return False
    if len(clause.roles) != 3:
        return False
    mentions = _checker_mentions(text, clause.span.start)
    expected = _checker_roles(mentions, gives)
    if expected is None:
        return False
    for name, role in roles.items():
        value, case, start, end = expected[name]
        if (role.term != value or role.rule != "literal" or role.span.source != source
                or role.span.start != start or role.span.end != end
                or role.span.text != value):
            return False
        local_end = role.span.end - clause.span.start
        if text[local_end:local_end + len(case)] != case:
            return False
    embedded = ending_start > 0 and text[ending_start - 1] in "てで"
    if embedded:
        ps = clause.predicate_span
        if (ps.source != source or ps.start < clause.span.start or ps.end > clause.span.end
                or ps.start >= ps.end or full_source[ps.start:ps.end] != ps.text):
            return False
        region_start = ps.start - clause.span.start
        region_end = ending_end
        region = text[region_start:region_end]
        suffix = ending
        if not (region.endswith(suffix) and len(region) > len(suffix)
                and region[-len(suffix) - 1] in "てで"):
            return False
        if not clause.predicate:
            return False
    else:
        if clause.predicate != lemma:
            return False
        expected_start = clause.span.start + ending_start
        expected_end = clause.span.start + ending_end
        if (clause.predicate_span.source != source or clause.predicate_span.start != expected_start
                or clause.predicate_span.end != expected_end
                or clause.predicate_span.text != text[ending_start:ending_end]):
            return False
    return _checker_covers(text, mentions, ending_start, ending_end, clause.predicate_span,
                           clause.span.start, embedded)


register(Construction(
    name="giving",
    priority=70,
    reads=reads,
    licenses=licenses,
    refines=("frame",),
))


__all__ = ("licenses", "reads")
