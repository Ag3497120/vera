"""A source-bounded reader for explicit Japanese giving constructions."""
from __future__ import annotations

from dataclasses import replace
import re

from ..semantic_ir import Clause, Role, Span
from . import Construction, ConstructionContext, Reading, TokenSpan, TypedNote, register


NAME = "gold_giving"
_AUX = {
    "上げる": "give",
    "あげる": "give",
    "呉れる": "give",
    "くれる": "give",
    "貰う": "receive",
    "もらう": "receive",
}
_ALLOWED_UNSUPPORTED = frozenset((
    "unrepresented source content",
    "multiple predicates need explicit clause scope",
    "ambiguous frame role",
    "ambiguous case role: に",
    "ambiguous case role: から",
    "unlicensed role borrowing",
    "ambiguous construction readings: giving, zero_subject",
))
_TIME_PREFIXES = (
    "先週", "昨日", "今日", "今週", "先月", "昨年", "前年", "前日", "先日",
    "翌日", "前週", "翌週", "今朝", "今年",
)
_PUNCT = frozenset("、。，．！？!?;；:： \t\r\n")


def _surface(text: str, token: TokenSpan) -> str:
    return text[token.start:token.end]


def _lemma(token: TokenSpan) -> str:
    feature = getattr(token.token, "feature", None)
    return str(getattr(feature, "lemma", "") or "")


def _is_verb(token: TokenSpan) -> bool:
    return str(getattr(token.token, "pos", "")).startswith("動詞")


def _event_nominal(token: TokenSpan) -> bool:
    feature = getattr(token.token, "feature", None)
    return ("サ変可能" in str(getattr(token.token, "pos", ""))
            or getattr(feature, "pos2", "") == "サ変可能")


def _span(source: str, base: int, text: str, start: int, end: int) -> Span:
    return Span(source, base + start, base + end, text[start:end])


def _time_prefix_end(text: str) -> int:
    for word in _TIME_PREFIXES:
        if text.startswith(word):
            end = len(word)
            if text[end:end + 1] in ("、", ","):
                end += 1
            return end
    return 0


def _reader_nominal_modifier(text: str) -> bool:
    if not text or any(char in _PUNCT for char in text):
        return False
    return "の" in text or "な" in text or bool(re.search(r"[ぁ-ん]$", text))


def _trailing_form(tokens: tuple[TokenSpan, ...], text: str, aux_index: int) -> bool:
    """Require a positive finite ending after the benefactive auxiliary."""
    tail = "".join(_surface(text, token) for token in tokens[aux_index + 1:])
    tail = tail.rstrip("。．.!！?？\t\r\n ")
    if not tail:
        return True
    return tail in ("た", "る", "ます", "ました", "まし", "です")


def _candidate_span(
    clauses: tuple[Clause, ...], names: tuple[str, ...], marker_start: int,
) -> Span | None:
    found = [
        role.span
        for clause in clauses
        for role in clause.roles
        if role.name in names and role.span.end == marker_start
        and role.span.start < role.span.end
    ]
    unique = {(span.source, span.start, span.end, span.text): span for span in found}
    return next(iter(unique.values())) if len(unique) == 1 else None


def _phrase_start(
    text: str, tokens: tuple[TokenSpan, ...], marker_index: int,
    lower: int = 0,
) -> int:
    """Bound a short argument after the nearest prior case/topic separator."""
    start = lower
    for index in range(marker_index):
        if tokens[index].start < lower:
            continue
        surface = _surface(text, tokens[index])
        if surface in ("、", ",", "は", "が", "に", "から", "へ", "で", "と", "を"):
            start = tokens[index].end
    while start < tokens[marker_index].start and text[start:start + 1] in _PUNCT:
        start += 1
    return start


def _marker_indices(
    text: str, tokens: tuple[TokenSpan, ...], surface: str, before: int,
) -> tuple[int, ...]:
    return tuple(i for i in range(before) if _surface(text, tokens[i]) == surface)


