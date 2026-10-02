"""Source-bounded comparison clauses with an independently checked grammar."""
from __future__ import annotations

import hashlib
import re

from ..semantic_ir import Clause, Role, Span, Variable
from . import Construction, ConstructionContext, Reading, TypedNote, register


# The lexical inventory is deliberately closed.  Its sign records the direction
# of the adjective on the underlying scale (for example, 高い is greater while
# 低い is less).
_ADJECTIVES = (
    ("新しくない", "新しい", -1, True), ("新しい", "新しい", -1, False),
    ("短くない", "短い", -1, True), ("短い", "短い", -1, False),
    ("少なくない", "少ない", -1, True), ("少ない", "少ない", -1, False),
    ("小さくない", "小さい", -1, True), ("小さい", "小さい", -1, False),
    ("低くない", "低い", -1, True), ("低い", "低い", -1, False),
    ("軽くない", "軽い", -1, True), ("軽い", "軽い", -1, False),
    ("弱くない", "弱い", -1, True), ("弱い", "弱い", -1, False),
    ("遅くない", "遅い", -1, True), ("遅い", "遅い", -1, False),
    ("狭くない", "狭い", -1, True), ("狭い", "狭い", -1, False),
    ("高くない", "高い", 1, True), ("高い", "高い", 1, False),
    ("大きくない", "大きい", 1, True), ("大きい", "大きい", 1, False),
    ("多くない", "多い", 1, True), ("多い", "多い", 1, False),
    ("長くない", "長い", 1, True), ("長い", "長い", 1, False),
    ("重くない", "重い", 1, True), ("重い", "重い", 1, False),
    ("強くない", "強い", 1, True), ("強い", "強い", 1, False),
    ("速くない", "速い", 1, True), ("速い", "速い", 1, False),
    ("古くない", "古い", 1, True), ("古い", "古い", 1, False),
    ("広くない", "広い", 1, True), ("広い", "広い", 1, False),
)
_ADJ_BY_SURFACE = {surface: (lemma, sign, negative)
                   for surface, lemma, sign, negative in _ADJECTIVES}
_ADJ_SUFFIXES = tuple(sorted(_ADJ_BY_SURFACE, key=len, reverse=True))
_ENDINGS = ("である", "でした", "だった", "です", "だ")
_PUNCTUATION = "。！？"
_EVENT_CUES = (
    ("多くの", "quantity", "greater"), ("少なく", "quantity", "less"),
    ("丁寧に", "care", "greater"), ("正確に", "accuracy", "greater"),
    ("詳しく", "detail", "greater"), ("高価な", "price", "greater"),
    ("大きな", "size", "greater"), ("小さな", "size", "less"),
    ("長い", "duration", "greater"), ("短い", "duration", "less"),
    ("重い", "weight", "greater"), ("軽い", "weight", "less"),
    ("広い", "range", "greater"), ("狭い", "range", "less"),
    ("高い", "height_or_price", "greater"), ("低い", "height_or_price", "less"),
    ("早く", "time", "earlier"), ("先に", "time", "earlier"),
    ("遅く", "time", "later"), ("速く", "speed", "faster"),
    ("強く", "force", "greater"), ("多く", "quantity", "greater"),
    ("少ない", "quantity", "less"), ("長く", "duration", "greater"),
    ("短く", "duration", "less"), ("大きく", "size", "greater"),
    ("小さく", "size", "less"), ("安い", "price", "less"),
)
_EVENT_CUES = tuple(sorted(_EVENT_CUES, key=lambda item: len(item[0]), reverse=True))
_EVENT_ALLOWED_REASONS = frozenset(("unrepresented source content", "ambiguous case role: に",
                                    "ambiguous case role: で", "ambiguous frame role"))
_EVENT_ROLE_NAMES = frozenset(("agent", "patient", "recipient", "topic", "source", "goal"))


def _clean_bounds(text: str, start: int, end: int):
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end, text[start:end]


def _dimension_bounds(text: str, start: int, end: int, pred_start: int,
                      pred_end: int, lemma: str):
    raw = text[start:end]
    left = len(raw) - len(raw.lstrip())
    dimension = raw.strip()
    while dimension.endswith(("が", "は", "の")):
        dimension = dimension[:-1].rstrip()
    dim_start = start + left
    if dimension:
        return dim_start, dim_start + len(dimension), dimension
    return pred_start, pred_end, lemma


def _trim_end(text: str) -> int:
    end = len(text)
    while end and (text[end - 1].isspace() or text[end - 1] in _PUNCTUATION):
        end -= 1
    for ending in _ENDINGS:
        if text[:end].endswith(ending):
            end -= len(ending)
            while end and text[end - 1].isspace():
                end -= 1
            break
    return end


def _adjective_at_end(text: str, start: int, end: int, negative: bool | None = None):
    for surface in _ADJ_SUFFIXES:
        info = _ADJ_BY_SURFACE[surface]
        if negative is not None and info[2] != negative:
            continue
        if end - start >= len(surface) and text[start:end].endswith(surface):
            return (end - len(surface), end, surface, info)
    return None


