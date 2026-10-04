"""Source-bounded passive frames and passive adnominal refinements."""
from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import replace

from fugashi import Tagger

from ..semantic_ir import Clause, Role, Span, Variable
from . import (Construction, ConstructionContext, Reading, TypedNote, register)
from . import adnominal, diathesis


NAME = "gold_passive"
_I_E = frozenset("いきぎしじちぢにひびぴみりえけげせぜてでねへべぺめれ")
_A_ROW = {"う": "わ", "く": "か", "ぐ": "が", "す": "さ", "つ": "た",
          "ぬ": "な", "ぶ": "ば", "む": "ま", "る": "ら"}
_PASSIVE_SUFFIXES = ("られた", "れた", "られる", "れる")
_SAFE_UNSUPPORTED = frozenset(("ambiguous case role: に", "ambiguous case role: で",
                               "ambiguous frame role", "unrepresented source content",
                               "unlicensed role borrowing"))
_TIME_HEADS = ("時期", "時", "朝", "昼", "夕方", "夜", "午前", "午後",
               "今日", "昨日", "明日", "先月", "今月", "来月")
_MARKERS = ("によって", "により", "には", "では", "として", "と共に", "ともに",
            "について", "による", "において", "における", "に対して",
            "が", "は", "を", "に", "で", "へ", "から", "と")
_PUNCT = frozenset("。．.!！?？、，,・:：;；()（）「」『』【】〔〕［］｛｝")


def _surface(token) -> str:
    return getattr(token.token, "surface", str(token.token))


def _expanded_agent(ctx: ConstructionContext, role: Role) -> Role | None:
    sentence = ctx.sentence_span
    if (role.span.source != sentence.source or role.span.start < sentence.start
            or role.span.end > sentence.end or role.span.text !=
            sentence.text[role.span.start - sentence.start:role.span.end - sentence.start]):
        return None
    first = next((i for i, token in enumerate(ctx.tokens)
                  if token.start + sentence.start == role.span.start), None)
    if first is None or first < 2:
        return None
    verb, past, noun = ctx.tokens[first - 2:first + 1]
    vf = getattr(verb.token, "feature", None)
    pf = getattr(past.token, "feature", None)
    nf = getattr(noun.token, "feature", None)
    if (verb.end != past.start or past.end != noun.start
            or getattr(vf, "pos1", "") not in ("動詞", "形容詞")
            or _surface(past) != "た" or getattr(pf, "pos1", "") != "助動詞"
            or getattr(pf, "lemma", "") != "た"
            or "連体形" not in getattr(pf, "cForm", "")
            or getattr(nf, "pos1", "") not in ("名詞", "代名詞")):
        return None
    start = sentence.start + verb.start
    span = Span(sentence.source, start, role.span.end,
                sentence.text[verb.start:role.span.end - sentence.start])
    if not span.text.endswith(role.span.text) or not span.text:
        return None
    return Role("agent", span.text, span, "literal")


def _case_after(text: str, start: int, end: int) -> tuple[str, int] | None:
    local_end = end - start
    for marker in _MARKERS:
        if text.startswith(marker, local_end):
            return marker, end + len(marker)
    return None


def _time_term(term: str) -> bool:
    return bool(term) and term.endswith(_TIME_HEADS)


def _reader_patient_parts(ctx: ConstructionContext, role: Role):
    selected = [token for token in ctx.tokens
                if role.span.start <= ctx.sentence_span.start + token.start
                and ctx.sentence_span.start + token.end <= role.span.end]
    if ("の" not in role.span.text or not selected
            or ctx.sentence_span.start + selected[0].start != role.span.start
            or ctx.sentence_span.start + selected[-1].end != role.span.end
            or "".join(_surface(token) for token in selected) != role.span.text):
        return None
    features = [getattr(token.token, "feature", None) for token in selected]
    if (len(selected) != 3 or getattr(features[0], "pos1", "") not in ("名詞", "代名詞")
            or _surface(selected[1]) != "の"
            or getattr(features[1], "pos1", "") != "助詞"
            or getattr(features[2], "pos1", "") not in ("名詞", "代名詞")):
        return None
    base = ctx.sentence_span.start
    prefix_span = Span(role.span.source, role.span.start, base + selected[2].start,
                       ctx.sentence_text[selected[0].start:selected[2].start])
    head_span = Span(role.span.source, base + selected[2].start,
                     base + selected[2].end, _surface(selected[2]))
    return (Role("modifier", prefix_span.text, prefix_span, "literal"),
            Role("patient", head_span.text, head_span, "literal"))