def _has_verb_between(
    tokens: tuple[TokenSpan, ...], start: int, end: int,
) -> bool:
    return any(_is_verb(tokens[i]) for i in range(start, end))


def _reader_coverage(
    text: str, spans: tuple[tuple[int, int], ...], time_end: int,
) -> bool:
    """Reject any lexical material the rule did not assign a source role."""
    ordered = sorted((a, b) for a, b in spans if a < b)
    cursor = 0
    for start, end in ordered:
        if start < cursor:
            return False
        gap = text[cursor:start]
        if any(char not in _PUNCT for char in gap):
            if not (cursor == 0 and time_end == start and time_end > 0):
                return False
        cursor = end
    gap = text[cursor:]
    if any(char not in _PUNCT for char in gap):
        return False
    if time_end and text[:time_end].strip("、,") not in _TIME_PREFIXES:
        return False
    return True


def _find_reading(ctx: ConstructionContext) -> Reading | None:
    text = ctx.sentence_text
    tokens = ctx.tokens
    sentence = ctx.sentence_span
    if (len(tokens) > ctx.budget.max_tokens or len(ctx.clauses) > ctx.budget.max_clauses
            or not tokens or sentence.text != text):
        return None

    matches: list[tuple[int, int, str, bool]] = []
    for index, token in enumerate(tokens):
        kind = _AUX.get(_lemma(token)) or _AUX.get(_surface(text, token))
        if kind is None or not _trailing_form(tokens, text, index):
            continue
        if index >= 2 and _surface(text, tokens[index - 1]) in ("て", "で") and _is_verb(tokens[index - 2]):
            matches.append((index - 2, index, kind, True))
        elif kind == "receive" or kind == "give":
            matches.append((index, index, kind, False))
    if len(matches) != 1:
        return None

    root_index, aux_index, kind, benefactive = matches[0]
    if not _is_verb(tokens[root_index]):
        return None
    root = tokens[root_index]
    root_start, root_end = root.start, root.end
    if not _trailing_form(tokens, text, aux_index):
        return None

    clause_candidates = tuple(
        clause for clause in ctx.clauses
        if clause.span.start == sentence.start and clause.span.end == sentence.end
        and clause.predicate_span.start == sentence.start + root_start
    )
    if not clause_candidates or not all(c.unsupported for c in clause_candidates):
        return None
    if any(not _ALLOWED_UNSUPPORTED.issuperset(c.unsupported) for c in clause_candidates):
        return None
    if any(c.conditions or c.exceptions or c.exception_of for c in clause_candidates):
        return None
    base = min(clause_candidates, key=lambda c: (len(c.unsupported), c.rule, c.id))
    if base.polarity != "+" or base.modality != "assert":
        return None

    object_markers = _marker_indices(text, tokens, "を", root_index)
    if not object_markers:
        return None
    object_index = object_markers[-1]

    if kind == "give":
        role_surface = "に"
        role_indices = _marker_indices(text, tokens, role_surface, object_index)
        role_index = next((i for i in reversed(role_indices)
                           if not _has_verb_between(tokens, i + 1, object_index)), None)
    else:
        sources = _marker_indices(text, tokens, "から", object_index)
        datives = _marker_indices(text, tokens, "に", object_index)
        role_index = sources[-1] if sources else next(
            (i for i in reversed(datives)
             if not _has_verb_between(tokens, i + 1, object_index)
             or (i + 1 < object_index and _surface(text, tokens[i + 1]) in ("、", ","))),
            None,
        )
        role_surface = _surface(text, tokens[role_index]) if role_index is not None else ""
    if role_index is None:
        return None
    if not benefactive and kind == "receive" and role_surface == "から":
        return None

    subject_markers = tuple(
        i for i in range(role_index)
        if _surface(text, tokens[i]) in ("は", "が")
    )
    if not subject_markers:
        return None
    subject_index = subject_markers[-1]
    role_marker_start = sentence.start + tokens[role_index].start
    subject_marker_start = sentence.start + tokens[subject_index].start

    if kind == "give":
        subject_role = "agent"
        other_names = ("recipient", "ambiguous")
    else:
        subject_role = "recipient"
        other_names = ("source", "agent")

    subject_span = _candidate_span(clause_candidates, (subject_role, "agent", "recipient"), subject_marker_start)
    if subject_span is None:
        subject_start = _phrase_start(text, tokens, subject_index, _time_prefix_end(text))
        subject_span = _span(sentence.source, sentence.start, text, subject_start, subject_marker_start)
    if subject_span.end != sentence.start + subject_marker_start:
        return None

    role_span = _candidate_span(clause_candidates, other_names, role_marker_start)
    if role_span is None:
        role_start = _phrase_start(text, tokens, role_index, subject_span.end - sentence.start)
        role_span = _span(sentence.source, sentence.start, text, role_start, role_marker_start)
    if role_span.start < subject_span.end or role_span.end != sentence.start + role_marker_start:
        return None
    if kind == "give" and "ため" in role_span.text:
        return None

    patient_start = tokens[role_index].end
    while patient_start < tokens[object_index].start and text[patient_start:patient_start + 1] in _PUNCT:
        patient_start += 1
    patient_end = tokens[object_index].start
    if patient_start >= patient_end:
        return None
    patient_candidates = [
        role for clause in clause_candidates for role in clause.roles
        if role.name == "patient" and role.term == role.span.text
        and role.span.start >= sentence.start + patient_start
        and role.span.end == sentence.start + patient_end
    ]
    patient_sources = {(role.span.source, role.span.start, role.span.end, role.span.text): role
                       for role in patient_candidates}
    head = next((token for token in reversed(tokens[:object_index])
                 if token.start >= patient_start and token.end == patient_end
                 and str(getattr(token.token, "pos", "")).startswith("名詞")), None)
    if head is None:
        return None
    patient_source = next(iter(patient_sources.values())) if len(patient_sources) == 1 else None
    preserve_event_phrase = patient_source is not None and _event_nominal(head)
    patient_span = (patient_source.span if preserve_event_phrase
                    else _span(sentence.source, sentence.start, text, head.start, head.end))
    patient_rule = (patient_source.rule if preserve_event_phrase
                    and patient_source.rule in ("frame", "literal") else "literal")
    patient_term = patient_span.text
    modifier_text = text[patient_start:patient_span.start - sentence.start]
    note = ()
    if modifier_text:
        if not _reader_nominal_modifier(modifier_text):
            return None
        note = (TypedNote(
            "nominal_modifier",
            _span(sentence.source, sentence.start, text, patient_start, head.start),
            "source-bounded patient modifier",
        ),)
    object_particle = tokens[object_index]
    connector_spans: list[tuple[int, int]] = []
    if benefactive:
        connector = tokens[aux_index - 1]
        connector_spans.append((connector.start, connector.end))
    aux_span = tokens[aux_index]
    tail_tokens = tuple(
        token for token in tokens[aux_index + 1:]
        if _surface(text, token) not in ("。", "．", ".", "!", "！", "?", "？")
    )
    if any(_surface(text, t) not in ("た", "る", "ます", "まし", "です") for t in tail_tokens):
        return None

    subj_marker = tokens[subject_index]
    role_marker = tokens[role_index]
    if kind == "give":
        role_term = role_span.text
        subject_term = subject_span.text
        roles = (
            Role("agent", subject_term, subject_span, "literal"),
            Role("patient", patient_term, patient_span, patient_rule),
            Role("recipient", role_term, role_span, "literal"),
        )
    else:
        roles = (
            Role("agent", role_span.text, role_span, "literal"),
            Role("patient", patient_term, patient_span, patient_rule),
            Role("recipient", subject_span.text, subject_span, "literal"),
        )

    ranges = [
        (subject_span.start - sentence.start, subject_span.end - sentence.start),
        (subj_marker.start, subj_marker.end),
        (role_span.start - sentence.start, role_span.end - sentence.start),
        (role_marker.start, role_marker.end),
        (patient_start, patient_end),
        (object_particle.start, object_particle.end),
        *(((root_start, root_end),) if benefactive else ()),
        (aux_span.start, aux_span.end),
        *connector_spans,
        *((token.start, token.end) for token in tail_tokens),
    ]
    for token in tokens[aux_index + 1:]:
        if _surface(text, token) in ("。", "．", ".", "!", "！", "?", "？"):
            ranges.append((token.start, token.end))
    time_end = _time_prefix_end(text)
    if not _reader_coverage(text, tuple(ranges), time_end):
        return None

    if benefactive:
        predicate = base.predicate
    else:
        predicate = "あげる"
    predicate_span = _span(sentence.source, sentence.start, text, root_start, root_end)
    result = replace(
        base,
        id=base.id + ":gold_giving",
        predicate=predicate,
        predicate_span=predicate_span,
        roles=roles,
        span=sentence,
        body_span=sentence,
        rule=NAME,
        unsupported=(),
    )
    return Reading((result,), (sentence,), note)


