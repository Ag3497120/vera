"""Source-bounded readings for light verbs and nominal case frames."""
from __future__ import annotations

import hashlib
from bisect import bisect_left

from . import Construction, ConstructionContext, Reading, TypedNote, register
from ..semantic_ir import Clause, Role, Span, Variable


_STATIC = {"属する": ("member", "group"), "位置する": ("entity", "location")}
_NOMINALIZERS = frozenset(("場合", "際", "こと", "事", "ため", "為", "時", "よう", "もの", "ところ", "わけ"))
_SCOPE_MARKERS = _NOMINALIZERS | frozenset(("なら", "ならば", "たら", "れば", "とき"))
_NP_LINKS = frozenset(("の", "・", "＝", "=", "-", "－", "/", "／"))
_COORDINATORS = frozenset(("と", "や", "及び", "および", "並びに", "ならびに", "または", "又は", "あるいは"))


def _feature(token, name):
    return getattr(getattr(token, "feature", None), name, "") or ""


def _surface(token):
    return getattr(token, "surface", "") or ""


def _atom(token):
    return _feature(token, "pos1") in ("名詞", "代名詞", "接頭辞", "接尾辞")


def _noun_phrases(tokens):
    """Index maximal adjacent nominal groups once, for bounded left lookups."""
    starts = [None] * len(tokens)
    ends = [None] * len(tokens)
    i = 0
    while i < len(tokens):
        if not _atom(tokens[i].token):
            i += 1
            continue
        first = i
        last = i
        while last + 1 < len(tokens):
            nxt = last + 1
            if _atom(tokens[nxt].token):
                last = nxt
                continue
            if (nxt + 1 < len(tokens) and _surface(tokens[nxt].token) in _NP_LINKS
                    and _atom(tokens[nxt + 1].token)):
                last = nxt + 1
                continue
            break
        starts[first] = last
        has_core_noun = any(_feature(tokens[k].token, "pos1") in ("名詞", "代名詞")
                            for k in range(first, last + 1))
        ends[last] = (first, has_core_noun)
        i = last + 1
    return starts, ends


def _phrase_left(tokens, ends, end):
    if end <= 0 or ends[end - 1] is None:
        return None
    start, has_core_noun = ends[end - 1]
    # Avoid treating a suffix by itself as a typed entity.
    if not has_core_noun:
        return None
    return start, end


def _phrase_head_right(tokens, starts, start):
    if start >= len(tokens) or starts[start] is None:
        return None
    end = starts[start] + 1
    # A genitive after the first head belongs to the following phrase.
    for i in range(start + 1, end):
        if _surface(tokens[i].token) == "の":
            end = i
            break
    if end < len(tokens) and _surface(tokens[end].token) == "の":
        return None
    if end < len(tokens) and _surface(tokens[end].token) in _COORDINATORS:
        return None
    if not any(_feature(tokens[i].token, "pos1") in ("名詞", "代名詞")
               for i in range(start, end)):
        return None
    if _surface(tokens[start].token) in _NOMINALIZERS:
        return None
    return start, end


def _topic_left(ctx, ends, before, *, limit=24):
    """Find a directly scoped は/が subject, allowing only a comma after it."""
    tokens = ctx.tokens
    low = max(0, before - limit)
    for marker in range(before - 1, low - 1, -1):
        token = tokens[marker].token
        if (_surface(token) not in ("は", "が")
                or _feature(token, "pos1") != "助詞"):
            continue
        gaps = tokens[marker + 1:before]
        if any(_surface(item.token) not in ("、", ",") for item in gaps):
            return None
        phrase = _phrase_left(tokens, ends, marker)
        if phrase is None:
            return None
        return phrase[0], marker
    return None


def _abs_span(ctx, first, last):
    tokens = ctx.tokens
    start = ctx.sentence_span.start + tokens[first].start
    end = ctx.sentence_span.start + tokens[last - 1].end
    return Span(ctx.sentence_span.source, start, end,
                ctx.sentence_text[tokens[first].start:tokens[last - 1].end])


def _text_span(ctx, start, end):
    return Span(ctx.sentence_span.source, ctx.sentence_span.start + start,
                ctx.sentence_span.start + end, ctx.sentence_text[start:end])