def _relative_form(text: str):
    """Parse only the two asserted, source-bounded relative comparison forms."""
    end = _trim_end(text)
    core = text[:end]
    topic = core.find("は")
    if topic <= 0:
        return None

    # AはBほど...ない encodes a lower value on the stated dimension.
    rest_start = topic + 1
    relative = core.find("ほど", rest_start)
    if relative >= 0:
        standard_start, standard_end = rest_start, relative
        tail_start = relative + 2
        adj = _adjective_at_end(core, tail_start, end, True)
        if adj is None:
            return None
        pred_start, pred_end, surface, (lemma, scale_sign, _negative) = adj
        subject_start, subject_end, subject = _clean_bounds(core, 0, topic)
        standard_start, standard_end, standard = _clean_bounds(core, standard_start, standard_end)
        if not subject or not standard:
            return None
        # Remove a dimension marker such as 背が/人口が from the predicate tail.
        prefix = core[tail_start:pred_start]
        dimension_start, dimension_end, dimension_text = _dimension_bounds(
            core, tail_start, pred_start, pred_start, pred_end, lemma)
        return {
            "subject": (subject_start, subject_end, subject),
            "standard": (standard_start, standard_end, standard),
            "dimension": (dimension_start, dimension_end, dimension_text),
            "predicate": (pred_start, pred_end, lemma),
            "direction": "less" if scale_sign > 0 else "greater",
            "form": "ほど",
            "sentence_end": len(text),
        }

    # AはBより... supports a positive adjective only.  Negated statements are
    # deliberately left ambiguous because they do not establish a strict order.
    relative = core.find("より", rest_start)
    if relative >= 0:
        standard_start, standard_end = rest_start, relative
        tail_start = relative + 2
        if core[tail_start:tail_start + 1] == "も":
            tail_start += 1
        adj = _adjective_at_end(core, tail_start, end, False)
        if adj is None:
            return None
        pred_start, pred_end, _surface, (lemma, scale_sign, _negative) = adj
        subject_start, subject_end, subject = _clean_bounds(core, 0, topic)
        standard_start, standard_end, standard = _clean_bounds(core, standard_start, standard_end)
        if not subject or not standard:
            return None
        prefix = core[tail_start:pred_start]
        dimension_start, dimension_end, dimension_text = _dimension_bounds(
            core, tail_start, pred_start, pred_start, pred_end, lemma)
        return {
            "subject": (subject_start, subject_end, subject),
            "standard": (standard_start, standard_end, standard),
            "dimension": (dimension_start, dimension_end, dimension_text),
            "predicate": (pred_start, pred_end, lemma),
            "direction": "greater" if scale_sign > 0 else "less",
            "form": "より",
            "sentence_end": len(text),
        }
    return None


def _superlative_form(text: str):
    """Recognize superlatives only when a source phrase names their comparison set."""
    end = _trim_end(text)
    core = text[:end]
    topic = core.find("は")
    if topic <= 0:
        return None
    marker = None
    marker_width = 0
    for word in ("最も", "一番"):
        found = core.find(word, topic + 1)
        if found >= 0 and (marker is None or found < marker):
            marker, marker_width = found, len(word)
    if marker is None:
        return None
    group_piece = core[topic + 1:marker]
    if not group_piece.endswith("で"):
        return None
    group = group_piece[:-1].strip()
    if not group:
        return None
    pred_start = marker + marker_width
    # Superlative nominals may follow the adjective: 日本で最も高い山.
    pred = None
    for surface in _ADJ_SUFFIXES:
        lemma, scale_sign, negative = _ADJ_BY_SURFACE[surface]
        if negative:
            continue
        found = core.find(surface, pred_start)
        if found >= 0 and (pred is None or found < pred[0]):
            pred = (found, found + len(surface), lemma, scale_sign)
    if pred is None:
        return None
    pred_start, pred_end, lemma, _scale_sign = pred
    candidate_start, candidate_end, candidate_class = _clean_bounds(core, pred_end, end)
    # The text after the adjective may name the candidate class, but arbitrary
    # clauses after it are not treated as a comparison set.
    while candidate_class.startswith(("は", "が", "の")):
        candidate_start += 1
        candidate_class = candidate_class[1:]
    while candidate_class.endswith(("は", "が", "の")):
        candidate_end -= 1
        candidate_class = candidate_class[:-1]
    candidate_class = candidate_class.strip()
    if candidate_class and not re.fullmatch(r"[\w一-龯ぁ-んァ-ヶー]+", candidate_class):
        return None
    subject_start, subject_end, subject = _clean_bounds(core, 0, topic)
    group_start, group_end, group = _clean_bounds(core, topic + 1, marker - 1)
    if not subject:
        return None
    return {
        "subject": (subject_start, subject_end, subject),
        "standard": (candidate_start, candidate_end, candidate_class) if candidate_class else
                    (group_start, group_end, group),
        "dimension": (pred_start, pred_end, lemma),
        "predicate": (pred_start, pred_end, lemma),
        "direction": "greatest" if _ADJ_BY_SURFACE[surface][1] > 0 else "least",
        "form": "superlative",
        "sentence_end": len(text),
        "scope": (group_start, group_end, group),
    }


