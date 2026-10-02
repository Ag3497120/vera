"""Composition-based recovery for a narrowly scoped comparison modifier."""
from __future__ import annotations

from dataclasses import replace

from . import Construction, Reading, enabled, register

_COMPARISON_ROLES = frozenset(("entity", "standard", "dimension", "direction"))
_PUNCTUATION = frozenset("、，,。！？? \n")
_COMPARATIVE_SURFACE = frozenset(("正確に", "早く", "先に", "遅く", "後に"))
_TIME_DIRECTIONS = {
    ("早く", "time", "earlier"),
    ("先に", "time", "earlier"),
    ("遅く", "time", "later"),
    ("後に", "time", "later"),
}


def _topic_gap(source, entity_end, standard_start):
    gap = source[entity_end:standard_start]
    return gap if gap in ("は", "が", "は、", "が、", "は，", "が，", "は,", "が,") else ""


def _source_span(span, source, source_name):
    return (span is not None and span.source == source_name
            and 0 <= span.start <= span.end <= len(source)
            and span.text == source[span.start:span.end])


def _relation_shape(clause, source):
    roles = {role.name: role for role in clause.roles}
    if (len(roles) != len(clause.roles) or set(roles) != _COMPARISON_ROLES
            or clause.predicate != "comparison" or clause.unsupported
            or clause.conditions or clause.exceptions
            or clause.polarity != "+" or clause.modality != "assert"):
        return False
    entity, standard = roles["entity"], roles["standard"]
    dimension, direction = roles["dimension"], roles["direction"]
    if (clause.span.start < 0 or clause.span.end > len(source)
            or not _source_span(clause.span, source, clause.span.source)
            or not _source_span(clause.body_span, source, clause.span.source)
            or not _source_span(clause.predicate_span, source, clause.span.source)
            or not _source_span(entity.span, source, clause.span.source)
            or not _source_span(standard.span, source, clause.span.source)
            or not _source_span(dimension.span, source, clause.span.source)
            or not _source_span(direction.span, source, clause.span.source)):
        return False
    if (entity.rule != "comparison_entity" or entity.term != entity.span.text
            or standard.rule != "literal"
            or dimension.rule != "comparison_dimension"
            or direction.rule != "comparison_direction"
            or standard.term != standard.span.text
            or dimension.span != direction.span):
        return False
    if not _topic_gap(source, entity.span.end, standard.span.start):
        return False
    if (source[standard.span.end:dimension.span.start] != "より"
            or source.count("より", clause.span.start, clause.span.end) != 1
            or dimension.span.end > clause.predicate_span.start):
        return False
    return (dimension.span.text, dimension.term, direction.term) in _TIME_DIRECTIONS


def _comparison_rule():
    return next((rule for rule in enabled() if rule.name == "comparison"), None)


def _shift_span(span, offset, source):
    if span is None:
        return None
    start, end = span.start - offset, span.end - offset
    if start < 0 or end < start or end > len(source):
        return None
    return replace(span, start=start, end=end, text=source[start:end])


def _relative_clause(clause, offset, source):
    def role(value):
        span = _shift_span(value.span, offset, source)
        return None if span is None else replace(value, span=span)

    span = _shift_span(clause.span, offset, source)
    predicate_span = _shift_span(clause.predicate_span, offset, source)
    body_span = _shift_span(clause.body_span, offset, source)
    roles = tuple(role(value) for value in clause.roles)
    if (span is None or predicate_span is None or body_span is None
            or any(value is None for value in roles)):
        return None
    return replace(clause, span=span, predicate_span=predicate_span,
                   body_span=body_span, roles=roles)


def _masked_frame_licenses(clause, source, comparison_start, comparison_end):
    if not (0 <= comparison_start < comparison_end <= len(source)):
        return False
    protected = [(role.span.start, role.span.end) for role in clause.roles]
    protected.append((clause.predicate_span.start, clause.predicate_span.end))
    if any(left < comparison_end and right > comparison_start
           for left, right in protected):
        return False
    chars = list(source)
    for index in range(comparison_start, comparison_end):
        chars[index] = " "
    masked = "".join(chars)

    def update(span):
        return None if span is None else replace(span, text=masked[span.start:span.end])

    from verantyx.semantic_ir import View
    from verantyx.semantic_verify import license_clause

    frame = replace(clause, rule="frame", span=update(clause.span),
                    body_span=update(clause.body_span),
                    predicate_span=update(clause.predicate_span),
                    roles=tuple(replace(role, span=update(role.span))
                                for role in clause.roles),
                    unsupported=(), conditions=(), condition_spans=(),
                    exceptions=(), exception_spans=(), exception_of="")
    view = View(sources={clause.span.source: masked}, clauses=(frame,))
    try:
        license_clause(frame, view)
    except Exception:
        return False
    return True