def _role(ctx, name, phrase):
    span = _abs_span(ctx, phrase[0], phrase[1])
    return Role(name, span.text, span, "literal")


def _scope_safe(ctx):
    return (":" not in ctx.sentence_text and "：" not in ctx.sentence_text
            and not any(mark in ctx.sentence_text
                        for mark in ("「", "」", "『", "』", "“", "”", '"'))
            and not any(_surface(t.token) in _SCOPE_MARKERS for t in ctx.tokens))


def _identity(ctx, start, end, predicate, predicate_span, roles, time):
    signature = "\0".join((ctx.sentence_span.source, str(start), str(end),
                           predicate, *(r.name + ":" + r.span.text for r in roles)))
    ident = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:24]
    span = ctx.sentence_span
    source_clause = ctx.clauses[0] if ctx.clauses else None
    return Clause(
        id=ident,
        event=Variable("event_" + ident, "event"),
        predicate=predicate,
        predicate_span=predicate_span,
        roles=tuple(roles),
        span=span,
        body_span=span,
        polarity="+",
        modality="assert",
        time=time,
        rule="light_verb",
        sovereign=source_clause.sovereign if source_clause else "document",
        family=source_clause.family if source_clause else "document",
        unsupported=(),
    )


def _relation_readings(ctx, starts, ends):
    tokens = ctx.tokens
    out = []
    i = 0
    while i < len(tokens):
        token = tokens[i].token
        surface = _surface(token)
        relation = surface if surface in _STATIC else ""
        pred_first = i
        pred_last = i + 1
        arg_particle = i - 1
        if (not relation and surface == "する" and i >= 2
                and _surface(tokens[i - 1].token) in ("由来", "位置")
                and "サ変可能" in _feature(tokens[i - 1].token, "pos3")):
            relation = _surface(tokens[i - 1].token) + "する"
            pred_first = i - 1
            arg_particle = i - 2
        if not relation or arg_particle < 0:
            i += 1
            continue
        particle = tokens[arg_particle].token
        if (_surface(particle) != "に" or _feature(particle, "pos1") != "助詞"
                or _feature(particle, "pos2") != "格助詞"):
            i += 1
            continue
        argument = _phrase_left(tokens, ends, arg_particle)
        if argument is None:
            i += 1
            continue
        pred_span = _abs_span(ctx, pred_first, pred_last)
        if relation == "属する":
            argument_role, subject_role = "group", "member"
        elif relation == "位置する":
            argument_role, subject_role = "location", "entity"
        else:
            argument_role, subject_role = "source", "entity"
        after = pred_last
        head = _phrase_head_right(tokens, starts, after) if after < len(tokens) else None
        topic = _topic_left(ctx, ends, argument[0])
        if head is not None and topic is not None:
            i += 1
            continue
        if head is not None:
            end = head[1]
            roles = (_role(ctx, subject_role, head), _role(ctx, argument_role, argument))
            span_start = tokens[argument[0]].start
            span_end = tokens[end - 1].end
        elif topic is not None:
            subject = _phrase_left(tokens, ends, topic[1])
            if subject is None:
                i += 1
                continue
            roles = (_role(ctx, subject_role, subject), _role(ctx, argument_role, argument))
            span_start = tokens[subject[0]].start
            span_end = tokens[pred_last - 1].end
        else:
            i += 1
            continue
        clause = _identity(ctx, span_start, span_end, relation, pred_span, roles,
                           "nonpast")
        out.append((clause, _text_span(ctx, span_start, span_end)))
        i = pred_last
    return out


def _lightverb(tokens, first):
    if first >= len(tokens):
        return None
    token = tokens[first].token
    surface = _surface(token)
    base = _feature(token, "orthBase") or surface
    if base in ("行う", "する") and surface in ("行う", "する"):
        return first + 1, "nonpast"
    if surface in ("行っ", "し") and base in ("行う", "する"):
        if first + 1 < len(tokens):
            following = tokens[first + 1].token
            if _surface(following) == "た" and _feature(following, "pos1") == "助動詞":
                return first + 2, "past"
    return None