def _reader_match(text: str):
    # Question-shaped comparisons are requests, not assertions or evidence.
    if "どちら" in text and any(mark in text for mark in ("?", "？", "か。", "か？")):
        return None
    if "ことが多い" in text:
        return None
    match = _relative_form(text)
    return match if match is not None else _superlative_form(text)


def _after_particle(text: str, end: int, choices: tuple[str, ...]):
    rest = text[end:]
    skipped = len(rest) - len(rest.lstrip())
    rest = rest[skipped:]
    for choice in choices:
        if rest.startswith(choice):
            pos = end + skipped + len(choice)
            while pos < len(text) and (text[pos].isspace() or text[pos] in "、,"):
                pos += 1
            return pos
    return None


def _event_role_ok(text: str, role: Role, start: int, end: int) -> bool:
    if role.name == "agent":
        return _after_particle(text, end, ("は", "が", "のほうが", "の方が")) is not None
    if role.name == "patient":
        return _after_particle(text, end, ("を", "が")) is not None
    if role.name == "recipient":
        return _after_particle(text, end, ("に", "へ")) is not None
    if role.name == "topic":
        return _after_particle(text, end, ("では", "には", "は", "で", "について")) is not None
    if role.name == "source":
        return _after_particle(text, end, ("から",)) is not None
    if role.name == "goal":
        return _after_particle(text, end, ("へ", "に")) is not None
    return False


def _event_comparison(ctx: ConstructionContext):
    text = ctx.sentence_text
    if len(ctx.clauses) != 1 or "ことが多い" in text:
        return None
    base = ctx.clauses[0]
    if (base.rule != "frame" or not base.unsupported
            or not set(base.unsupported).issubset(_EVENT_ALLOWED_REASONS)
            or base.conditions or base.condition_spans or base.exceptions
            or base.exception_spans or base.exception_of
            or base.polarity != "+" or base.modality != "assert"):
        return None
    marker = text.find("より")
    if marker < 0 or text.find("より", marker + 2) >= 0:
        return None
    marker_end = marker + 2 + (1 if text[marker + 2:marker + 3] == "も" else 0)
    event_start = base.predicate_span.start - ctx.sentence_span.start
    event_end = base.predicate_span.end - ctx.sentence_span.start
    if event_start < marker_end or event_end > len(text):
        return None

    agent = next((r for r in base.roles if r.name == "agent"), None)
    if agent is None:
        return None
    agent_start = agent.span.start - ctx.sentence_span.start
    agent_end = agent.span.end - ctx.sentence_span.start
    if agent_start < 0 or agent_end <= agent_start or agent_end > len(text):
        return None
    entity_start, entity_end = agent_start, agent_end
    if text[entity_start:entity_end].endswith("のほう"):
        entity_end -= 3
    entity_text = text[entity_start:entity_end]
    if not entity_text:
        return None

    if agent_start < marker:
        standard_start = _after_particle(text, agent_end, ("は", "が"))
        if standard_start is None or standard_start > marker:
            return None
        delimiter = max(text.rfind("、", standard_start, marker),
                        text.rfind(",", standard_start, marker))
        if delimiter >= standard_start:
            standard_start = delimiter + 1
            while standard_start < marker and text[standard_start].isspace():
                standard_start += 1
    else:
        houga = text.find("のほうが", marker_end, event_start + 1)
        if houga < 0 or not (marker_end <= entity_start < houga):
            return None
        delimiter = max(text.rfind("、", 0, marker), text.rfind(",", 0, marker))
        standard_start = delimiter + 1
        while standard_start < marker and text[standard_start].isspace():
            standard_start += 1
    standard_start, standard_end, standard_text = _clean_bounds(text, standard_start, marker)
    if not standard_text:
        return None

    cue_candidates = []
    for surface, dimension, direction in _EVENT_CUES:
        pos = text.find(surface, marker_end, event_start)
        if pos >= 0:
            cue_candidates.append((pos, -len(surface), surface, dimension, direction))
    if not cue_candidates:
        return None
    cue_candidates.sort()
    cue_start, _neg_length, cue_surface, dimension, direction = cue_candidates[0]
    # Multiple comparison scales in one clause need a separate scoped reading.
    if any(pos != cue_start for pos, _n, _s, _d, _direction in cue_candidates[1:]):
        return None
    cue_end = cue_start + len(cue_surface)
    patient = next((r for r in base.roles if r.name == "patient"
                    and r.span.start - ctx.sentence_span.start <= cue_start
                    < r.span.end - ctx.sentence_span.start), None)
    if patient is not None:
        dimension_start = patient.span.start - ctx.sentence_span.start
        dimension_end = patient.span.end - ctx.sentence_span.start
        dimension_text = dimension
    else:
        dimension_start, dimension_end, dimension_text = cue_start, cue_end, dimension
        if text[cue_end:cue_end + 2] == "時間":
            dimension_end = cue_end + 2
            dimension_text = dimension

    event_roles = []
    seen = set()
    for role in base.roles:
        start = role.span.start - ctx.sentence_span.start
        end = role.span.end - ctx.sentence_span.start
        overlaps_comparison = (start < standard_end and end > standard_start
                               or start < cue_end and end > cue_start)
        if role.name == "ambiguous":
            if overlaps_comparison:
                continue
            return None
        if role.name == "goal" and start < cue_end and end > cue_start:
            continue
        if role.name not in _EVENT_ROLE_NAMES:
            if overlaps_comparison:
                continue
            return None
        if role.name in seen or start < 0 or end <= start or end > len(text):
            return None
        if role.span.text != text[start:end] or role.term != role.span.text:
            return None
        if not _event_role_ok(text, role, start, end):
            return None
        seen.add(role.name)
        if role.name == "agent" and text[start:end].endswith("のほう"):
            event_roles.append(Role(role.name, text[start:entity_end],
                                    _absolute_span(ctx, start, entity_end), role.rule))
        else:
            event_roles.append(role)
    if "agent" not in seen:
        return None
    if not _event_role_ok(text, agent, entity_start, entity_end):
        # The normalized entity in an のほうが phrase is followed by that phrase.
        return None
    for reason in base.unsupported:
        if reason.startswith("ambiguous case role:") and not any(
                r.name == "ambiguous" and
                ((r.span.start - ctx.sentence_span.start < standard_end
                  and r.span.end - ctx.sentence_span.start > standard_start)
                 or (r.span.start - ctx.sentence_span.start < cue_end
                     and r.span.end - ctx.sentence_span.start > cue_start))
                for r in base.roles):
            return None
        if reason == "ambiguous frame role" and not any(
                r.name == "ambiguous" and
                ((r.span.start - ctx.sentence_span.start < standard_end
                  and r.span.end - ctx.sentence_span.start > standard_start)
                 or (r.span.start - ctx.sentence_span.start < cue_end
                     and r.span.end - ctx.sentence_span.start > cue_start))
                for r in base.roles):
            return None

    return {
        "base": base,
        "event_roles": tuple(event_roles),
        "entity": (entity_start, entity_end, entity_text),
        "standard": (standard_start, standard_end, standard_text),
        "dimension": (dimension_start, dimension_end, dimension_text),
        "cue": (cue_start, cue_end, cue_surface),
        "direction": direction,
    }


