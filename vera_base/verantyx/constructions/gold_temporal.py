"""Source-bounded event ordering for explicit Japanese temporal clauses."""
from __future__ import annotations

import hashlib
import re
from dataclasses import replace

from ..semantic_ir import Clause, Role, Span, Variable
from . import Construction, ConstructionContext, Reading, TypedNote, register


NAME = "gold_temporal"
_MARKER_RE = re.compile(r"てから|でから|後(?:に|で|、)|前(?:に|で|、)")
_PARTICLES = {
    "agent": ("は", "が"),
    "patient": ("を",),
    "recipient": ("に", "へ"),
}
_CLEARABLE = frozenset(("multiple predicates need explicit clause scope",
                        "unrepresented source content"))
_FUNCTION_POS = frozenset(("助詞", "助動詞", "補助記号", "記号"))


def _inside(span: Span, sentence: Span) -> bool:
    return (span.source == sentence.source
            and sentence.start <= span.start < span.end <= sentence.end)


def _major_pos(token: object) -> str:
    pos = getattr(token, "pos", ())
    if isinstance(pos, (tuple, list)) and pos:
        return str(pos[0])
    return str(pos).split(",", 1)[0]


def _normalized_role(ctx: ConstructionContext, role: Role) -> Role | None:
    if (role.name not in _PARTICLES or not isinstance(role.term, str) or not role.term
            or not _inside(role.span, ctx.sentence_span)):
        return None
    start = role.span.start - ctx.sentence_span.start
    end = role.span.end - ctx.sentence_span.start
    exact = ctx.sentence_text[start:end]
    if exact != role.span.text or (role.term != exact and not exact.startswith(role.term)):
        return None
    if not any(ctx.sentence_text.startswith(particle, end)
               for particle in _PARTICLES[role.name]):
        return None
    return replace(role, term=exact, rule=NAME)


def _event_roles(ctx: ConstructionContext, clause: Clause, marker: Span,
                 other: Clause) -> tuple[Role, ...]:
    before_marker = clause.predicate_span.end <= marker.start
    after_marker = clause.predicate_span.start >= marker.end
    if not (before_marker or after_marker):
        return ()
    roles: list[Role] = []
    for role in clause.roles:
        normalized = _normalized_role(ctx, role)
        if normalized is None:
            continue
        role_before = role.span.end <= marker.start
        role_after = role.span.start >= marker.end
        shared_matrix_topic = (
            after_marker and clause.predicate_span.start > marker.end
            and role.name == "agent" and role_before
            and role.span.end <= min(clause.predicate_span.start, other.predicate_span.start)
            and ctx.sentence_text.startswith("は", role.span.end - ctx.sentence_span.start)
        )
        if ((before_marker and role_before) or (after_marker and role_after)
                or shared_matrix_topic):
            roles.append(normalized)
    return tuple(roles)


def _event_scoped_clause(ctx: ConstructionContext, clause: Clause,
                         roles: tuple[Role, ...]) -> Clause | None:
    if not _inside(clause.predicate_span, ctx.sentence_span):
        return None
    identity = hashlib.sha256(
        f"{clause.id}:{clause.predicate_span.start}:{','.join(role.name for role in roles)}".encode("utf-8")
    ).hexdigest()[:24]
    return replace(
        clause,
        id=identity,
        event=Variable("temporal_" + identity, "event"),
        roles=roles,
        span=ctx.sentence_span,
        body_span=ctx.sentence_span,
        rule=NAME,
        unsupported=(),
        conditions=(),
        condition_spans=(),
        exceptions=(),
        exception_spans=(),
        exception_of="",
    )


def _context_content_covered(
    ctx: ConstructionContext, clauses: tuple[Clause, ...], marker: Span,
) -> bool:
    spans = [marker]
    spans.extend(clause.predicate_span for clause in clauses)
    spans.extend(role.span for clause in clauses for role in clause.roles)
    for token in ctx.tokens:
        if _major_pos(token.token) in _FUNCTION_POS:
            continue
        if not any(span.start - ctx.sentence_span.start <= token.start
                   and token.end <= span.end - ctx.sentence_span.start for span in spans):
            return False
    return True