def _action_readings(ctx, starts, ends):
    tokens = ctx.tokens
    out = []
    for particle in range(1, len(tokens)):
        if (_surface(tokens[particle].token) != "を"
                or _feature(tokens[particle].token, "pos2") != "格助詞"):
            continue
        vn = particle - 1
        if (_feature(tokens[vn].token, "pos1") != "名詞"
                or "サ変可能" not in _feature(tokens[vn].token, "pos3")):
            continue
        if (vn >= 2 and _surface(tokens[vn - 1].token) in ("、", ",", "，", "と", "や")
                and _feature(tokens[vn - 2].token, "pos1") == "名詞"
                and "サ変可能" in _feature(tokens[vn - 2].token, "pos3")):
            continue
        light = _lightverb(tokens, particle + 1)
        if light is None:
            continue
        after, time = light
        if after < len(tokens) and _surface(tokens[after].token) in _NOMINALIZERS:
            continue
        head = _phrase_head_right(tokens, starts, after) if after < len(tokens) else None
        topic = _topic_left(ctx, ends, vn)
        if head is not None and topic is not None:
            continue
        vn_span = _abs_span(ctx, vn, vn + 1)
        if head is not None:
            agent = _role(ctx, "agent", head)
            start, end = tokens[vn].start, tokens[head[1] - 1].end
        elif topic is not None:
            subject = _phrase_left(tokens, ends, topic[1])
            if subject is None:
                continue
            agent = _role(ctx, "agent", subject)
            start, end = tokens[subject[0]].start, tokens[after - 1].end
        else:
            continue
        clause = _identity(ctx, start, end, vn_span.text + "する", vn_span,
                           (agent,), time)
        out.append((clause, _text_span(ctx, start, end)))
    return out


def _use_readings(ctx, starts, ends):
    tokens = ctx.tokens
    out = []
    offsets = []
    at = ctx.sentence_text.find("として")
    while at >= 0:
        offsets.append(at)
        at = ctx.sentence_text.find("として", at + 1)
    token_ends = {item.end: j for j, item in enumerate(tokens)}
    for pred in range(len(tokens)):
        token = tokens[pred].token
        if ((_feature(token, "orthBase") or _surface(token)) != "用いる"
                or _surface(token) != "用いる"):
            continue
        char_end = tokens[pred].start
        mark_index = bisect_left(offsets, char_end) - 1
        if mark_index < 0:
            continue
        char_start = offsets[mark_index]
        capacity_token = token_ends.get(char_start)
        if capacity_token is None:
            continue
        capacity_end = capacity_token + 1
        capacity = _phrase_left(tokens, ends, capacity_end)
        if capacity is None:
            continue
        capacity_span = _abs_span(ctx, capacity[0], capacity[1])
        if ctx.sentence_text[capacity_span.end - ctx.sentence_span.start:char_end] != "として":
            continue
        obj_particle = capacity[0] - 1
        if (obj_particle < 1 or _surface(tokens[obj_particle].token) != "を"
                or _feature(tokens[obj_particle].token, "pos2") != "格助詞"):
            continue
        patient = _phrase_left(tokens, ends, obj_particle)
        if patient is None:
            continue
        predicate_span = _abs_span(ctx, pred, pred + 1)
        roles = (_role(ctx, "patient", patient), _role(ctx, "capacity", capacity))
        clause = _identity(ctx, tokens[patient[0]].start, tokens[pred].end,
                           "用いる", predicate_span, roles, "nonpast")
        out.append((clause, _text_span(ctx, tokens[patient[0]].start, tokens[pred].end)))
    return out


def reads(ctx: ConstructionContext) -> Reading | None:
    tokens = ctx.tokens
    if (len(tokens) > ctx.budget.max_tokens or not tokens
            or not _scope_safe(ctx)):
        return None
    starts, ends = _noun_phrases(tokens)
    candidates = (_relation_readings(ctx, starts, ends)
                  + _action_readings(ctx, starts, ends)
                  + _use_readings(ctx, starts, ends))
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[1].start, item[1].end, item[0].predicate))
    kept = []
    notes = []
    prior_end = -1
    for clause, span in candidates:
        if len(kept) + len(notes) >= ctx.budget.max_clauses:
            return None
        if span.start < prior_end:
            notes.append(TypedNote("ambiguous construction scope", span,
                                   "overlapping light-verb readings were left unresolved"))
            if kept and kept[-1][1].end > span.start:
                kept.pop()
            prior_end = max(prior_end, span.end)
            continue
        kept.append((clause, span))
        prior_end = span.end
    if not kept:
        return Reading((), (), tuple(notes)) if notes else None
    if len(kept) * 4 + len(notes) > ctx.budget.max_steps:
        return None
    return Reading(tuple(clause for clause, _ in kept),
                   tuple(ctx.sentence_span for _ in kept), tuple(notes))