def _event_clause(ctx: ConstructionContext, match) -> Clause:
    base = match["base"]
    text = ctx.sentence_text
    identity = hashlib.blake2s(
        (ctx.sentence_span.source + "\0" + str(ctx.sentence_span.start)
         + "\0comparison-event\0" + text).encode("utf-8"), digest_size=10).hexdigest()
    roles = list(match["event_roles"])
    return Clause(
        id="comparison_" + identity,
        event=base.event,
        predicate=base.predicate,
        predicate_span=base.predicate_span,
        roles=tuple(roles),
        span=ctx.sentence_span,
        body_span=ctx.sentence_span,
        polarity=base.polarity,
        modality=base.modality,
        time=base.time,
        conditions=(), condition_spans=(), exceptions=(), exception_spans=(),
        exception_of="", rule="comparison", sovereign="document", family="document",
        unsupported=(),
    )


def _event_relation_clause(ctx: ConstructionContext, match) -> Clause:
    base = match["base"]
    text = ctx.sentence_text
    identity = hashlib.blake2s(
        (ctx.sentence_span.source + "\0" + str(ctx.sentence_span.start)
         + "\0comparison-relation\0" + text).encode("utf-8"), digest_size=10).hexdigest()
    roles = []
    for name, key, rule in (("entity", "entity", "comparison_entity"),
                            ("standard", "standard", "literal")):
        start, end, term = match[key]
        roles.append(Role(name, term, _absolute_span(ctx, start, end), rule))
    direction_start, direction_end, _ = match["cue"]
    roles.append(Role("dimension", match["dimension"][2],
                      _absolute_span(ctx, direction_start, direction_end),
                      "comparison_dimension"))
    roles.append(Role("direction", match["direction"],
                      _absolute_span(ctx, direction_start, direction_end),
                      "comparison_direction"))
    return Clause(
        id="comparison_relation_" + identity,
        event=Variable("event_comparison_" + identity, "event"),
        predicate="comparison",
        predicate_span=base.predicate_span,
        roles=tuple(roles),
        span=ctx.sentence_span,
        body_span=ctx.sentence_span,
        polarity=base.polarity,
        modality=base.modality,
        time=base.time,
        conditions=(), condition_spans=(), exceptions=(), exception_spans=(),
        exception_of="", rule="comparison", sovereign="document", family="document",
        unsupported=(),
    )