def _projected_frame_licenses(clause, source, comparison_start, comparison_end):
    """License the source-projected event after checking that only its comparison
    interval and punctuation were omitted from the projection.
    """
    if (not 0 <= clause.span.start < clause.span.end <= len(source)
            or not 0 <= comparison_start < comparison_end <= len(source)
            or comparison_start < clause.span.start
            or comparison_end > clause.span.end):
        return False
    parts = []
    for index, role in enumerate(clause.roles):
        span = role.span
        if (role.rule != "frame" or not _source_span(span, source, clause.span.source)
                or role.term != span.text):
            return False
        if role.name == "agent":
            if source[span.end:span.end + 1] not in ("は", "が"):
                return False
            left, right = span.start, span.end + 1
        elif role.name == "patient":
            if source[span.end:span.end + 1] in ("を", "が"):
                left, right = span.start, span.end + 1
            elif span.start > clause.span.start and source[span.start - 1:span.start] in ("を", "が"):
                left, right = span.start - 1, span.end
            else:
                return False
        elif role.name == "recipient":
            if source[span.end:span.end + 1] in ("に", "へ"):
                left, right = span.start, span.end + 1
            elif span.start > clause.span.start and source[span.start - 1:span.start] in ("に", "へ"):
                left, right = span.start - 1, span.end
            else:
                return False
        else:
            return False
        if left < clause.span.start or right > clause.span.end:
            return False
        parts.append((left, right, index, role))
    if not any(role.name == "agent" for role in clause.roles):
        return False
    if not _source_span(clause.predicate_span, source, clause.span.source):
        return False
    parts.append((clause.predicate_span.start, clause.span.end, -1, None))
    parts.sort(key=lambda part: (part[0], part[1]))
    if any(left < prior_end for (left, _, _, _), prior_end in
           zip(parts[1:], (part[1] for part in parts[:-1]))):
        return False

    projected_parts = []
    projected_roles = []
    projected_predicate = None
    cursor = 0
    source_cursor = clause.span.start
    for left, right, index, role in parts:
        for position in range(source_cursor, left):
            if not (comparison_start <= position < comparison_end
                    or source[position] in _PUNCTUATION):
                return False
        text = source[left:right]
        projected_parts.append(text)
        if role is not None:
            role_start = cursor + role.span.start - left
            role_end = cursor + role.span.end - left
            projected_roles.append((index, replace(
                role,
                span=replace(role.span, start=role_start, end=role_end,
                             text="".join(projected_parts)[role_start:role_end]),
            )))
        else:
            pred_start = cursor + clause.predicate_span.start - left
            pred_end = cursor + clause.predicate_span.end - left
            projected_predicate = (pred_start, pred_end)
        cursor += len(text)
        source_cursor = right
    for position in range(source_cursor, clause.span.end):
        if not (comparison_start <= position < comparison_end
                or source[position] in _PUNCTUATION):
            return False
    projected = "".join(projected_parts)
    if projected_predicate is None or len(projected_roles) != len(clause.roles):
        return False

    from verantyx.semantic_ir import Span, View
    from verantyx.semantic_verify import license_clause

    roles = tuple(role for _, role in sorted(projected_roles))
    predicate_span = Span(clause.span.source, *projected_predicate,
                          projected[projected_predicate[0]:projected_predicate[1]])
    full_span = Span(clause.span.source, 0, len(projected), projected)
    frame = replace(clause, roles=roles, rule="frame", span=full_span,
                    body_span=full_span, predicate_span=predicate_span,
                    unsupported=(), conditions=(), condition_spans=(),
                    exceptions=(), exception_spans=(), exception_of="")
    view = View(sources={clause.span.source: projected}, clauses=(frame,))
    try:
        license_clause(frame, view)
    except Exception:
        return False
    return True