def reads(ctx: ConstructionContext) -> Reading | None:
    """Read a narrowly licensed giving/receiving form from explicit cases."""
    return _find_reading(ctx)


def _surface_after(text: str, start: int, endings: tuple[str, ...]) -> str | None:
    for ending in endings:
        if text.startswith(ending, start):
            return ending
    return None


def _license_complete(body: str, ranges: tuple[tuple[int, int], ...]) -> bool:
    """Independently reject lexical gaps after licensing each role marker."""
    cursor = 0
    for start, end in sorted(ranges):
        if start < cursor or start > len(body) or end > len(body):
            return False
        gap = body[cursor:start]
        if any(char not in _PUNCT for char in gap):
            prefix = body[:start]
            recognized = next((word for word in _TIME_PREFIXES if prefix.startswith(word)), None)
            if not recognized or prefix[len(recognized):].strip("、,"):
                return False
        cursor = end
    gap = body[cursor:]
    return all(char in _PUNCT for char in gap)


def licenses(clause: Clause, full_source: str) -> bool:
    """Verify the source string again without calling or sharing the reader."""
    if not isinstance(full_source, str) or clause.rule != NAME:
        return False
    if (clause.span.start < 0 or clause.span.end > len(full_source)
            or clause.span.start >= clause.span.end):
        return False
    body = full_source[clause.span.start:clause.span.end]
    if body != clause.span.text or clause.polarity != "+" or clause.modality != "assert":
        return False
    if clause.conditions or clause.exceptions or clause.exception_of:
        return False
    if not clause.predicate_span.text or clause.predicate_span.source != clause.span.source:
        return False
    if not (clause.span.start <= clause.predicate_span.start < clause.predicate_span.end <= clause.span.end):
        return False
    if clause.predicate_span.text != full_source[clause.predicate_span.start:clause.predicate_span.end]:
        return False

    roles = {role.name: role for role in clause.roles}
    if set(roles) != {"agent", "patient", "recipient"} or len(clause.roles) != 3:
        return False
    if any(role.rule not in ("literal", "frame") or not role.term or role.term != role.span.text
           for role in clause.roles):
        return False
    for role in clause.roles:
        if (role.span.source != clause.span.source or role.span.start < clause.span.start
                or role.span.end > clause.span.end or role.span.start >= role.span.end
                or role.span.text != full_source[role.span.start:role.span.end]):
            return False

    local = lambda span: (span.start - clause.span.start, span.end - clause.span.start)
    agent_start, agent_end = local(roles["agent"].span)
    patient_start, patient_end = local(roles["patient"].span)
    recipient_start, recipient_end = local(roles["recipient"].span)
    predicate_start, predicate_end = local(clause.predicate_span)
    if len({(agent_start, agent_end), (patient_start, patient_end), (recipient_start, recipient_end)}) != 3:
        return False

    suffixes = (
        "てあげ", "て上げ", "であげ", "で上げ", "てくれ", "でくれ",
        "てもら", "でもら", "て貰", "で貰",
    )
    after_predicate = body[predicate_end:]
    benefactive = next((s for s in suffixes if after_predicate.startswith(s)), None)
    if benefactive:
        aux_form = "receive" if ("もら" in benefactive or "貰" in benefactive) else "give"
        tail = after_predicate[len(benefactive):]
        if tail not in ("った。", "った", "た。", "た", "る。", "る", "ました。", "ました", "ます。", "ます"):
            return False
        if clause.predicate in ("もらう", "あげる", "くれる"):
            return False
    else:
        direct = re.match(r"(?:もらっ?|貰っ?|あげ|上げ|くれ|呉れ)(?:た|る|ました|ます)?[。．.!！?？]?\Z", body[predicate_start:])
        if not direct:
            return False
        aux_form = "receive" if body[predicate_start:].startswith(("もら", "貰")) else "give"

    if aux_form == "give":
        if clause.predicate in ("もらう",):
            return False
        subject = roles["agent"].span
        target = roles["recipient"].span
        target_marker = "に"
    else:
        if clause.predicate not in ("あげる", "もらう") and not benefactive:
            return False
        subject = roles["recipient"].span
        target = roles["agent"].span
        target_marker = "から" if full_source[target.end:target.end + 2] == "から" else "に"

    subject_local = local(subject)
    target_local = local(target)
    patient_local = local(roles["patient"].span)
    subject_marker = _surface_after(body, subject_local[1], ("は", "が"))
    if subject_marker is None:
        return False
    target_mark = _surface_after(body, target_local[1], (target_marker,))
    patient_mark = _surface_after(body, patient_local[1], ("を",))
    if target_mark is None or patient_mark is None:
        return False

    phrase_start = target_local[1] + len(target_mark)
    while phrase_start < patient_local[0] and body[phrase_start:phrase_start + 1] in _PUNCT:
        phrase_start += 1
    modifier = body[phrase_start:patient_local[0]]
    if modifier:
        if (any(char in _PUNCT for char in modifier)
                or not ("の" in modifier or "な" in modifier
                        or re.search(r"[ぁ-ん]$", modifier))):
            return False

    root_range = (predicate_start, predicate_end)
    if benefactive:
        link_start = predicate_end
        link_end = predicate_end + (1 if after_predicate.startswith(("て", "で")) else 0)
        if link_end == link_start:
            return False
        aux_start = link_start + 1
        aux_end = body.find("た", aux_start)
        if aux_end == -1:
            aux_end = body.find("る", aux_start)
        if aux_end == -1:
            return False
        aux_end += 1
        ending = len(body.rstrip("。．.!！?？"))
        aux_range = (aux_start, ending)
    else:
        aux_range = (predicate_start, len(body.rstrip("。．.!！?？")))
    marker_ranges = (
        (subject_local[1], subject_local[1] + len(subject_marker)),
        (target_local[1], target_local[1] + len(target_mark)),
        (patient_local[1], patient_local[1] + len(patient_mark)),
    )
    patient_phrase = (phrase_start, patient_local[1])
    if benefactive:
        coverage = (subject_local, target_local, patient_phrase, *marker_ranges,
                    root_range, (link_start, link_end), aux_range)
    else:
        coverage = (subject_local, target_local, patient_phrase, *marker_ranges, aux_range)
    return _license_complete(body, coverage)


register(Construction(
    name=NAME,
    priority=75,
    reads=reads,
    licenses=licenses,
    refines=("frame", "giving", "zero_subject"),
))