def _licensor_match(text: str):
    """Re-parse the source independently; this does not use the reader result."""
    if "どちら" in text and re.search(r"(?:\?|？|か[。！？]?$)", text):
        return None
    cut = len(text)
    while cut and (text[cut - 1].isspace() or text[cut - 1] in "。！？"):
        cut -= 1
    for suffix in ("である", "でした", "だった", "です", "だ"):
        if text[:cut].endswith(suffix):
            cut -= len(suffix)
            break
    text_end = cut
    body = text[:text_end]
    split = body.find("は")
    if split < 1:
        return None

    half = body.find("ほど", split + 1)
    if half >= 0:
        subject_start, subject_end, subject = _clean_bounds(body, 0, split)
        left_start, left_end, left = _clean_bounds(body, split + 1, half)
        pred_end = text_end
        pred = next((s for s in _ADJ_SUFFIXES
                     if _ADJ_BY_SURFACE[s][2] and body[:pred_end].endswith(s)), None)
        if pred is None:
            return None
        pred_start = pred_end - len(pred)
        before = body[half + 2:pred_start]
        dim_start, dim_end, dim = _dimension_bounds(
            body, half + 2, pred_start, pred_start, pred_end, _ADJ_BY_SURFACE[pred][0])
        if not subject or not left:
            return None
        scale_sign = _ADJ_BY_SURFACE[pred][1]
        return {"subject": (subject_start, subject_end, subject),
                "standard": (left_start, left_end, left),
                "dimension": (dim_start, dim_end, dim),
                "predicate": (pred_start, pred_end, _ADJ_BY_SURFACE[pred][0]),
                "direction": "less" if scale_sign > 0 else "greater",
                "form": "ほど", "sentence_end": len(text)}

    comp = body.find("より", split + 1)
    if comp >= 0:
        subject_start, subject_end, subject = _clean_bounds(body, 0, split)
        left_start, left_end, left = _clean_bounds(body, split + 1, comp)
        tail_start = comp + 2 + (1 if body[comp + 2:comp + 3] == "も" else 0)
        pred = next((s for s in _ADJ_SUFFIXES
                     if not _ADJ_BY_SURFACE[s][2] and body[:text_end].endswith(s)), None)
        if pred is None:
            return None
        pred_start, pred_end = text_end - len(pred), text_end
        before = body[tail_start:pred_start]
        dim_start, dim_end, dim = _dimension_bounds(
            body, tail_start, pred_start, pred_start, pred_end, _ADJ_BY_SURFACE[pred][0])
        if not subject or not left:
            return None
        sign = _ADJ_BY_SURFACE[pred][1]
        return {"subject": (subject_start, subject_end, subject),
                "standard": (left_start, left_end, left),
                "dimension": (dim_start, dim_end, dim),
                "predicate": (pred_start, pred_end, _ADJ_BY_SURFACE[pred][0]),
                "direction": "greater" if sign > 0 else "less",
                "form": "より", "sentence_end": len(text)}

    # Independent superlative check.
    marker = re.search(r"(?:最も|一番)", body[split + 1:])
    if marker is None:
        return None
    marker_start = split + 1 + marker.start()
    marker_end = split + 1 + marker.end()
    group_text = body[split + 1:marker_start]
    if not group_text.endswith("で") or not group_text[:-1].strip():
        return None
    chosen = None
    for surface in _ADJ_SUFFIXES:
        if _ADJ_BY_SURFACE[surface][2]:
            continue
        where = body.find(surface, marker_end)
        if where >= 0 and (chosen is None or where < chosen[0]):
            chosen = (where, where + len(surface), surface)
    if chosen is None:
        return None
    pstart, pend, surface = chosen
    candidate = body[pend:].strip("はがの ")
    if candidate and not re.fullmatch(r"[\w一-龯ぁ-んァ-ヶー]+", candidate):
        return None
    subject_start, subject_end, subject = _clean_bounds(body, 0, split)
    group_start, group_end, group = _clean_bounds(body, split + 1, marker_start - 1)
    candidate_start, candidate_end, candidate = _clean_bounds(body, pend, text_end)
    candidate = candidate.strip("はがの ")
    if candidate:
        # Candidate labels are single source-bounded nominal spans.
        while candidate_start < candidate_end and body[candidate_start] in "はがの ":
            candidate_start += 1
        while candidate_end > candidate_start and body[candidate_end - 1] in "はがの ":
            candidate_end -= 1
    scale_sign = _ADJ_BY_SURFACE[surface][1]
    if not subject or not group:
        return None
    return {"subject": (subject_start, subject_end, subject),
            "standard": (candidate_start, candidate_end, candidate) if candidate else
                        (group_start, group_end, group),
            "dimension": (pstart, pend, _ADJ_BY_SURFACE[surface][0]),
            "predicate": (pstart, pend, _ADJ_BY_SURFACE[surface][0]),
            "direction": "greatest" if scale_sign > 0 else "least",
            "form": "superlative", "sentence_end": len(text),
            "scope": (group_start, group_end, group)}