def _reader_candidate(comparison, event, relation, source):
    """Select only an existing comparison reading whose event frame gains a
    separately verifiable source projection.
    """
    if comparison.licenses(event, source):
        return False
    if event.conditions or event.exceptions or event.exception_of:
        return False
    relation_ok = (comparison.licenses(relation, source)
                   or _relation_shape(relation, source))
    if not relation_ok:
        return False
    roles = {role.name: role for role in relation.roles}
    if len(roles) != len(relation.roles) or set(roles) != _COMPARISON_ROLES:
        return False
    agent_roles = [role for role in event.roles if role.name == "agent"]
    if len(agent_roles) != 1:
        return False
    agent = agent_roles[0]
    entity = roles["entity"]
    standard = roles["standard"].span
    dimension = roles["dimension"].span
    direction = roles["direction"].span
    if (entity.span != agent.span or entity.term != agent.term
            or not _topic_gap(source, agent.span.end, standard.start)
            or dimension != direction
            or source[standard.end:dimension.start] != "より"
            or source.count("より") != 1):
        return False
    if comparison.licenses(relation, source):
        return _masked_frame_licenses(event, source, standard.start, direction.end)
    return _projected_frame_licenses(event, source, standard.start, direction.end)


def reads(ctx):
    """Compose the existing comparison reading for a strict topic comparison."""
    if (len(ctx.tokens) > ctx.budget.max_tokens
            or len(ctx.clauses) > ctx.budget.max_clauses):
        return None
    comparison = _comparison_rule()
    if comparison is None:
        return None
    original = comparison.reads(ctx)
    if original is None or not original.clauses:
        return None
    if (len(original.clauses) + len(original.consumed_spans) + len(original.notes)
            > ctx.budget.max_steps):
        return None

    relations = [clause for clause in original.clauses
                 if clause.predicate == "comparison"]
    events = [clause for clause in original.clauses
              if clause.predicate != "comparison"]
    if len(relations) != 1 or len(events) != 1:
        return None
    offset = ctx.sentence_span.start
    event = _relative_clause(events[0], offset, ctx.sentence_text)
    relation = _relative_clause(relations[0], offset, ctx.sentence_text)
    if (event is None or relation is None
            or not _reader_candidate(comparison, event, relation, ctx.sentence_text)):
        return None

    clauses = (replace(events[0], rule="gold_comparison"),
               replace(relations[0], rule="gold_comparison"))
    if len(clauses) + len(original.consumed_spans) + len(original.notes) > ctx.budget.max_steps:
        return None
    return Reading(clauses, original.consumed_spans, original.notes)


def _license_event(clause, source, comparison):
    if clause.conditions or clause.exceptions or clause.exception_of:
        return False
    prior = replace(clause, rule="comparison")
    if comparison.licenses(prior, source):
        return True

    start, end = clause.span.start, clause.span.end
    if not (0 <= start < end <= len(source)):
        return False
    sentence = source[start:end]
    agent_roles = [role for role in clause.roles if role.name == "agent"]
    if len(agent_roles) != 1:
        return False
    agent = agent_roles[0]
    local_agent_end = agent.span.end - start
    if local_agent_end < 0 or local_agent_end >= len(sentence):
        return False
    particle = sentence[local_agent_end:local_agent_end + 1]
    if particle not in ("は", "が"):
        return False
    standard_start = agent.span.end + 1
    if source[standard_start:standard_start + 1] in ("、", ",", "，"):
        standard_start += 1
    markers = []
    cursor = sentence.find("より")
    while cursor >= 0:
        markers.append(start + cursor)
        cursor = sentence.find("より", cursor + 2)
    if len(markers) != 1:
        return False
    marker = markers[0]
    if marker <= standard_start:
        return False
    standard = source[standard_start:marker]
    if not standard or any(char in standard for char in "。、，,\n？?！! "):
        return False

    descriptor_start = marker + 2
    following_roles = [role for role in clause.roles
                       if role.span.start >= descriptor_start
                       and role.name != "agent"]
    if not following_roles:
        return False
    next_role = min(following_roles, key=lambda role: role.span.start)
    tail = source[descriptor_start:next_role.span.start]
    descriptor = next((form for form in _COMPARATIVE_SURFACE
                        if tail.startswith(form)
                        and all(char in _PUNCTUATION or char in _CASE_PARTICLES
                                for char in tail[len(form):])), None)
    if descriptor is None:
        return False
    descriptor_end = descriptor_start + len(descriptor)
    if _masked_frame_licenses(clause, source, standard_start, descriptor_end):
        return True
    return _projected_frame_licenses(clause, source, standard_start,
                                     next_role.span.start)


def licenses(clause, source):
    """Check the comparison relation and the source-bounded event independently."""
    comparison = _comparison_rule()
    if comparison is None or clause.rule != "gold_comparison":
        return False
    try:
        if clause.predicate == "comparison":
            original = replace(clause, rule="comparison")
            return (comparison.licenses(original, source)
                    or _relation_shape(original, source))
        return _license_event(clause, source, comparison)
    except Exception:
        return False


register(Construction(
    name="gold_comparison",
    priority=30,
    reads=reads,
    licenses=licenses,
    refines=("comparison",),
))