def reads(ctx: ConstructionContext) -> Reading | None:
    """Read only event-local spans around one explicit temporal marker."""
    if (len(ctx.tokens) > ctx.budget.max_tokens
            or len(ctx.clauses) > ctx.budget.max_clauses
            or len(ctx.sentence_text) > ctx.budget.max_steps):
        return None
    sentence = ctx.sentence_text
    matches = list(_MARKER_RE.finditer(sentence))
    if len(matches) != 1:
        return None
    match = matches[0]
    marker = sentence[match.start():match.end()]
    marker_span = Span(
        source=ctx.sentence_span.source,
        start=ctx.sentence_span.start + match.start(),
        end=ctx.sentence_span.start + match.end(),
        text=marker,
    )

    before = [clause for clause in ctx.clauses
              if clause.predicate_span.end <= marker_span.start]
    after = [clause for clause in ctx.clauses
             if clause.predicate_span.start >= marker_span.end]
    if not before or not after:
        return None
    nearest_left_end = max(clause.predicate_span.end for clause in before)
    nearest_right_start = min(clause.predicate_span.start for clause in after)
    nearest_before = [clause for clause in before
                      if clause.predicate_span.end == nearest_left_end]
    nearest_after = [clause for clause in after
                     if clause.predicate_span.start == nearest_right_start]
    if len(nearest_before) != 1 or len(nearest_after) != 1:
        return None
    left, right = nearest_before[0], nearest_after[0]
    if (left is right or left.rule != "frame" or right.rule != "frame"
            or left.polarity != "+" or right.polarity != "+"
            or left.modality != "assert" or right.modality != "assert"
            or left.conditions or right.conditions or left.exceptions or right.exceptions):
        return None

    selected = (left, right)
    event_by_id: dict[str, Clause] = {}
    notes: list[TypedNote] = [TypedNote("temporal_order", marker_span,
                                         "before" if marker.startswith("前") else "after")]
    for clause in selected:
        other = right if clause is left else left
        roles = _event_roles(ctx, clause, marker_span, other)
        event_clause = _event_scoped_clause(ctx, clause, roles)
        if event_clause is not None:
            event_by_id[clause.id] = event_clause
        if len(roles) < len(clause.roles) or clause.unsupported:
            detail = "; ".join(clause.unsupported) or "unlicensed role span retained as ambiguity"
            notes.append(TypedNote("temporal_scope_unresolved", clause.predicate_span, detail))

    relation_clause: Clause | None = None
    if len(ctx.clauses) == 2:
        normalized_by_id = {
            clause.id: tuple(_normalized_role(ctx, role) for role in clause.roles)
            for clause in selected
        }
        left_roles = normalized_by_id[left.id]
        right_roles = normalized_by_id[right.id]
        source_roles = tuple(role for role in (*left_roles, *right_roles) if role is not None)
        if (len(source_roles) == sum(len(clause.roles) for clause in selected)
                and set(left.unsupported + right.unsupported).issubset(_CLEARABLE)
                and _context_content_covered(ctx, selected, marker_span)):
            predicate = "before" if marker.startswith("前") else "after"
            earlier, later = (right, left) if predicate == "before" else (left, right)
            relation_id = hashlib.sha256(
                f"{ctx.sentence_span.source}:{marker_span.start}:{earlier.id}:{later.id}".encode("utf-8")
            ).hexdigest()[:24]
            relation_roles = [
                Role("earlier", event_by_id.get(earlier.id, earlier).event,
                     earlier.predicate_span, NAME),
                Role("later", event_by_id.get(later.id, later).event,
                     later.predicate_span, NAME),
            ]
            relation_roles.extend(
                Role("earlier_" + role.name, role.term, role.span, NAME)
                for role in normalized_by_id[earlier.id]
            )
            relation_roles.extend(
                Role("later_" + role.name, role.term, role.span, NAME)
                for role in normalized_by_id[later.id]
            )
            relation_span = ctx.sentence_span
            relation_clause = Clause(
                id=relation_id,
                event=Variable("order_" + relation_id, "event"),
                predicate=predicate,
                predicate_span=marker_span,
                roles=tuple(relation_roles),
                span=relation_span,
                body_span=relation_span,
                polarity="+",
                modality="assert",
                time="",
                rule=NAME,
                sovereign=earlier.sovereign,
                family=earlier.family,
            )

    consumed = {marker_span}
    event_clauses = tuple(event_by_id.values())
    for clause in event_clauses:
        consumed.add(clause.span)
        consumed.add(clause.predicate_span)
        consumed.update(role.span for role in clause.roles)
    if relation_clause is not None:
        consumed.add(relation_clause.span)
        consumed.update((left.predicate_span, right.predicate_span))
        consumed.update(role.span for role in relation_clause.roles)
    consumed_spans = tuple(sorted(consumed, key=lambda span: (span.start, span.end)))
    if not event_clauses and relation_clause is None:
        return None
    clauses = tuple(event_clauses) + ((relation_clause,) if relation_clause is not None else ())
    return Reading(
        clauses=clauses,
        consumed_spans=consumed_spans,
        notes=tuple(notes),
    )