def _independent_event_license(clause: Clause, text: str) -> bool:
    """Independently recheck an event comparison and its case-marked arguments."""
    start0 = clause.span.start
    pstart = clause.predicate_span.start - start0
    pend = clause.predicate_span.end - start0
    if (pstart < 0 or pend <= pstart or pend > len(text)
            or text[pstart:pend] != clause.predicate_span.text):
        return False
    surface_predicate = text[pstart:pend]
    predicate = clause.predicate
    if predicate == "comparison":
        predicate_tail = text[pend:].strip("。！？ \t\n")
        if predicate_tail not in ("", "た", "だ", "ます", "ました", "る", "いる"):
            return False
        if not re.search(r"(?:た|だ|る|く|す|ます|いる)$", surface_predicate + predicate_tail):
            return False
    else:
        if predicate.endswith("する"):
            stem = predicate[:-2]
        else:
            stem = predicate[:-1] if predicate and predicate[-1] in "るうくぐすつぬぶむ" else predicate
        if not stem or stem not in surface_predicate:
            return False
    predicate_tail = text[pend:].strip("。！？ \t\n")
    if predicate_tail not in ("", "た", "だ", "ます", "ました", "る", "いる"):
        return False
    expected_time = "past" if (surface_predicate + predicate_tail).endswith(("た", "だ", "ました")) else ""
    if clause.time != expected_time:
        return False
    marks = [m.start() for m in re.finditer("より", text[:pstart])]
    if len(marks) != 1:
        return False
    mark = marks[0]
    after_mark = mark + 2 + (1 if text[mark + 2:mark + 3] == "も" else 0)

    entity = [r for r in clause.roles if r.name == "entity"]
    standard = [r for r in clause.roles if r.name == "standard"]
    dimension = [r for r in clause.roles if r.name == "dimension"]
    direction = [r for r in clause.roles if r.name == "direction"]
    if not (len(entity) == len(standard) == len(dimension) == len(direction) == 1):
        return False
    e, s, d, direct = entity[0], standard[0], dimension[0], direction[0]
    e0, e1 = e.span.start - start0, e.span.end - start0
    s0, s1 = s.span.start - start0, s.span.end - start0
    if (e0 < 0 or e1 <= e0 or e1 > len(text) or s0 < 0 or s1 <= s0
            or s1 > len(text) or text[e0:e1] != e.term or text[s0:s1] != s.term):
        return False
    if e0 < mark:
        rest = text[e1:mark]
        m = re.match(r"\s*(?:は|が)(?:\s*[、,])?\s*", rest)
        if m is None:
            return False
        ss, se = e1 + m.end(), mark
        delimiter = max(text.rfind("、", ss, mark), text.rfind(",", ss, mark))
        if delimiter >= ss:
            ss = delimiter + 1
    else:
        right = text.find("のほうが", after_mark, pstart)
        if right < 0 or not (after_mark <= e0 < right):
            return False
        delimiter = max(text.rfind("、", 0, mark), text.rfind(",", 0, mark))
        ss = delimiter + 1
        while ss < mark and text[ss].isspace():
            ss += 1
        se = mark
        if text[e0:right].endswith("のほう"):
            return False
    while ss < se and text[ss].isspace():
        ss += 1
    while se > ss and text[se - 1].isspace():
        se -= 1
    if (s0, s1) != (ss, se):
        return False

    # The checker has its own closed cue scan and independently derives the
    # comparison dimension and ordering.
    found = []
    segment = text[after_mark:pstart]
    for word, label, order in _EVENT_CUES:
        at = segment.find(word)
        if at >= 0:
            found.append((after_mark + at, -len(word), word, label, order))
    if not found:
        return False
    found.sort()
    cstart, _neglen, cword, label, order = found[0]
    if any(at != cstart for at, _n, _w, _l, _o in found[1:]):
        return False
    cend = cstart + len(cword)
    patients = [r for r in clause.roles if r.name == "patient"]
    cover = next((r for r in patients if r.span.start - start0 <= cstart
                  < r.span.end - start0), None)
    if cover is not None:
        d0, d1 = cover.span.start - start0, cover.span.end - start0
        dterm = label
    else:
        d0, d1, dterm = cstart, cend, label
        if text[cend:cend + 2] == "時間":
            d1 = cend + 2
    if ((d.span.start - start0, d.span.end - start0) != (d0, d1)
            or d.term != dterm or d.rule != "comparison_dimension"):
        return False
    q0, q1 = direct.span.start - start0, direct.span.end - start0
    if ((q0, q1) != (cstart, cend) or direct.term != order
            or direct.rule != "comparison_direction"):
        return False
    if e.rule != "comparison_entity" or s.rule != "literal":
        return False

    event_roles = [r for r in clause.roles if r.name not in
                   ("entity", "standard", "dimension", "direction")]
    if event_roles and not any(r.name == "agent" for r in event_roles):
        return False
    names = set()
    for role in event_roles:
        a0, a1 = role.span.start - start0, role.span.end - start0
        if (role.name not in _EVENT_ROLE_NAMES or role.name in names
                or a0 < 0 or a1 <= a0 or a1 > len(text)
                or role.term != text[a0:a1] or not role.rule):
            return False
        names.add(role.name)
        tail = text[a1:]
        if role.name == "agent":
            ok = re.match(r"\s*(?:は|が|のほうが|の方が)", tail) is not None
        elif role.name == "patient":
            ok = re.match(r"\s*(?:を|が)", tail) is not None
        elif role.name == "recipient":
            ok = re.match(r"\s*(?:に|へ)", tail) is not None
        elif role.name == "topic":
            ok = re.match(r"\s*(?:では|には|は|で|について)", tail) is not None
        elif role.name == "source":
            ok = re.match(r"\s*から", tail) is not None
        else:
            ok = re.match(r"\s*(?:へ|に)", tail) is not None
        if not ok:
            return False
    return True