def _source_span(span, source, outer):
    return (isinstance(span, Span) and span.source == outer.source
            and span.valid({span.source: source})
            and outer.start <= span.start <= span.end <= outer.end)


def _licensed_action(clause, action):
    if action not in ("を行う", "を行った", "をする", "をした"):
        return False
    return ((clause.time == "past" and action in ("を行った", "をした"))
            or (clause.time == "nonpast" and action in ("を行う", "をする")))


def licenses(clause: Clause, source: str) -> bool:
    """Recheck the clause grammar from source positions, without the reader."""
    if (not isinstance(clause, Clause) or not isinstance(source, str)
            or clause.rule != "light_verb" or clause.unsupported
            or clause.polarity != "+" or clause.modality != "assert"
            or clause.conditions or clause.exceptions or clause.exception_of
            or clause.time not in ("past", "nonpast")
            or not _source_span(clause.span, source, clause.span)
            or clause.body_span != clause.span
            or not _source_span(clause.body_span, source, clause.span)
            or not _source_span(clause.predicate_span, source, clause.span)):
        return False
    roles = clause.roles
    if any(not _source_span(r.span, source, clause.span) or r.rule != "literal"
           or r.term != r.span.text for r in roles):
        return False
    body = clause.body_span
    pred = clause.predicate_span
    raw = source

    if clause.predicate in _STATIC or clause.predicate == "由来する":
        if clause.time != "nonpast" or len(roles) != 2:
            return False
        subject_name, arg_name = (("member", "group") if clause.predicate == "属する"
                                  else ("entity", "location") if clause.predicate == "位置する"
                                  else ("entity", "source"))
        subject = next((r for r in roles if r.name == subject_name), None)
        argument = next((r for r in roles if r.name == arg_name), None)
        if subject is None or argument is None or pred.text != clause.predicate:
            return False
        if raw[argument.span.end:pred.start] != "に":
            return False
        if subject.span.start >= pred.end:
            # Relative form: N に predicate HEAD.
            return (subject.span.start == pred.end
                    and raw[argument.span.start:subject.span.end] ==
                    argument.span.text + "に" + pred.text
                    + subject.span.text)
        # Topic form: SUBJECT は/が[, ] N に predicate.
        gap = raw[subject.span.end:argument.span.start]
        return (subject.span.end <= argument.span.start
                and gap in ("は", "が", "は、", "が、", "は,", "が,")
                and raw[subject.span.start:pred.end] == subject.span.text + gap
                + argument.span.text + "に" + pred.text)

    if clause.predicate == "用いる":
        if (clause.time != "nonpast" or len(roles) != 2 or pred.text != "用いる"
                or body != clause.span):
            return False
        patient = next((r for r in roles if r.name == "patient"), None)
        capacity = next((r for r in roles if r.name == "capacity"), None)
        return (patient is not None and capacity is not None
                and patient.span.start == body.start
                and raw[patient.span.end:capacity.span.start] == "を"
                and raw[capacity.span.end:pred.start] == "として")

    if (clause.predicate.endswith("する") and len(roles) == 1
            and pred.text + "する" == clause.predicate):
        agent = roles[0]
        if agent.name != "agent":
            return False
        if agent.span.end <= pred.start:
            action = next((form for form in ("を行った", "をする", "をした", "を行う")
                           if raw.startswith(form, pred.end)), "")
            gap = raw[agent.span.end:pred.start]
            return (gap in
                    ("は", "が", "は、", "が、", "は,", "が,")
                    and _licensed_action(clause, action)
                    and raw[agent.span.start:pred.end + len(action)] ==
                    agent.span.text + gap + pred.text + action)
        if agent.span.start >= pred.end:
            action = raw[pred.end:agent.span.start]
            return (_licensed_action(clause, action)
                    and raw[pred.start:agent.span.end] == pred.text + action + agent.span.text)
        return False
    return False


register(Construction(name="light_verb", priority=35, reads=reads,
                      licenses=licenses, refines=()))
