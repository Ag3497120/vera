"""Read explicit case-marked arguments when their source order is scrambled.

The rule reuses a native frame only for arguments whose case particle names
the same role. Unclear case phrases stay as opaque, source-bound roles so a
question about a different, explicit argument can still be checked.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import replace

from . import Construction, ConstructionContext, Reading, register
from ..frames import _predicates, canonical, read_all
from ..semantic_ir import Clause, Role, Span
from ..semantic_names import is_past_aux
from ..typed_edges import _tagger


NAME = "gold_scramble"
_REFUSABLE = frozenset((
    "unrepresented source content", "ambiguous frame role", "unlocated agent",
    "unlocated patient", "unlocated recipient", "ambiguous case role: に",
    "ambiguous case role: で", "ambiguous case role: と",
    "ambiguous case role: から",
))
_CONTENT_POS = frozenset(("名詞", "代名詞", "形容詞", "形状詞", "副詞", "接頭辞", "接尾辞"))
_NP_POS = frozenset(("名詞", "代名詞", "形容詞", "形状詞", "連体詞", "数", "接頭辞", "接尾辞"))
_SINGLE_PARTICLES = frozenset(("が", "は", "を", "に", "で", "と", "へ", "から", "まで"))
_COMPOUND_PARTICLES = (
    "における", "において", "に対して", "によって", "について", "として",
    "と共に", "ともに", "による", "により", "では",
)
_ROLE_MARKERS = {
    "agent": frozenset(("が",)),
    "patient": frozenset(("を",)),
    "recipient": frozenset(("に",)),
    "goal": frozenset(("に",)),
    "location": frozenset(("に",)),
    "time": frozenset(("に", "で")),
    "place": frozenset(("で",)),
    "means": frozenset(("で",)),
    "source": frozenset(("から",)),
    "origin": frozenset(("から",)),
    "limit": frozenset(("まで",)),
    "direction": frozenset(("へ",)),
    "companion": frozenset(("と",)),
    "quotation": frozenset(("と",)),
    "capacity": frozenset(("として",)),
    "accompaniment": frozenset(("と共に", "ともに")),
    "target": frozenset(("に対して",)),
    "topic": frozenset(("について", "では")),
    "setting": frozenset(("において", "における")),
    "by": frozenset(("によって", "による", "により")),
}
_SCOPE = re.compile(
    r"もし|だったなら|はず|かもしれ|だろう|らしい|すべて|全部|それぞれ|"
    r"最後|最初|同時|前後|以前|以後|最新|現在|今日|昨日|今年|午前|午後|"
    r"ただし|以外|除[くき]|のみ|だけ|必ず|場合|なら|たら|れば|とき|時|際|ので|"
    r"[0-9]+[年月日時]"
)
_NEGATIVE_OR_MODAL = re.compile(
    r"(?:ない|なかった|ません|ませんでした|ず|ぬ|べき|たい|ようだ|"
    r"そうだ|かもしれ|だろう)"
)
_UNSAFE_AUX = frozenset(("ない", "なかった", "ません", "ませんでした", "ず", "ぬ",
                         "れる", "られる", "せる", "させる", "たい", "べき"))


def _surface(item) -> str:
    return getattr(item.token, "surface", str(item.token))


def _pos1(item) -> str:
    return getattr(getattr(item.token, "feature", None), "pos1", "")


def _span_ok(span: Span, sentence: Span, text: str) -> bool:
    return (isinstance(span, Span) and span.source == sentence.source
            and sentence.start <= span.start < span.end <= sentence.end
            and span.text == text[span.start - sentence.start:span.end - sentence.start])


def _particle_after(tokens, end: int) -> str:
    """Return one exact case sequence directly after a local token boundary."""
    first = next((i for i, item in enumerate(tokens) if item.start == end), None)
    if first is None or _pos1(tokens[first]) != "助詞":
        return ""
    joined = ""
    for item in tokens[first:first + 5]:
        if _pos1(item) != "助詞":
            break
        joined += _surface(item)
        if joined in _COMPOUND_PARTICLES:
            return joined
        if joined in _SINGLE_PARTICLES:
            return joined
        if not any(marker.startswith(joined) for marker in _COMPOUND_PARTICLES):
            break
    return ""


def _np_before(tokens, particle_index: int) -> tuple[int, int] | None:
    """Bound a local nominal phrase ending immediately before a case particle."""
    first = particle_index
    cursor = particle_index - 1
    has_content = False
    while cursor >= 0:
        item = tokens[cursor]
        surface, pos = _surface(item), _pos1(item)
        if pos in _NP_POS:
            first = cursor
            has_content = True
            cursor -= 1
            continue
        if surface == "の" and pos == "助詞" and has_content:
            first = cursor
            cursor -= 1
            continue
        if surface == "な" and pos == "助動詞" and has_content:
            first = cursor
            cursor -= 1
            continue
        if surface in ("・", "＝", "=", "-", "‐", "–", "/") and has_content:
            first = cursor
            cursor -= 1
            continue
        break
    if not has_content:
        return None
    return tokens[first].start, tokens[particle_index - 1].end


def _case_phrase_spans(ctx: ConstructionContext) -> tuple[Span, ...]:
    """List exact single-particle NPs without deciding their semantic roles."""
    found = []
    pred_start = min((c.predicate_span.start - ctx.sentence_span.start
                     for c in ctx.clauses if c.span == ctx.sentence_span),
                    default=len(ctx.sentence_text))
    for i, item in enumerate(ctx.tokens):
        if item.start >= pred_start or _pos1(item) != "助詞":
            continue
        if _surface(item) not in _SINGLE_PARTICLES:
            continue
        bounds = _np_before(ctx.tokens, i)
        if bounds is None:
            continue
        start, end = bounds
        text = ctx.sentence_text[start:end]
        if text:
            found.append(Span(ctx.sentence_span.source,
                              ctx.sentence_span.start + start,
                              ctx.sentence_span.start + end, text))
    return tuple(found)


def _scrambled(roles: tuple[Role, ...]) -> bool:
    order = {"agent": 0, "recipient": 1, "patient": 2}
    core = sorted((r for r in roles if r.name in order), key=lambda r: r.span.start)
    ranks = [order[r.name] for r in core]
    return len(ranks) >= 2 and ranks != sorted(ranks)


def _local_clauses(ctx: ConstructionContext) -> list[Clause]:
    return [c for c in ctx.clauses if c.span.source == ctx.sentence_span.source
            and c.span.start == ctx.sentence_span.start and c.span.end == ctx.sentence_span.end]


def _case_frames_already_reads(ctx: ConstructionContext) -> bool:
    """Let the count-backed case rule own any ambiguity it can resolve."""
    try:
        from .case_frames import reads as read_case_frames
        reading = read_case_frames(ctx)
    except Exception:
        return False
    return bool(reading and any(c.span == ctx.sentence_span for c in reading.clauses))


def reads(ctx: ConstructionContext) -> Reading | None:
    if (len(ctx.tokens) > ctx.budget.max_tokens
            or len(ctx.clauses) * 2 + len(ctx.tokens) * 4 > ctx.budget.max_steps
            or ctx.sentence_span.text != ctx.sentence_text
            or ctx.sentence_span.end - ctx.sentence_span.start != len(ctx.sentence_text)):
        return None
    local = _local_clauses(ctx)
    if len(local) != 1:
        return None
    base = local[0]
    if (base.rule != "frame" or not base.unsupported
            or not set(base.unsupported).issubset(_REFUSABLE)
            or base.conditions or base.exceptions or base.condition_spans
            or base.exception_spans or base.exception_of
            or base.polarity != "+" or base.modality != "assert"
            or base.time not in ("past", "nonpast")
            or base.span != ctx.sentence_span or base.body_span != ctx.sentence_span
            or _SCOPE.search(ctx.sentence_text) or _NEGATIVE_OR_MODAL.search(ctx.sentence_text)
            or any(ch in ctx.sentence_text for ch in "「『")):
        return None
    if any(_pos1(item) == "助動詞" and _surface(item) in _UNSAFE_AUX for item in ctx.tokens):
        return None
    if _case_frames_already_reads(ctx):
        return None

    case_spans = {(span.start, span.end) for span in _case_phrase_spans(ctx)}

    roles: list[Role] = []
    unresolved: list[Span] = []
    for old in base.roles:
        if not _span_ok(old.span, ctx.sentence_span, ctx.sentence_text):
            return None
        marker = _particle_after(ctx.tokens, old.span.end - ctx.sentence_span.start)
        if old.name in ("agent", "patient", "recipient"):
            if (marker in _ROLE_MARKERS.get(old.name, ())
                    and old.span.end <= base.predicate_span.start
                    and old.term == canonical(old.span.text)):
                roles.append(Role(old.name, canonical(old.span.text), old.span, "frame"))
            else:
                if (old.span.start, old.span.end) not in case_spans:
                    return None
                unresolved.append(old.span)
        elif (old.name in _ROLE_MARKERS and marker in _ROLE_MARKERS[old.name]
              and old.term == old.span.text):
            roles.append(Role(old.name, old.term, old.span, old.rule))
        else:
            if (old.span.start, old.span.end) not in case_spans:
                return None
            unresolved.append(old.span)

    if len({r.name for r in roles}) != len(roles):
        return None

    # Recover case-bounded phrases omitted by the native frame as unknown
    # slots. They remain unusable as agent/patient/recipient evidence.
    known_intervals = [(r.span.start, r.span.end) for r in roles]
    unresolved_intervals = [(s.start, s.end) for s in unresolved]
    for phrase in _case_phrase_spans(ctx):
        if any(a <= phrase.start and phrase.end <= b for a, b in unresolved_intervals):
            continue
        if any(phrase.start < b and a < phrase.end for a, b in known_intervals):
            continue
        if any(phrase.start < b and a < phrase.end for a, b in unresolved_intervals):
            return None
        has_uncovered_content = any(
            item.start < phrase.end - ctx.sentence_span.start
            and phrase.start - ctx.sentence_span.start < item.end
            and _pos1(item) in _CONTENT_POS
            and not any(a <= ctx.sentence_span.start + item.start
                        and ctx.sentence_span.start + item.end <= b
                        for a, b in known_intervals + unresolved_intervals)
            for item in ctx.tokens
        )
        if has_uncovered_content:
            unresolved.append(phrase)
            unresolved_intervals.append((phrase.start, phrase.end))

    # Every source content token must belong to a checked role, an opaque
    # case-bounded phrase, or the predicate. Free modifiers remain a refusal.
    covered = [(r.span.start, r.span.end) for r in roles]
    covered.extend((s.start, s.end) for s in unresolved)
    covered.append((base.predicate_span.start, base.predicate_span.end))
    pred_index = next((i for i, item in enumerate(ctx.tokens)
                       if item.start == base.predicate_span.start - ctx.sentence_span.start), None)
    if pred_index is None:
        return None
    if (base.predicate.endswith("する") and pred_index > 0
            and getattr(ctx.tokens[pred_index - 1].token, "feature", None) is not None
            and getattr(ctx.tokens[pred_index - 1].token.feature, "pos1", "") == "名詞"):
        prior = ctx.tokens[pred_index - 1]
        covered.append((ctx.sentence_span.start + prior.start,
                        ctx.sentence_span.start + prior.end))
    for item in ctx.tokens:
        if _pos1(item) in _CONTENT_POS:
            absolute_start = ctx.sentence_span.start + item.start
            absolute_end = ctx.sentence_span.start + item.end
            if not any(a <= absolute_start and absolute_end <= b for a, b in covered):
                return None
        if (_pos1(item) == "動詞" and not any(
                a <= ctx.sentence_span.start + item.start
                and ctx.sentence_span.start + item.end <= b for a, b in covered)):
            return None

    roles.extend(
        Role(f"unresolved_{index}", span.text, span, "literal")
        for index, span in enumerate(sorted(set(unresolved), key=lambda s: (s.start, s.end)))
    )
    roles_tuple = tuple(sorted(roles, key=lambda r: (r.span.start, r.span.end, r.name)))
    if not _scrambled(roles_tuple):
        return None

    signature = (f"{NAME}:{base.span.source}:{base.span.start}:{base.predicate_span.start}:"
                 + ",".join(f"{r.name}={r.span.start}:{r.span.end}" for r in roles_tuple))
    digest = hashlib.sha256(signature.encode("utf-8")).hexdigest()[:24]
    built = replace(base, id=digest,
                    event=replace(base.event, name="event_" + digest, sort="event"),
                    roles=roles_tuple, rule=NAME, unsupported=())
    return Reading((built,), (ctx.sentence_span,), ())


def _positions(raw: str, words) -> list[int]:
    out = []
    cursor = 0
    for word in words:
        at = raw.find(word.surface, cursor)
        if at < 0:
            return []
        out.append(at)
        cursor = at + len(word.surface)
    return out


def _source_case_phrases(raw: str, words, positions) -> tuple[tuple[int, int, str], ...]:
    phrases = []
    for i, word in enumerate(words):
        if word.feature.pos1 != "助詞" or word.surface not in _SINGLE_PARTICLES:
            continue
        cursor = i - 1
        first = i
        has_content = False
        while cursor >= 0:
            item = words[cursor]
            pos, surface = item.feature.pos1, item.surface
            if pos in _NP_POS:
                first = cursor
                has_content = True
                cursor -= 1
                continue
            if surface == "の" and pos == "助詞" and has_content:
                first = cursor
                cursor -= 1
                continue
            if surface == "な" and pos == "助動詞" and has_content:
                first = cursor
                cursor -= 1
                continue
            if surface in ("・", "＝", "=", "-", "‐", "–", "/") and has_content:
                first = cursor
                cursor -= 1
                continue
            break
        if has_content:
            phrases.append((positions[first], positions[i - 1] + len(words[i - 1].surface), word.surface))
    return tuple(phrases)


def _source_particle_after(words, positions, end: int) -> tuple[str, int | None]:
    first = next((i for i, at in enumerate(positions) if at == end), None)
    if first is None or words[first].feature.pos1 != "助詞":
        return "", None
    joined = ""
    for i in range(first, min(len(words), first + 5)):
        word = words[i]
        if word.feature.pos1 != "助詞":
            break
        joined += word.surface
        if joined in _COMPOUND_PARTICLES or joined in _SINGLE_PARTICLES:
            return joined, first
        if not any(marker.startswith(joined) for marker in _COMPOUND_PARTICLES):
            break
    return "", None


def _resolved_case_role(role: Role, marker: str, marker_index: int | None,
                        raw: str, words, positions, predicate: str) -> bool:
    if role.name not in ("goal", "location", "time", "place", "means",
                         "companion", "quotation", "source", "origin"):
        return True
    if marker_index is None:
        return False
    try:
        from ..semantic_reader import _case_role
        quoted = (marker == "と" and raw[:positions[marker_index]].rstrip().endswith("」"))
        previous = words[marker_index - 1] if marker_index else None
        person = bool(previous and (
            previous.feature.pos3 == "人名" or role.span.text.endswith(("さん", "氏"))))
        expected, _ = _case_role(marker, role.span.text, predicate,
                                 quoted=quoted, person=person)
    except Exception:
        return False
    return expected == role.name or (role.name == "origin" and expected == "source")


def licenses(clause: Clause, source: str) -> bool:
    """Independently license explicit scrambled roles and opaque case NPs."""
    if (not isinstance(clause, Clause) or clause.rule != NAME or clause.unsupported
            or not isinstance(source, str) or clause.span.source == ""
            or clause.span.start < 0 or clause.span.end > len(source)
            or clause.span.start >= clause.span.end
            or source[clause.span.start:clause.span.end] != clause.span.text
            or clause.body_span != clause.span or clause.polarity != "+"
            or clause.modality != "assert" or clause.time not in ("past", "nonpast")
            or clause.conditions or clause.condition_spans or clause.exceptions
            or clause.exception_spans or clause.exception_of or _SCOPE.search(clause.span.text)
            or _NEGATIVE_OR_MODAL.search(clause.span.text)
            or any(ch in clause.span.text for ch in "「『")):
        return False
    raw = clause.span.text
    try:
        words = list(_tagger()(raw))
    except Exception:
        return False
    if not words or len(words) > 256:
        return False
    positions = _positions(raw, words)
    if len(positions) != len(words):
        return False
    predicates = _predicates(words)
    frames = read_all(raw)
    if len(predicates) != 1 or len(frames) != 1:
        return False
    pred_index, predicate = predicates[0]
    if (predicate != clause.predicate
            or clause.predicate_span.start != clause.span.start + positions[pred_index]
            or clause.predicate_span.text != words[pred_index].surface
            or clause.predicate_span.end != clause.span.start + positions[pred_index] + len(words[pred_index].surface)
            or frames[0].predicate != clause.predicate):
        return False
    if frames[0].negated:
        return False
    if any(word.feature.pos1 == "助動詞" and word.surface in
           ("ない", "なかった", "ません", "ませんでした", "ず", "ぬ", "れる", "られる", "せる", "させる")
           for word in words):
        return False
    if ("past" if any(is_past_aux(word) for word in words[pred_index + 1:]) else "nonpast") != clause.time:
        return False

    roles = clause.roles
    if len(roles) > 64 or len({r.name for r in roles}) != len(roles):
        return False
    known = [r for r in roles if r.name in _ROLE_MARKERS]
    opaque = [r for r in roles if r.name.startswith("unresolved_")]
    if len(known) + len(opaque) != len(roles):
        return False
    if not _scrambled(roles):
        return False
    for role in known:
        local_start = role.span.start - clause.span.start
        local_end = role.span.end - clause.span.start
        marker, marker_index = _source_particle_after(words, positions, local_end)
        if (role.span.source != clause.span.source
                or not 0 <= local_start < local_end <= len(raw)
                or raw[local_start:local_end] != role.span.text
                or local_end > positions[pred_index]
                or marker not in _ROLE_MARKERS[role.name]
                or not _resolved_case_role(role, marker, marker_index, raw,
                                           words, positions, clause.predicate)):
            return False
        if role.name in ("agent", "patient", "recipient"):
            expected = getattr(frames[0], role.name)
            if not expected or role.term != canonical(role.span.text) or expected != role.term:
                return False
        elif role.term != role.span.text:
            return False

    for role in opaque:
        if (role.span.source != clause.span.source or role.rule != "literal"
                or role.term != role.span.text
                or not 0 <= role.span.start - clause.span.start < role.span.end - clause.span.start <= len(raw)):
            return False
    intervals = [(r.span.start - clause.span.start, r.span.end - clause.span.start) for r in roles]
    if any(a < d and c < b for i, (a, b) in enumerate(intervals)
           for c, d in intervals[i + 1:]):
        return False

    # Every otherwise-unassigned content token must be in a case-bounded
    # opaque phrase. This is independent of the reader's residual-span list.
    phrase_bounds = _source_case_phrases(raw, words, positions)
    for role in opaque:
        local_start = role.span.start - clause.span.start
        local_end = role.span.end - clause.span.start
        if not any((a, b) == (local_start, local_end) for a, b, _ in phrase_bounds):
            return False
    covered = [(r.span.start - clause.span.start, r.span.end - clause.span.start) for r in roles]
    covered.append((positions[pred_index], positions[pred_index] + len(words[pred_index].surface)))
    if (clause.predicate.endswith("する") and pred_index > 0
            and words[pred_index - 1].feature.pos1 == "名詞"
            and words[pred_index - 1].surface + "する" == clause.predicate):
        covered.append((positions[pred_index - 1], positions[pred_index - 1] + len(words[pred_index - 1].surface)))
    for word, start in zip(words, positions):
        if word.feature.pos1 in _CONTENT_POS and not any(
                a <= start and start + len(word.surface) <= b for a, b in covered):
            return False
        if (word.feature.pos1 == "動詞" and not any(
                a <= start and start + len(word.surface) <= b for a, b in covered)):
            return False
    return True


register(Construction(name=NAME, priority=45, reads=reads, licenses=licenses,
                      refines=("case_frames",)))


__all__ = ("licenses", "reads")