def _independent_event_arguments(clause: Clause, text: str) -> bool:
    """Check the event projection without trusting the comparison reader."""
    start0 = clause.span.start
    pstart = clause.predicate_span.start - start0
    pend = clause.predicate_span.end - start0
    if (pstart < 0 or pend <= pstart or pend > len(text)
            or text[pstart:pend] != clause.predicate_span.text
            or text[pend:].strip("。！？ \t\n") not in
            ("", "た", "だ", "ます", "ました", "る", "いる")):
        return False
    predicate = clause.predicate
    stem = predicate[:-2] if predicate.endswith("する") else (
        predicate[:-1] if predicate and predicate[-1] in "るうくぐすつぬぶむ" else predicate)
    if not stem or stem not in text[pstart:pend]:
        return False
    predicate_tail = text[pend:].strip("。！？ \t\n")
    event_surface = text[pstart:pend] + predicate_tail
    expected_time = "past" if event_surface.endswith(("た", "だ", "ました")) else ""
    if clause.time != expected_time:
        return False
    matches = list(re.finditer("より", text[:pstart]))
    if len(matches) != 1:
        return False
    mark = matches[0].start()
    after = mark + 2 + (1 if text[mark + 2:mark + 3] == "も" else 0)
    agents = [r for r in clause.roles if r.name == "agent"]
    if len(agents) != 1:
        return False
    agent = agents[0]
    a0, a1 = agent.span.start - start0, agent.span.end - start0
    if (a0 < 0 or a1 <= a0 or a1 > len(text) or agent.term != text[a0:a1]
            or not agent.rule):
        return False
    if a1 <= mark:
        remainder = text[a1:mark]
        parsed = re.match(r"\s*(?:は|が)(?:\s*[、,])?\s*", remainder)
        if parsed is None or not text[a1 + parsed.end():mark].strip():
            return False
    else:
        if (a0 < after or text.find("のほうが", after, pstart) < a1
                or not text[:mark].split("、")[-1].strip()):
            return False
    # A closed cue must follow the standard and precede the event predicate.
    region = text[after:pstart]
    if not any(word in region for word, _dimension, _direction in _EVENT_CUES):
        return False
    names = set()
    for role in clause.roles:
        a0, a1 = role.span.start - start0, role.span.end - start0
        if (role.name not in _EVENT_ROLE_NAMES or role.name in names
                or a0 < 0 or a1 <= a0 or a1 > len(text)
                or role.term != text[a0:a1] or not role.rule):
            return False
        names.add(role.name)
        after_role = text[a1:]
        if role.name == "agent":
            ok = re.match(r"\s*(?:は|が|のほうが|の方が)", after_role) is not None
        elif role.name == "patient":
            ok = re.match(r"\s*(?:を|が)", after_role) is not None
        elif role.name == "recipient":
            ok = re.match(r"\s*(?:に|へ)", after_role) is not None
        elif role.name == "topic":
            ok = re.match(r"\s*(?:では|には|は|で|について)", after_role) is not None
        elif role.name == "source":
            ok = re.match(r"\s*から", after_role) is not None
        else:
            ok = re.match(r"\s*(?:へ|に)", after_role) is not None
        if not ok:
            return False
    return True


def _absolute_span(ctx: ConstructionContext, start: int, end: int) -> Span:
    local = ctx.sentence_text[start:end]
    return Span(ctx.sentence_span.source, ctx.sentence_span.start + start,
                ctx.sentence_span.start + end, local)