def _covered(text: str, base: int, roles: tuple[Role, ...],
             marked: tuple[tuple[int, int], ...], predicate: tuple[int, int]) -> bool:
    intervals = [(role.span.start - base, role.span.end - base) for role in roles]
    intervals.extend(marked)
    intervals.append(predicate)
    intervals.sort()
    cursor = 0
    for start, end in intervals:
        if start < cursor or start < 0 or end <= start or end > len(text):
            return False
        if any(not char.isspace() and char not in _PUNCT
               and unicodedata.category(char)[0] not in ("P", "Z")
               for char in text[cursor:start]):
            return False
        cursor = end
    return not any(not char.isspace() and char not in _PUNCT
                   and unicodedata.category(char)[0] not in ("P", "Z")
                   for char in text[cursor:])


def _reader_roles(ctx: ConstructionContext, clause: Clause):
    text, base = ctx.sentence_text, ctx.sentence_span.start
    located = []
    for old in clause.roles:
        found = _case_after(text, base, old.span.end)
        if (old.span.source != ctx.sentence_span.source or old.span.start < base
                or old.span.end > ctx.sentence_span.end or old.span.start >= old.span.end
                or old.term != old.span.text
                or old.span.text != text[old.span.start-base:old.span.end-base]
                or found is None):
            return None
        marker, end = found
        located.append((old, marker, end))

    output = []
    marks = []
    agents = patients = 0
    for old, marker, marker_end in located:
        if marker in ("が", "は"):
            name = "patient"
        elif marker in ("によって", "により"):
            name = "agent"
        elif marker == "に" and _time_term(old.term):
            name = "time"
        elif marker == "を":
            name = "complement" if any(role.name == "patient" for role in output) else "patient"
        elif marker == "で" and old.name in ("place", "location"):
            name = old.name
        elif marker == "へ" and old.name in ("direction", "goal"):
            name = "direction"
        elif marker == "から" and old.name in ("source", "origin"):
            name = old.name
        else:
            return None
        if name == "patient":
            split = _reader_patient_parts(ctx, old)
            if split is not None:
                output.extend(split)
            else:
                output.append(Role(name, old.span.text, old.span, "literal"))
        else:
            output.append(Role(name, old.span.text, old.span, "literal"))
        marks.append((old.span.end-base, marker_end-base))
        agents += name == "agent"
        patients += name == "patient"
    if agents != 1 or patients != 1 or len({role.name for role in output}) != len(output):
        return None
    return tuple(sorted(output, key=lambda role: (role.span.start, role.span.end, role.name))), tuple(marks)


def _direct_passive_reading(ctx: ConstructionContext) -> tuple[Clause, ...]:
    sentence = ctx.sentence_span
    local = tuple(clause for clause in ctx.clauses
                  if clause.rule == "frame" and clause.span.source == sentence.source
                  and clause.span.start == sentence.start and clause.span.end == sentence.end)
    if len(local) != 1:
        return ()
    clause = local[0]
    if (clause.unsupported and any(reason not in _SAFE_UNSUPPORTED
                                   for reason in clause.unsupported)
            or clause.polarity != "+" or clause.modality != "assert"
            or clause.conditions or clause.exceptions or clause.exception_of):
        return ()
    base = sentence.start
    p0 = clause.predicate_span.start - base
    p1 = clause.predicate_span.end - base
    matches = [match for match in diathesis._form_at(ctx.sentence_text, p0, p1,
                                                      clause.predicate)
               if match[0] == "passive"]
    unique = set(matches)
    if len(unique) != 1:
        return ()
    _, start, end, form = next(iter(unique))
    roles_and_marks = _reader_roles(ctx, clause)
    if roles_and_marks is None:
        return ()
    roles, marks = roles_and_marks
    if not _covered(ctx.sentence_text, base, roles, marks, (start, end)):
        return ()
    time = "past" if form.endswith(("た", "ていた")) else "nonpast"
    digest = hashlib.sha256(
        (sentence.source + ":" + str(sentence.start) + ":" + str(start) + ":"
         + clause.predicate + ":gold_passive:" + ",".join(
             role.name + "=" + role.span.text for role in roles)).encode("utf-8")
    ).hexdigest()[:24]
    pred_span = Span(sentence.source, base + start, base + end,
                     ctx.sentence_text[start:end])
    return (replace(
        clause, id=digest, event=Variable("event_" + digest, "event"),
        predicate_span=pred_span, roles=roles, span=sentence, body_span=sentence,
        polarity="+", modality="assert", time=time, conditions=(), condition_spans=(),
        exceptions=(), exception_spans=(), exception_of="", rule=NAME, unsupported=(),
    ),)