def _tagged_tokens(sentence: str) -> list[tuple[int, int, object]] | None:
    try:
        from fugashi import Tagger
        tagged = Tagger()(sentence)
    except Exception:
        return None
    result: list[tuple[int, int, object]] = []
    offset = 0
    for token in tagged:
        offset += len(token.white_space or "")
        start = offset
        end = start + len(token.surface)
        result.append((start, end, token))
        offset = end
        if len(result) > 256:
            return None
    return result


def _sentence_bounds(source: str, start: int, end: int) -> tuple[int, int]:
    left = 0
    right = len(source)
    for mark in ("。", "！", "？", "!", "?", "\n"):
        pos = source.rfind(mark, 0, start)
        if pos >= 0:
            left = max(left, pos + len(mark))
        pos = source.find(mark, end)
        if pos >= 0:
            right = min(right, pos + len(mark))
    return left, right


def _event_temporal_context(
    clause: Clause, source: str,
) -> tuple[Span, Span, Span] | None:
    left, right = _sentence_bounds(source, clause.predicate_span.start,
                                   clause.predicate_span.end)
    sentence = source[left:right]
    matches = list(_MARKER_RE.finditer(sentence))
    if len(matches) != 1:
        return None
    marker = matches[0]
    tagged = _tagged_tokens(sentence)
    if tagged is None:
        return None
    predicates: list[tuple[int, int, str]] = []
    for start, end, token in tagged:
        feature = token.feature
        if getattr(feature, "pos1", "") == "動詞":
            predicates.append((start, end, getattr(feature, "lemma", "")))
    if len(predicates) != 2:
        return None
    pred_start = clause.predicate_span.start - left
    pred_end = clause.predicate_span.end - left
    current = next((item for item in predicates
                    if item == (pred_start, pred_end, clause.predicate)), None)
    if current is None:
        return None
    before = next((item for item in predicates if item[1] <= marker.start()), None)
    after = next((item for item in predicates if item[0] >= marker.end()), None)
    if before is None or after is None:
        return None
    marker_span = Span(clause.span.source, left + marker.start(), left + marker.end(),
                       sentence[marker.start():marker.end()])
    before_span = Span(clause.span.source, left + before[0], left + before[1],
                       sentence[before[0]:before[1]])
    after_span = Span(clause.span.source, left + after[0], left + after[1],
                      sentence[after[0]:after[1]])
    return marker_span, before_span, after_span


def _event_temporal_link(clause: Clause, source: str) -> bool:
    return _event_temporal_context(clause, source) is not None


def _source_temporal_covered(clause: Clause, source: str) -> bool:
    context = _event_temporal_context(clause, source)
    if context is None:
        return False
    marker, before, after = context
    span = clause.span
    covered = [
        (clause.predicate_span.start - span.start, clause.predicate_span.end - span.start),
        (marker.start - span.start, marker.end - span.start),
        (before.start - span.start, before.end - span.start),
        (after.start - span.start, after.end - span.start),
    ]
    covered.extend((role.span.start - span.start, role.span.end - span.start)
                   for role in clause.roles)
    tagged = _tagged_tokens(span.text)
    if tagged is None:
        return False
    for start, end, token in tagged:
        major = str(token.pos).split(",", 1)[0]
        if major in _FUNCTION_POS or any(a <= start and end <= b for a, b in covered):
            continue
        if (major == "名詞" and any(source.startswith(particle, span.start + end)
                                    for particle in ("は", "が", "を", "に", "で", "と", "へ"))):
            continue
        return False
    return True