def reads(ctx: ConstructionContext) -> Reading | None:
    text = ctx.sentence_text
    if (len(ctx.tokens) > ctx.budget.max_tokens or len(text) > 4096
            or len(ctx.clauses) > ctx.budget.max_clauses):
        return None
    if (ctx.sentence_span.end - ctx.sentence_span.start != len(text)
            or ctx.sentence_span.text != text):
        return None
    event_match = _event_comparison(ctx)
    if event_match is not None:
        return Reading((_event_clause(ctx, event_match),
                        _event_relation_clause(ctx, event_match)),
                       (ctx.sentence_span,))
    match = _reader_match(text)
    if match is None:
        if re.search(r"(?:一番|最も)", text) and "は" in text:
            note = TypedNote("comparison_missing_standard", ctx.sentence_span,
                             "superlative comparison set is not source-bounded")
            return Reading((), (ctx.sentence_span,), (note,))
        return None
    if len(match) > ctx.budget.max_steps // 8:
        return None

    roles = []
    for name, key in (("entity", "subject"), ("standard", "standard"),
                      ("dimension", "dimension")):
        start, end, term = match[key]
        if not term or start < 0 or end <= start or end > len(text):
            return None
        roles.append(Role(name, term, _absolute_span(ctx, start, end),
                          "literal" if name != "dimension" else "comparison_dimension"))
    direction_start, direction_end, _ = match["predicate"]
    roles.append(Role("direction", match["direction"],
                      _absolute_span(ctx, direction_start, direction_end),
                      "comparison_direction"))
    if "scope" in match:
        start, end, term = match["scope"]
        if term and start < end:
            roles.append(Role("scope", term, _absolute_span(ctx, start, end), "literal"))

    pred_start, pred_end, predicate = match["predicate"]
    full_span = ctx.sentence_span
    identity = hashlib.blake2s(
        (full_span.source + "\0" + str(full_span.start) + "\0" + text).encode("utf-8"),
        digest_size=10,
    ).hexdigest()
    clause = Clause(
        id="comparison_" + identity,
        event=Variable("event_comparison_" + identity, "event"),
        predicate=predicate,
        predicate_span=_absolute_span(ctx, pred_start, pred_end),
        roles=tuple(roles),
        span=full_span,
        body_span=full_span,
        polarity="+",
        modality="assert",
        time="",
        conditions=(),
        condition_spans=(),
        exceptions=(),
        exception_spans=(),
        exception_of="",
        rule="comparison",
        sovereign="document",
        family="document",
        unsupported=(),
    )
    return Reading((clause,), (full_span,))


def licenses(clause: Clause, source: str) -> bool:
    """Check the grammar, roles, offsets and assertion independently."""
    if (clause.rule != "comparison" or clause.span.source == ""
            or clause.span.start < 0 or clause.span.end > len(source)
            or clause.span.end <= clause.span.start):
        return False
    text = source[clause.span.start:clause.span.end]
    if text != clause.span.text or clause.body_span != clause.span:
        return False
    if clause.predicate == "comparison":
        if (clause.polarity != "+" or clause.modality != "assert"
                or clause.time not in ("", "past")
                or clause.conditions or clause.condition_spans or clause.exceptions
                or clause.exception_spans or clause.exception_of
                or clause.sovereign != "document" or clause.family != "document"
                or clause.unsupported
                or not isinstance(clause.event, Variable) or clause.event.sort != "event"):
            return False
        return _independent_event_license(clause, text)
    if any(role.name == "agent" for role in clause.roles):
        if (clause.polarity != "+" or clause.modality != "assert"
                or clause.time not in ("", "past")
                or clause.conditions or clause.condition_spans or clause.exceptions
                or clause.exception_spans or clause.exception_of
                or clause.sovereign != "document" or clause.family != "document"
                or clause.unsupported
                or not isinstance(clause.event, Variable) or clause.event.sort != "event"):
            return False
        return _independent_event_arguments(clause, text)
    match = _licensor_match(text)
    if match is None:
        return False
    if (clause.polarity != "+" or clause.modality != "assert" or clause.time
            or clause.conditions or clause.condition_spans or clause.exceptions
            or clause.exception_spans or clause.exception_of
            or clause.sovereign != "document" or clause.family != "document"
            or clause.unsupported):
        return False
    if (not isinstance(clause.event, Variable) or clause.event.sort != "event"
            or clause.predicate != match["predicate"][2]):
        return False
    pred_start, pred_end, _ = match["predicate"]
    expected_pred_span = Span(clause.span.source, clause.span.start + pred_start,
                              clause.span.start + pred_end, text[pred_start:pred_end])
    if clause.predicate_span != expected_pred_span:
        return False

    expected = []
    for role_name, key in (("entity", "subject"), ("standard", "standard"),
                           ("dimension", "dimension")):
        start, end, term = match[key]
        expected.append((role_name, term, start, end,
                         "literal" if role_name != "dimension" else "comparison_dimension"))
    direction_start, direction_end, _ = match["predicate"]
    expected.append(("direction", match["direction"], direction_start, direction_end,
                     "comparison_direction"))
    if "scope" in match:
        start, end, term = match["scope"]
        if term and start < end:
            expected.append(("scope", term, start, end, "literal"))
    if len(clause.roles) != len(expected):
        return False
    for role, (name, term, start, end, rule) in zip(clause.roles, expected):
        wanted = Span(clause.span.source, clause.span.start + start,
                      clause.span.start + end, text[start:end])
        if (role.name != name or role.term != term or role.span != wanted
                or role.rule != rule):
            return False
    return True


register(Construction(name="comparison", priority=30, reads=reads,
                      licenses=licenses, refines=()))