def reads(ctx: ConstructionContext) -> Reading | None:
    """Compose adnominal recovery and bounded complete passive case frames."""
    if (len(ctx.tokens) > ctx.budget.max_tokens or len(ctx.clauses) > ctx.budget.max_steps
            or len(ctx.sentence_text) > 4096):
        return None
    prior = adnominal.reads(ctx)
    built: list[Clause] = list(_direct_passive_reading(ctx))
    notes: list[TypedNote] = []
    for clause in prior.clauses if isinstance(prior, Reading) else ():
        if (clause.polarity != "+" or clause.modality != "assert"
                or not clause.predicate_span.text.endswith(_PASSIVE_SUFFIXES)):
            continue
        agents = [role for role in clause.roles if role.name == "agent"]
        if len(agents) != 1:
            continue
        expanded = _expanded_agent(ctx, agents[0])
        if expanded is None:
            continue
        roles = tuple(expanded if role is agents[0] else role for role in clause.roles)
        digest = hashlib.sha256(
            (clause.id + ":" + NAME + ":" + str(expanded.span.start) + ":"
             + str(expanded.span.end)).encode("utf-8")
        ).hexdigest()[:24]
        built.append(replace(
            clause, id=digest, event=replace(clause.event, name="event_" + digest),
            roles=roles, rule=NAME, unsupported=(),
        ))
        notes.append(TypedNote(
            "passive_agent_modifier", expanded.span,
            "a source-bounded prenominal predicate modifies the passive agent noun",
        ))
    if not built:
        return None
    consumed = prior.consumed_spans if prior is not None else (ctx.sentence_span,)
    return Reading(tuple(built[:ctx.budget.max_clauses]), consumed,
                   tuple(notes[:ctx.budget.max_steps]))


def _licensed_passive_forms(predicate: str) -> frozenset[str]:
    """Build a closed passive-form set independently of the reader."""
    if predicate.endswith("する"):
        stem = predicate[:-2] + "され"
    elif predicate in ("来る", "くる"):
        stem = ("来" if predicate == "来る" else "こ") + "られ"
    elif len(predicate) > 1 and predicate.endswith("る") and predicate[-2] in _I_E:
        stem = predicate[:-1] + "られ"
    elif predicate and predicate[-1] in _A_ROW:
        stem = predicate[:-1] + _A_ROW[predicate[-1]] + "れ"
    else:
        return frozenset()
    return frozenset(stem + ending for ending in ("た", "る", "ている", "ていた", "ており"))


def _source_tokens(source: str):
    pos = 0
    found = []
    for token in Tagger()(source):
        surface = token.surface
        end = pos + len(surface)
        found.append((surface, pos, end, token.feature))
        pos = end
    return found if pos == len(source) else []


def _agent_modifier_shape(role: Role, source: str, tagged) -> bool:
    selected = [item for item in tagged
                if role.span.start <= item[1] and item[2] <= role.span.end]
    if (not selected or selected[0][1] != role.span.start
            or selected[-1][2] != role.span.end
            or "".join(item[0] for item in selected) != role.span.text
            or len(selected) < 3):
        return False
    first, past, head = selected[:3]
    if (first[3].pos1 not in ("動詞", "形容詞") or past[0] != "た"
            or past[3].pos1 != "助動詞" or past[3].lemma != "た"
            or "連体形" not in past[3].cForm
            or head[3].pos1 not in ("名詞", "代名詞")):
        return False
    for surface, _, _, feature in selected[2:]:
        if feature.pos1 in ("名詞", "代名詞", "接頭辞", "接尾辞"):
            continue
        if surface == "の" and feature.pos1 == "助詞" and feature.pos2 == "格助詞":
            continue
        return False
    return source[role.span.start:role.span.end] == role.span.text