def _licenses_relation(clause: Clause, source: str) -> bool:
    span = clause.span
    marker_span = clause.predicate_span
    if (clause.predicate not in {"before", "after"}
            or not (0 <= span.start < span.end <= len(source))
            or source[span.start:span.end] != span.text
            or not (span.start <= marker_span.start < marker_span.end <= span.end)
            or source[marker_span.start:marker_span.end] != marker_span.text
            or marker_span.source != span.source):
        return False

    if marker_span.text in {"てから", "でから", "後に", "後で", "後、"}:
        expected = "after"
    elif marker_span.text in {"前に", "前で", "前、"}:
        expected = "before"
    else:
        return False
    if clause.predicate != expected or len(clause.roles) < 2:
        return False

    if clause.roles[0].name != "earlier" or clause.roles[1].name != "later":
        return False
    roles = {role.name: role for role in clause.roles}
    if len(roles) != len(clause.roles) or not {"earlier", "later"}.issubset(roles):
        return False
    earlier, later = roles["earlier"], roles["later"]
    if (not isinstance(clause.event, Variable) or clause.event.sort != "event"
            or not isinstance(earlier.term, Variable) or not isinstance(later.term, Variable)
            or earlier.term.sort != "event" or later.term.sort != "event"
            or earlier.term == later.term or clause.event in {earlier.term, later.term}
            or earlier.rule != NAME or later.rule != NAME):
        return False
    if not (_inside(earlier.span, span) and _inside(later.span, span)):
        return False
    if (source[earlier.span.start:earlier.span.end] != earlier.span.text
            or source[later.span.start:later.span.end] != later.span.text
            or earlier.span.start == earlier.span.end
            or later.span.start == later.span.end):
        return False

    if expected == "after":
        order_ok = earlier.span.end <= marker_span.start < marker_span.end <= later.span.start
    else:
        order_ok = later.span.end <= marker_span.start < marker_span.end <= earlier.span.start

    covered = [
        (earlier.span.start - span.start, earlier.span.end - span.start),
        (later.span.start - span.start, later.span.end - span.start),
        (marker_span.start - span.start, marker_span.end - span.start),
    ]
    for role in clause.roles[2:]:
        side, _, name = role.name.partition("_")
        particles = _PARTICLES.get(name, ())
        if (side not in {"earlier", "later"} or not particles
                or not isinstance(role.term, str) or role.rule != NAME
                or not _inside(role.span, span)
                or source[role.span.start:role.span.end] != role.span.text
                or role.term != role.span.text
                or not any(source.startswith(particle, role.span.end) for particle in particles)):
            return False
        source_side = "before" if role.span.end <= marker_span.start else (
            "after" if role.span.start >= marker_span.end else "overlap")
        expected_side = (("before" if side == "earlier" else "after") if expected == "after"
                         else ("after" if side == "earlier" else "before"))
        if source_side != expected_side:
            matrix_side = "later" if expected == "after" else "earlier"
            shared_topic = (
                name == "agent" and side == matrix_side and source_side == "before"
                and role.span.end <= min(earlier.span.start, later.span.start)
                and source.startswith("は", role.span.end)
            )
            if not shared_topic:
                return False
        covered.append((role.span.start - span.start, role.span.end - span.start))
    if not _source_content_covered(span.text, covered):
        return False
    return (order_ok and clause.polarity == "+" and clause.modality == "assert"
            and not clause.conditions and not clause.exceptions and not clause.unsupported)


def _source_content_covered(sentence: str, spans: list[tuple[int, int]]) -> bool:
    tagged = _tagged_tokens(sentence)
    if tagged is None:
        return False
    for start, end, token in tagged:
        major = str(token.pos).split(",", 1)[0]
        if major in _FUNCTION_POS:
            continue
        if not any(a <= start and end <= b for a, b in spans):
            return False
    return True


def _licenses_repaired_frame(clause: Clause, source: str) -> bool:
    span = clause.span
    pred = clause.predicate_span
    context = _event_temporal_context(clause, source)
    if (not (0 <= span.start < span.end <= len(source))
            or source[span.start:span.end] != span.text
            or not (span.start <= pred.start < pred.end <= span.end)
            or source[pred.start:pred.end] != pred.text
            or clause.polarity != "+" or clause.modality != "assert"
            or clause.unsupported or clause.conditions or clause.exceptions
            or not isinstance(clause.event, Variable) or clause.event.sort != "event"
            or context is None):
        return False

    marker, before, after = context
    pred_before = pred.end <= marker.start
    covered = [(pred.start - span.start, pred.end - span.start)]
    names: set[str] = set()
    for role in clause.roles:
        if (role.name in names or role.span.source != span.source
                or not (span.start <= role.span.start < role.span.end <= span.end)
                or source[role.span.start:role.span.end] != role.span.text
                or role.term != role.span.text or role.rule != NAME):
            return False
        names.add(role.name)
        particles = _PARTICLES.get(role.name, ())
        if (not particles
                or not any(source.startswith(p, role.span.end) for p in particles)):
            return False
        role_before = role.span.end <= marker.start
        role_after = role.span.start >= marker.end
        same_side = role_before if pred_before else role_after
        shared_topic = (
            not pred_before and role_before and role.name == "agent"
            and role.span.end <= before.start and source.startswith("は", role.span.end)
        )
        if not (same_side or shared_topic):
            return False
        covered.append((role.span.start - span.start, role.span.end - span.start))
    return _source_temporal_covered(clause, source)


def licenses(clause: Clause, source: str) -> bool:
    """Check the source marker and exact event/argument spans without reading."""
    if clause.rule != NAME or not isinstance(source, str):
        return False
    if clause.predicate in {"before", "after"}:
        return _licenses_relation(clause, source)
    return _licenses_repaired_frame(clause, source)


register(Construction(
    name=NAME,
    priority=22,
    reads=reads,
    licenses=licenses,
    refines=("frame", "connective_rel", "time_expr"),
))
