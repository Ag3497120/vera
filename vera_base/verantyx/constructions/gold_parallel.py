"""Read simple, shared-marker Japanese coordinations as one typed role."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

from . import Construction, ConstructionContext, Reading, Span, TypedNote, register
from ..semantic_ir import Clause, Role, Variable


_NAME = "gold_parallel"
_AMBIGUOUS_T_RULE = "case:と:companion|quotation"
_SUPPORTED_UNSUPPORTED = frozenset(("ambiguous case role: と", "duplicate role in clause"))
_ROLE_MARKERS = {
    "agent": ("が", "は"),
    "patient": ("を",),
    "recipient": ("に", "へ"),
    "goal": ("に", "へ"),
    "source": ("から",),
    "topic": ("では", "には", "は"),
    "companion": ("と",),
    "time": ("に", "で"),
    "location": ("で", "に"),
    "means": ("で",),
    "instrument": ("で",),
    "manner": ("で",),
}
_FILLER = frozenset("はがをにへでとから、,，")
_PUNCTUATION = ("。", "！", "？", "!", "?")
_PARALLEL_MARKERS = ("と", "や", "および", "及び", "ならびに", "並びに")
_CHOICE_MARKERS = ("または", "あるいは", "もしくは", "ないし", "どちらか", "どれか",
                   "いずれか", "それとも")
_RECIPIENT_PREDICATES = frozenset((
    "届ける", "送る", "教える", "伝える", "渡す", "配る", "与える", "貸す", "返す",
    "知らせる", "見せる", "示す", "報告する", "呼びかける", "売る", "贈る", "預ける",
    "紹介する", "尋ねる", "聞く", "借りる", "受け取る", "発行する",
))
_TIME_WORDS = frozenset((
    "今日", "昨日", "明日", "今朝", "今夜", "昨夜", "夕方", "夕刻", "夕食", "朝", "昼",
    "夜", "午前", "午後", "当日", "翌日", "先日", "今月", "先月", "来月", "今年",
    "昨年", "来年", "今週", "先週", "来週", "曜日",
))
_TIME_EVENT_WORDS = frozenset((
    "授業", "会議", "出発", "到着", "退職", "卒業", "引っ越し", "移動", "作業", "運動", "試合",
))
_NOMINAL_POS = frozenset(("名詞", "接尾辞", "代名詞", "連体詞", "形容詞", "形状詞"))


def _span_text(ctx: ConstructionContext, span: Span) -> str | None:
    base = ctx.sentence_span.start
    if (span.source != ctx.sentence_span.source or span.start < base
            or span.end > ctx.sentence_span.end or span.end < span.start):
        return None
    local_start, local_end = span.start - base, span.end - base
    value = ctx.sentence_text[local_start:local_end]
    return value if value == span.text else None


def _has_token(ctx: ConstructionContext, start: int, end: int, surface: str) -> bool:
    return any(token.start == start and token.end == end and str(token.token) == surface
               for token in ctx.tokens)


def _surface(token) -> str:
    return str(token.token)


def _feature(token):
    return getattr(token.token, "feature", None)


def _coordination_kind(text: str) -> str | None:
    if any(marker in text for marker in _CHOICE_MARKERS):
        return "choice"
    if "どちらか" in text and len(text) > len("どちらか"):
        return "choice"
    if text.count("か") == 1 and not text.startswith(("何か", "誰か", "どこか", "いつか")):
        at = text.find("か")
        if 0 < at < len(text) - 1:
            return "choice"
    for marker in _PARALLEL_MARKERS:
        if (text.count(marker) == 1 and text.find(marker) > 0
                and text.find(marker) + len(marker) < len(text)):
            return "parallel"
    return None


def _role_rule(text: str) -> str:
    kind = _coordination_kind(text)
    return _NAME + (":" + kind if kind else ":role")


def _time_phrase(text: str, tokens) -> bool:
    words = {_surface(token) for token in tokens}
    lemmas = {getattr(_feature(token), "lemma", "") for token in tokens
              if _feature(token) is not None}
    if words & _TIME_WORDS or lemmas & _TIME_WORDS:
        return True
    if text.endswith(("前", "後", "中", "間")):
        return any(word in text for word in _TIME_WORDS | _TIME_EVENT_WORDS)
    return False


def _nominal_chunk(tokens) -> bool:
    if not tokens:
        return False
    allowed_particles = frozenset(("の", "と", "や", "か", "または", "あるいは", "それとも",
                                   "もしくは", "ないし", "及び", "および", "並びに", "ならびに",
                                   "どれか", "いずれか"))
    for token in tokens:
        surface = _surface(token)
        feature = _feature(token)
        pos = getattr(feature, "pos1", "") if feature is not None else ""
        if surface in ("、", ",", "，"):
            return False
        if pos not in _NOMINAL_POS and not (pos == "助詞" and surface in allowed_particles):
            return False
    return True


def _expand_suru_predicate(ctx: ConstructionContext, clause):
    if not clause.predicate.endswith("する"):
        return clause
    local_start = clause.predicate_span.start - ctx.sentence_span.start
    previous = [token for token in ctx.tokens if token.end == local_start]
    if len(previous) != 1:
        return clause
    token = previous[0]
    feature = _feature(token)
    if (getattr(feature, "pos1", "") != "名詞"
            or getattr(feature, "pos3", "") != "サ変可能"
            or _surface(token) != clause.predicate[:-2]):
        return clause
    start = token.start + ctx.sentence_span.start
    text = ctx.sentence_text[token.start:clause.predicate_span.end - ctx.sentence_span.start]
    return replace(clause, predicate_span=Span(clause.predicate_span.source, start,
                                               clause.predicate_span.end, text))


def _role_marker(ctx: ConstructionContext, role: Role, local_end: int,
                 token_index=None) -> str | None:
    markers = _ROLE_MARKERS.get(role.name, ())
    for marker in markers:
        if not ctx.sentence_text.startswith(marker, local_end):
            continue
        token_matches = (_has_token(ctx, local_end, local_end + len(marker), marker)
                         if token_index is None else
                         token_index.get((local_end, local_end + len(marker))) == marker)
        if token_matches:
            return marker
    return None


def _past_form_from_reader(ctx: ConstructionContext, clause) -> bool:
    if (clause.polarity != "+" or clause.modality != "assert" or clause.time != "past"
            or clause.conditions or clause.exceptions or clause.exception_of):
        return False
    start = clause.predicate_span.start - ctx.sentence_span.start
    end = clause.predicate_span.end - ctx.sentence_span.start
    if start < 0 or end < start or end > len(ctx.sentence_text):
        return False
    if ctx.sentence_text[start:end] != clause.predicate_span.text:
        return False
    tail = ctx.sentence_text[end:]
    if tail.endswith(_PUNCTUATION):
        tail = tail[:-1]
    predicate, stem = clause.predicate, clause.predicate_span.text
    if predicate.endswith("する"):
        return ((stem == predicate[:-2] and tail in ("した", "しました"))
                or (stem == predicate[:-2] + "し" and tail in ("た", "ました")))
    if predicate.endswith(("える", "いる")):
        return stem == predicate[:-1] and tail in ("た", "ました")
    if predicate.endswith(("う", "つ", "る")):
        if stem == predicate[:-1] + "っ":
            return tail in ("た", "ました")
        if stem == predicate[:-1]:
            return tail in ("た", "ました")
    if predicate.endswith(("む", "ぶ", "ぬ")):
        return stem == predicate[:-1] + "ん" and tail in ("だ", "でした")
    if predicate.endswith("く"):
        expected = predicate[:-1] + "い"
        if predicate == "行く":
            expected = "行っ"
        return stem == expected and tail in ("た", "ました")
    if predicate.endswith("ぐ"):
        return stem == predicate[:-1] + "い" and tail in ("だ", "でした")
    if predicate.endswith("す"):
        return stem == predicate[:-1] + "し" and tail in ("た", "ました")
    return False


def _reader_gaps_are_closed(ctx: ConstructionContext, clause, roles: tuple[Role, ...]) -> bool:
    base = ctx.sentence_span.start
    spans = [(role.span.start - base, role.span.end - base) for role in roles]
    spans.append((clause.predicate_span.start - base, clause.predicate_span.end - base))
    spans.sort()
    cursor = 0
    for start, end in spans:
        if start < cursor or end < start or end > len(ctx.sentence_text):
            return False
        gap = ctx.sentence_text[cursor:start]
        if any(char not in _FILLER for char in gap):
            return False
        cursor = end
    return _past_form_from_reader(ctx, clause)


def _unread_simple_clause(ctx: ConstructionContext) -> tuple[Clause, tuple[TypedNote, ...]] | None:
    tokens = ctx.tokens
    if not tokens:
        return None
    verbs = [i for i, token in enumerate(tokens)
             if getattr(_feature(token), "pos1", "") == "動詞"]
    if len(verbs) != 1:
        return None
    verb_i = verbs[0]
    verb_token = tokens[verb_i]
    feature = _feature(verb_token)
    predicate = getattr(feature, "lemma", "") if feature is not None else ""
    if not isinstance(predicate, str) or not predicate:
        return None
    predicate_start, predicate_end = verb_token.start, verb_token.end
    if predicate.endswith("する") and verb_i > 0:
        previous = tokens[verb_i - 1]
        previous_feature = _feature(previous)
        if (previous.end == verb_token.start
                and getattr(previous_feature, "pos1", "") == "名詞"
                and getattr(previous_feature, "pos3", "") == "サ変可能"
                and _surface(previous) == predicate[:-2]):
            predicate_start = previous.start

    roles: list[Role] = []
    segment = 0
    marker_i = 0
    while marker_i < verb_i:
        token = tokens[marker_i]
        surface = _surface(token)
        feature = _feature(token)
        if getattr(feature, "pos1", "") != "助詞":
            marker_i += 1
            continue
        marker_end = marker_i + 1
        marker = surface
        if surface in ("で", "に") and marker_i + 1 < verb_i and _surface(tokens[marker_i + 1]) == "は":
            if tokens[marker_i].end != tokens[marker_i + 1].start:
                return None
            marker = surface + "は"
            marker_end += 1

        if marker not in ("が", "は", "を", "に", "へ", "から", "で", "では", "には"):
            marker_i = marker_end
            continue
        start_i = segment
        while start_i < marker_i and _surface(tokens[start_i]) in ("、", ",", "，"):
            start_i += 1
        phrase_tokens = tokens[start_i:marker_i]
        if not _nominal_chunk(phrase_tokens):
            return None
        phrase_start, phrase_end = phrase_tokens[0].start, token.start
        phrase = ctx.sentence_text[phrase_start:phrase_end]
        if not phrase:
            return None

        if marker == "が":
            role_name = "agent"
        elif marker in ("は", "では", "には"):
            role_name = "topic"
        elif marker == "を":
            role_name = "patient"
        elif marker == "へ":
            role_name = "goal"
        elif marker == "から":
            role_name = "source"
        elif marker == "で":
            return None
        elif marker == "に":
            if _time_phrase(phrase, phrase_tokens):
                role_name = "time"
            elif predicate in _RECIPIENT_PREDICATES:
                role_name = "recipient"
            else:
                return None
        else:
            return None
        absolute_start = ctx.sentence_span.start + phrase_start
        absolute_end = ctx.sentence_span.start + phrase_end
        span = Span(ctx.sentence_span.source, absolute_start, absolute_end, phrase)
        roles.append(Role(role_name, phrase, span, _role_rule(phrase)))
        segment = marker_end
        while segment < verb_i and _surface(tokens[segment]) in ("、", ",", "，"):
            segment += 1
        marker_i = marker_end

    if segment < verb_i or not roles or len({role.name for role in roles}) != len(roles):
        return None
    if not any(_coordination_kind(role.term) for role in roles if isinstance(role.term, str)):
        return None
    # A parallel patient and a separate choice have unresolved scope between arguments.
    if (any(role.name == "patient" and role.rule == _NAME + ":parallel" for role in roles)
            and any(role.rule == _NAME + ":choice" for role in roles)):
        return None

    source_span = ctx.sentence_span
    predicate_text = ctx.sentence_text[predicate_start:predicate_end]
    predicate_span = Span(source_span.source, source_span.start + predicate_start,
                          source_span.start + predicate_end, predicate_text)
    clause_id = sha256((f"{_NAME}:{source_span.source}:{source_span.start}:"
                        f"{source_span.end}:{predicate}").encode("utf-8")).hexdigest()[:24]
    clause = Clause(
        id=clause_id,
        event=Variable(name="event_" + clause_id, sort="event"),
        predicate=predicate,
        predicate_span=predicate_span,
        roles=tuple(roles),
        span=source_span,
        body_span=source_span,
        polarity="+",
        modality="assert",
        time="past",
        rule=_NAME,
        sovereign="document",
        family="document",
    )
    if not _past_form_from_reader(ctx, clause) or not _reader_gaps_are_closed(ctx, clause, clause.roles):
        return None
    notes = tuple(
        TypedNote(
            "choice" if role.rule == _NAME + ":choice" else "parallel",
            role.span,
            "explicit source alternatives retained in source order",
        )
        for role in roles if role.rule in (_NAME + ":choice", _NAME + ":parallel")
    )
    return clause, notes


def reads(ctx: ConstructionContext) -> Reading | None:
    if (len(ctx.tokens) > ctx.budget.max_tokens or len(ctx.clauses) > ctx.budget.max_clauses
            or len(ctx.sentence_text) > ctx.budget.max_steps):
        return None
    if (ctx.sentence_span.end - ctx.sentence_span.start != len(ctx.sentence_text)
            or ctx.sentence_span.text != ctx.sentence_text):
        return None
    clauses = tuple(c for c in ctx.clauses
                    if c.span.source == ctx.sentence_span.source
                    and c.span.start == ctx.sentence_span.start
                    and c.span.end == ctx.sentence_span.end)
    if len(clauses) == 0:
        overlaps = tuple(c for c in ctx.clauses
                         if c.span.source == ctx.sentence_span.source
                         and c.span.start < ctx.sentence_span.end
                         and ctx.sentence_span.start < c.span.end)
        if overlaps:
            return None
        parsed = _unread_simple_clause(ctx)
        if parsed is None:
            return None
        clause, notes = parsed
        return Reading((clause,), (clause.span,), notes)
    if len(clauses) != 1:
        return None
    clause = _expand_suru_predicate(ctx, clauses[0])
    if clause.rule != "frame" or not clause.unsupported:
        return None
    if not set(clause.unsupported).issubset(_SUPPORTED_UNSUPPORTED):
        return None
    if "ambiguous case role: と" not in clause.unsupported:
        return None
    if not _past_form_from_reader(ctx, clause):
        return None

    roles = tuple(clause.roles)
    ambiguous = tuple(role for role in roles
                      if role.name == "ambiguous" and role.rule == _AMBIGUOUS_T_RULE)
    if (any(not isinstance(role.term, str) for role in roles)
            or len(roles) * len(roles) * 3 > ctx.budget.max_steps):
        return None
    if not ambiguous or any(role.name == "ambiguous" for role in roles) != bool(ambiguous):
        return None
    if any(role.name == "ambiguous" and role not in ambiguous for role in roles):
        return None

    pairs: list[tuple[Role, Role]] = []
    used_targets: set[Role] = set()
    required_left = set(ambiguous)
    token_index = {(token.start, token.end): str(token.token) for token in ctx.tokens}
    role_texts = {role: _span_text(ctx, role.span) for role in roles}
    optional_subject_left = {
        role for role in roles
        if role.name == "companion" and any(
            target.name == "agent"
            and _role_marker(ctx, target, target.span.end - ctx.sentence_span.start,
                             token_index) in ("は", "が")
            for target in roles
        )
    }
    for left in sorted(required_left | optional_subject_left, key=lambda r: r.span.start):
        left_text = role_texts[left]
        if left_text is None or not isinstance(left.term, str) or left.term != left_text:
            if left in required_left:
                return None
            continue
        left_end = left.span.end - ctx.sentence_span.start
        candidates: list[Role] = []
        for target in roles:
            if target is left or target in used_targets or target.name not in (
                    "agent", "patient", "recipient", "goal"):
                continue
            if target.span.start <= left.span.end:
                continue
            target_text = role_texts[target]
            if target_text is None or not isinstance(target.term, str) or target.term != target_text:
                continue
            target_start = target.span.start - ctx.sentence_span.start
            target_end = target.span.end - ctx.sentence_span.start
            if ctx.sentence_text[left_end:target_start] != "と":
                continue
            if token_index.get((left_end, left_end + 1)) != "と":
                continue
            marker = _role_marker(ctx, target, target_end, token_index)
            if marker is None:
                continue
            if left.name == "companion" and (target.name != "agent" or marker not in ("は", "が")):
                continue
            candidates.append(target)
        if len(candidates) == 1:
            pairs.append((left, candidates[0]))
            used_targets.add(candidates[0])
        elif left in required_left:
            return None

    if any(left not in {pair[0] for pair in pairs} for left in ambiguous):
        return None
    if not pairs or len({left for left, _ in pairs}) != len(pairs):
        return None

    pair_by_target = {target: left for left, target in pairs}
    new_roles: list[Role] = []
    paired_left = {left for left, _ in pairs}
    for role in roles:
        if role in paired_left:
            continue
        left = pair_by_target.get(role)
        if left is None:
            new_roles.append(role)
            continue
        text = ctx.sentence_text[
            left.span.start - ctx.sentence_span.start:role.span.end - ctx.sentence_span.start
        ]
        new_roles.append(Role(
            role.name,
            text,
            Span(role.span.source, left.span.start, role.span.end, text),
            _NAME + ":" + (_coordination_kind(text) or "parallel"),
        ))

    new_roles.sort(key=lambda role: (role.span.start, role.span.end, role.name))
    if len({role.name for role in new_roles}) != len(new_roles):
        return None
    if not _reader_gaps_are_closed(ctx, clause, tuple(new_roles)):
        return None
    if (any(role.name == "patient" and role.rule == _NAME + ":parallel" for role in new_roles)
            and any(_coordination_kind(role.term) == "choice"
                    for role in new_roles if isinstance(role.term, str))):
        return None
    clause_id = sha256((_NAME + ":" + clause.id).encode("utf-8")).hexdigest()[:24]
    event = Variable(name="event_" + clause_id, sort=clause.event.sort)
    revised = replace(clause, id=clause_id, event=event, roles=tuple(new_roles),
                      predicate_span=clause.predicate_span, rule=_NAME, unsupported=())
    return Reading((revised,), (clause.span,))


def _licensed_past_form(clause, source: str) -> bool:
    """Independently match a positive, simple past source predicate."""
    if (clause.polarity != "+" or clause.modality != "assert" or clause.time != "past"
            or clause.conditions or clause.exceptions or clause.exception_of):
        return False
    span = clause.predicate_span
    if span.source != clause.span.source or span.start < clause.span.start or span.end > clause.span.end:
        return False
    if source[span.start:span.end] != span.text:
        return False
    ending = source[span.end:clause.span.end]
    if ending.endswith(_PUNCTUATION):
        ending = ending[:-1]
    lemma = clause.predicate
    surface = span.text
    if lemma.endswith("する"):
        return ((surface == lemma[:-2] and ending in ("した", "しました"))
                or (surface == lemma[:-2] + "し" and ending in ("た", "ました")))
    if lemma.endswith(("える", "いる")):
        return surface == lemma[:-1] and ending in ("た", "ました")
    if lemma.endswith(("う", "つ", "る")):
        return (surface == lemma[:-1] + "っ" and ending in ("た", "ました")) or (
            surface == lemma[:-1] and ending in ("た", "ました"))
    if lemma.endswith(("む", "ぶ", "ぬ")):
        return surface == lemma[:-1] + "ん" and ending in ("だ", "でした")
    if lemma.endswith("く"):
        surface_form = "行っ" if lemma == "行く" else lemma[:-1] + "い"
        return surface == surface_form and ending in ("た", "ました")
    if lemma.endswith("ぐ"):
        return surface == lemma[:-1] + "い" and ending in ("だ", "でした")
    if lemma.endswith("す"):
        return surface == lemma[:-1] + "し" and ending in ("た", "ました")
    return False


def _licensed_marker(role: Role, source: str) -> bool:
    if role.span.end > len(source):
        return False
    return any(source.startswith(marker, role.span.end)
               for marker in _ROLE_MARKERS.get(role.name, ()))


def _licensed_coordination(role: Role, source: str) -> bool:
    phrase = source[role.span.start:role.span.end]
    if not isinstance(role.term, str) or role.term != phrase:
        return False
    kind = role.rule.split(":", 1)[1] if ":" in role.rule else ""
    if kind not in ("parallel", "choice") or _coordination_kind(phrase) != kind:
        return False
    marker = _ROLE_MARKERS.get(role.name, ())
    return bool(marker) and any(source.startswith(value, role.span.end) for value in marker)


def _licensed_coverage(clause, source: str) -> bool:
    spans = [(role.span.start, role.span.end) for role in clause.roles]
    spans.append((clause.predicate_span.start, clause.predicate_span.end))
    spans.sort()
    cursor = clause.span.start
    for start, end in spans:
        if start < cursor or end < start or end > clause.span.end:
            return False
        if any(char not in _FILLER for char in source[cursor:start]):
            return False
        cursor = end
    return _licensed_past_form(clause, source) and cursor == clause.predicate_span.end


def licenses(clause, source: str) -> bool:
    """Check the coordination and entire simple clause without using the reader."""
    if (clause.rule != _NAME or clause.unsupported or len(source) > 1_000_000
            or clause.span.end - clause.span.start > 4096):
        return False
    if (not isinstance(clause.event, Variable) or clause.event.sort != "event"
            or clause.event.name != "event_" + clause.id):
        return False
    if (clause.span.start < 0 or clause.span.end > len(source)
            or clause.span.end <= clause.span.start
            or source[clause.span.start:clause.span.end] != clause.span.text):
        return False
    if clause.body_span is not None:
        body = clause.body_span
        if (body.source != clause.span.source or body.start < clause.span.start
                or body.end > clause.span.end or source[body.start:body.end] != body.text):
            return False
    if not clause.roles or not _licensed_past_form(clause, source):
        return False
    names = [role.name for role in clause.roles]
    if len(names) != len(set(names)) or "ambiguous" in names:
        return False
    changed = [role for role in clause.roles if role.rule.startswith(_NAME + ":")]
    if not changed or not any(role.rule in (_NAME + ":parallel", _NAME + ":choice") for role in changed):
        return False
    for role in clause.roles:
        if (role.span.source != clause.span.source or role.span.start < clause.span.start
                or role.span.end > clause.span.end or role.span.end <= role.span.start
                or source[role.span.start:role.span.end] != role.span.text
                or not isinstance(role.term, str) or role.term != role.span.text
                or not _licensed_marker(role, source)):
            return False
        if role.rule in (_NAME + ":parallel", _NAME + ":choice") and not _licensed_coordination(role, source):
            return False
        if role.rule == _NAME + ":role" and _coordination_kind(role.term):
            return False
    return _licensed_coverage(clause, source)


register(Construction(
    name=_NAME,
    priority=75,
    reads=reads,
    licenses=licenses,
    refines=("frame",),
))