def licenses(clause: Clause, source: str) -> bool:
    """Independently license passive case frames and relative agent modifiers."""
    if isinstance(clause, Clause) and clause.rule == NAME:
        return _licenses_direct(clause, source) or _licenses_relative(clause, source)
    return False


def _licenses_direct(clause: Clause, source: str) -> bool:
    if (not isinstance(source, str) or clause.unsupported or clause.polarity != "+"
            or clause.modality != "assert" or clause.time not in ("past", "nonpast")
            or clause.conditions or clause.condition_spans or clause.exceptions
            or clause.exception_spans or clause.exception_of
            or getattr(clause.event, "sort", None) != "event"):
        return False
    outer, body, pred = clause.span, clause.body_span, clause.predicate_span
    if (body != outer or outer.source != pred.source or outer.start < 0
            or outer.end > len(source) or outer.start >= outer.end
            or source[outer.start:outer.end] != outer.text
            or not outer.text.endswith(("。", "!", "！", "?", "？"))
            or pred.start < outer.start or pred.end > outer.end or pred.start >= pred.end
            or source[pred.start:pred.end] != pred.text
            or pred.text not in _licensed_passive_forms(clause.predicate)
            or clause.time != ("past" if pred.text.endswith(("た", "ていた")) else "nonpast")):
        return False
    if len({role.name for role in clause.roles}) != len(clause.roles):
        return False
    located = []
    descriptors = [role for role in clause.roles if role.name == "modifier"]
    patient_roles = [role for role in clause.roles if role.name == "patient"]
    if len(descriptors) > 1 or len(patient_roles) != 1:
        return False
    if descriptors:
        descriptor = descriptors[0]
        patient = patient_roles[0]
        if (descriptor.span.source != outer.source or descriptor.span.start < outer.start
                or descriptor.span.end > outer.end or descriptor.span.start >= descriptor.span.end
                or descriptor.rule != "literal" or descriptor.term != descriptor.span.text
                or not descriptor.span.text.endswith("の")
                or descriptor.span.end != patient.span.start
                or source[descriptor.span.start:descriptor.span.end] != descriptor.span.text):
            return False
    for role in clause.roles:
        if role.name == "modifier":
            continue
        if (role.span.source != outer.source or role.span.start < outer.start
                or role.span.end > outer.end or role.span.start >= role.span.end
                or source[role.span.start:role.span.end] != role.span.text
                or not isinstance(role.term, str)
                or role.rule != "literal"):
            return False
        expected_term = (_license_head(source, role.span.start, role.span.end)
                         if role.name == "patient" else None)
        if role.term != (expected_term or role.span.text):
            return False
        case = _license_case_after(source, role.span.end, outer.end)
        if case is None:
            return False
        marker, marker_end = case
        located.append((role, marker, marker_end))
    expected = [("modifier", descriptors[0].span.start, descriptors[0].span.end,
                 descriptors[0].span.text)] if descriptors else []
    marks = []
    agents = patients = 0
    for role, marker, marker_end in located:
        if marker in ("が", "は"):
            name = "patient"
        elif marker in ("によって", "により"):
            name = "agent"
        elif marker == "に" and _license_time_term(role.term):
            name = "time"
        elif marker == "を":
            name = "complement" if any(old[0] == "patient" for old in expected) else "patient"
        elif marker == "で" and role.name == "place":
            name = "place"
        elif marker == "へ" and role.name == "direction":
            name = "direction"
        elif marker == "から" and role.name in ("source", "origin"):
            name = role.name
        else:
            return False
        term = (_license_head(source, role.span.start, role.span.end)
                if name == "patient" else None) or role.span.text
        expected.append((name, role.span.start, role.span.end, term))
        marks.append((role.span.end, marker_end))
        agents += name == "agent"
        patients += name == "patient"
    actual = [(role.name, role.span.start, role.span.end, role.term) for role in clause.roles]
    if (agents != 1 or patients != 1 or sorted(expected) != sorted(actual)):
        return False
    covered = [(role.span.start, role.span.end) for role in clause.roles]
    covered.extend(marks)
    covered.append((pred.start, pred.end))
    return _license_coverage(source, outer.start, outer.end, covered)


def _license_case_after(source: str, start: int, limit: int) -> tuple[str, int] | None:
    for marker in _MARKERS:
        end = start + len(marker)
        if end <= limit and source.startswith(marker, start):
            return marker, end
    return None


def _license_time_term(term: str) -> bool:
    return bool(term) and term.endswith(_TIME_HEADS)


def _license_head(source: str, start: int, end: int) -> str | None:
    selected = [item for item in _source_tokens(source) if start <= item[1] and item[2] <= end]
    if (len(selected) != 3 or selected[0][1] != start or selected[-1][2] != end
            or "".join(item[0] for item in selected) != source[start:end]
            or "の" not in source[start:end]):
        return None
    if (selected[0][3].pos1 not in ("名詞", "代名詞")
            or selected[1][0] != "の" or selected[1][3].pos1 != "助詞"
            or selected[2][3].pos1 not in ("名詞", "代名詞")):
        return None
    return selected[2][0]


def _license_coverage(source: str, start: int, end: int,
                      intervals: list[tuple[int, int]]) -> bool:
    ordered = sorted(intervals)
    cursor = start
    for left, right in ordered:
        if left < cursor or right <= left or right > end:
            return False
        for char in source[cursor:left]:
            if not char.isspace() and unicodedata.category(char)[0] not in ("P", "Z"):
                return False
        cursor = right
    return all(char.isspace() or unicodedata.category(char)[0] in ("P", "Z")
               for char in source[cursor:end])


def _licenses_relative(clause: Clause, source: str) -> bool:
    if (not isinstance(clause, Clause) or clause.rule != NAME or not isinstance(source, str)
            or clause.unsupported or clause.polarity != "+" or clause.modality != "assert"
            or clause.time not in ("past", "nonpast") or clause.conditions
            or clause.condition_spans or clause.exceptions or clause.exception_spans
            or clause.exception_of or getattr(clause.event, "sort", None) != "event"):
        return False
    outer = clause.span
    body = clause.body_span
    pred = clause.predicate_span
    if (outer.source != pred.source or type(outer.start) is not int or type(outer.end) is not int
            or not 0 <= outer.start < outer.end <= len(source)
            or source[outer.start:outer.end] != outer.text or body != outer
            or pred.start < outer.start or pred.end > outer.end or pred.start >= pred.end
            or source[pred.start:pred.end] != pred.text
            or pred.text not in _licensed_passive_forms(clause.predicate)
            or not pred.text.endswith(_PASSIVE_SUFFIXES)
            or clause.time != ("past" if pred.text.endswith("た") else "nonpast")):
        return False
    patients = [role for role in clause.roles if role.name == "patient"]
    modifiers = [role for role in clause.roles if role.name == "modifier"]
    agents = [role for role in clause.roles if role.name == "agent"]
    if (len(clause.roles) != 3 or len(patients) != 1 or len(modifiers) != 1
            or len(agents) != 1):
        return False
    patient, modifier, agent = patients[0], modifiers[0], agents[0]
    if (patient.span != modifier.span or patient.term != modifier.term
            or patient.term != patient.span.text or patient.rule != "nominal"
            or modifier.rule != "nominal" or not patient.span.text
            or agent.rule != "literal" or agent.term != agent.span.text
        or agent.span.source != outer.source or patient.span.source != outer.source
            or agent.span.start < outer.start or agent.span.end > pred.start
            or patient.span.start != pred.end or patient.span.end > outer.end
            or source[agent.span.start:agent.span.end] != agent.span.text
            or source[patient.span.start:patient.span.end] != patient.span.text
            or source[agent.span.end:pred.start] != "に"
            or any(role.span.source != outer.source or role.span.start < outer.start
                   or role.span.end > outer.end or role.span.start >= role.span.end
                   or source[role.span.start:role.span.end] != role.span.text
                   for role in clause.roles)):
        return False
    tagged = _source_tokens(source)
    return _agent_modifier_shape(agent, source, tagged)


register(Construction(name=NAME, priority=61, reads=reads, licenses=licenses,
                      refines=("adnominal", "diathesis")))


__all__ = ("licenses", "reads")
