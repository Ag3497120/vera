"""Source-bounded readings for explicit Japanese causative-passive clauses."""
from __future__ import annotations

import hashlib
from dataclasses import replace

from ..semantic_ir import Clause, Role, Span
from . import Construction, ConstructionContext, Reading, TypedNote, register


NAME = "gold_caus_pass"
_A_ROW = {
    "う": "わ", "く": "か", "ぐ": "が", "す": "さ", "つ": "た",
    "ぬ": "な", "ぶ": "ば", "む": "ま", "る": "ら",
}
_I_E = frozenset("いきぎしじちぢにひびぴみりえけげせぜてでねへべぺめれ")
_MARKERS = frozenset(("は", "が", "を", "に", "へ", "で", "と", "から", "まで"))
_COMPOUNDS = ("によって", "により", "において", "における", "に対して", "について",
              "による", "として", "と共に", "ともに", "には", "では")
_PUNCT = frozenset(("、", "，", ",", "。", "！", "？", "!", "?", "；", ";"))
_SAFE_REASONS = frozenset((
    "multiple predicates need explicit clause scope", "ambiguous frame role",
    "unlocated patient", "unlocated agent", "unrepresented source content",
    "unlicensed role borrowing", "ambiguous case role: に", "ambiguous case role: で",
    "ambiguous case role: と", "ambiguous case role: から", "duplicate role in clause",
    "causative frame: causer/causee unresolved",     # named reason from the reader (W1-a); this rule re-assigns the roles
))
_PLACE_ENDINGS = ("脇", "前", "後ろ", "裏", "中", "近く", "そば", "隣", "横", "上", "下")
_PLACE_WORDS = frozenset(("学校", "駅", "公園", "玄関", "台所", "病院", "会社", "家", "庭"))
_TIME_WORDS = frozenset(("昨日", "今日", "明日", "今朝", "今晩", "今夜", "昨夜", "朝", "朝方",
                        "夕方", "夜", "先週", "今週", "来週", "先月", "今月", "来月", "去年",
                        "今年", "来年", "当日", "当時", "毎日", "毎朝", "毎晩", "週末"))
_UNSAFE_SCOPE = ("すべて", "全部", "それぞれ", "最後", "最初", "同時", "前後", "以前", "以後",
                 "最新", "以外", "除く", "のみ", "だけ", "必ず", "ただし", "場合", "なら", "たら", "れば")


def _verb_class(lemma: str) -> tuple[str, str] | None:
    if lemma.endswith("する") and len(lemma) > 2:
        return "suru", lemma[:-2]
    if lemma in ("来る", "くる"):
        return "kuru", "来" if lemma == "来る" else "こ"
    if len(lemma) > 1 and lemma.endswith("る") and lemma[-2] in _I_E:
        return "ichidan", lemma[:-1]
    row = _A_ROW.get(lemma[-1:] if lemma else "")
    return ("godan", lemma[:-1] + row) if row else None


def _reader_forms(lemma: str) -> tuple[tuple[str, bool], ...]:
    parsed = _verb_class(lemma)
    if parsed is None:
        return ()
    kind, stem = parsed
    if kind == "suru":
        root = stem + "させられ"
        forms = (root + "る", root + "た", root + "ている", root + "ていた", root + "ており",
                 root + "ます", root + "ました", root + "ています", root + "ていました")
    elif kind == "kuru":
        roots = (stem + "させられ", "こさせられ")
        forms = tuple(root + ending for root in roots for ending in (
            "る", "た", "ている", "ていた", "ており", "ます", "ました", "ています", "ていました"))
    elif kind == "ichidan":
        root = stem + "させられ"
        forms = tuple(root + ending for ending in (
            "る", "た", "ている", "ていた", "ており", "ます", "ました", "ています", "ていました"))
    else:
        a_stem = stem
        roots = (a_stem + "せられ", a_stem + "され")
        forms = tuple(root + ending for root in roots for ending in (
            "る", "た", "ている", "ていた", "ており", "ます", "ました", "ています", "ていました"))
    return tuple((form, form.endswith(("た", "ていた", "ました", "ていました")))
                 for form in sorted(set(forms), key=lambda value: (-len(value), value)))


def _reader_bases(causative: str) -> tuple[str, ...]:
    candidates = set()
    if causative.endswith("こさせる"):
        candidates.add("くる")
    elif causative.endswith("来させる"):
        candidates.add("来る")
    elif causative.endswith("させる") and len(causative) > 3:
        root = causative[:-3]
        candidates.add(root + ("る" if root and root[-1] in _I_E else "する"))
    elif causative.endswith("せる") and len(causative) > 2:
        a_stem = causative[:-2]
        reverse = {value: key for key, value in _A_ROW.items()}
        final = a_stem[-1:]
        if final in reverse:
            candidates.add(a_stem[:-1] + reverse[final])
    return tuple(sorted(base for base in candidates if _verb_class(base)))


def _reader_causative_forms(causative: str, fallback: str) -> tuple[tuple[str, bool], ...]:
    forms = [form for base in _reader_bases(causative) for form in _reader_forms(base)]
    forms.extend(_short_reader_forms(causative))
    if not forms:
        forms.extend(_reader_forms(fallback))
    return tuple(sorted(set(forms), key=lambda item: (-len(item[0]), item[0])))


def _reader_source_start(ctx: ConstructionContext, predicate_start: int, causative: str) -> int:
    if causative.endswith("させる") and len(causative) > 3:
        root = causative[:-3]
        before = ctx.sentence_text[:predicate_start]
        if root and before.endswith(root):
            return predicate_start - len(root)
    return predicate_start


def _short_reader_forms(causative: str) -> tuple[tuple[str, bool], ...]:
    if (not causative.endswith("す") or len(causative) < 2
            or causative[-2] not in frozenset(_A_ROW.values())):
        return ()
    root = causative[:-1] + "され"
    forms = tuple(root + ending for ending in (
        "る", "た", "ている", "ていた", "ており", "ます", "ました", "ています", "ていました"))
    return tuple((form, form.endswith(("た", "ていた", "ました", "ていました")))
                 for form in forms)


def _case_marks(ctx: ConstructionContext, predicate_start: int):
    text = ctx.sentence_text
    marks = []
    for index, item in enumerate(ctx.tokens):
        token = item.token
        if item.start >= predicate_start or token.surface not in _MARKERS:
            continue
        feature = token.feature
        if feature.pos1 != "助詞" or feature.pos2 not in ("格助詞", "係助詞", "副助詞"):
            continue
        if any(text.startswith(compound, item.start) for compound in _COMPOUNDS):
            continue
        marks.append((index, item.start, item.end, token.surface))
    return marks


def _segment_start(ctx: ConstructionContext, marks, at_index: int) -> int:
    start = 0
    for index, item in enumerate(ctx.tokens):
        if index >= at_index:
            break
        if item.token.surface in _PUNCT:
            start = max(start, item.end)
    for mark_index, _, end, _ in marks:
        if mark_index < at_index:
            start = max(start, end)
    return start


def _modifier_prefix(ctx: ConstructionContext, start: int, end: int) -> bool:
    """Allow only a closed, source-local modifier sequence before a noun head."""
    items = [item for item in ctx.tokens if start <= item.start and item.end <= end]
    if not items:
        return not ctx.sentence_text[start:end].strip()
    saw_verb = False
    for position, item in enumerate(items):
        feature = item.token.feature
        if feature.pos1 in ("形容詞", "形状詞", "連体詞", "接頭辞", "名詞"):
            continue
        if item.token.surface == "の" and feature.pos1 == "助詞":
            continue
        if feature.pos1 == "動詞":
            saw_verb = True
            continue
        if feature.pos1 == "助動詞":
            if "連体形" in str(feature.cForm):
                continue
            if (position > 0 and items[position - 1].token.feature.pos1 == "動詞"
                    and item.token.surface in ("た", "だ")):
                continue
        return False
    if saw_verb and not any("連体形" in str(item.token.feature.cForm) for item in items):
        return False
    return True


def _native_candidate(ctx: ConstructionContext, left: int, right: int):
    candidates = {}
    for clause in ctx.clauses:
        if clause.span.source != ctx.sentence_span.source:
            continue
        for role in clause.roles:
            span = role.span
            if (span.source == ctx.sentence_span.source and left <= span.start < span.end == right
                    and role.term == span.text):
                candidates[(span.start, span.end)] = role
    if len(candidates) == 1:
        return next(iter(candidates.values()))
    if len(candidates) > 1:
        return None
    return False


def _phrase(ctx: ConstructionContext, start: int, particle_start: int):
    base = ctx.sentence_span.start
    text = ctx.sentence_text
    left = start
    right = particle_start
    while left < right and (text[left].isspace() or text[left] in _PUNCT):
        left += 1
    while right > left and (text[right - 1].isspace() or text[right - 1] in _PUNCT):
        right -= 1
    if left >= right:
        return None
    old = _native_candidate(ctx, base + left, base + right)
    if old is None:
        return None
    if old is not False:
        role_span = old.span
        local_role_start = role_span.start - base
        if not _modifier_prefix(ctx, left, local_role_start):
            return None
        return Role("", role_span.text, role_span, NAME)
    items = [item for item in ctx.tokens if left <= item.start and item.end <= right]
    if (not items or items[-1].token.feature.pos1 not in ("名詞", "代名詞", "接尾辞")
            or not _modifier_prefix(ctx, left, right)):
        return None
    span = Span(ctx.sentence_span.source, base + left, base + right, text[left:right])
    return Role("", span.text, span, NAME)


def _strong_adjunct(role: Role, particle: str, prior_roles: tuple[Role, ...]) -> str | None:
    compact = role.term.replace(" ", "").replace("　", "")
    if particle == "に":
        if compact in _TIME_WORDS or any(char.isdigit() for char in compact) and any(
                unit in compact for unit in "年月日時分"):
            return "time"
        if compact.endswith(_PLACE_ENDINGS) or compact in _PLACE_WORDS:
            return "location"
        native = {old.name for clause in prior_roles for old in (clause,)}
        if "time" in native:
            return "time"
        if native.intersection(("location", "place")):
            return "location"
        return None
    return None


def _time_spans(ctx: ConstructionContext, before: int):
    text = ctx.sentence_text
    found = []
    for item in ctx.tokens:
        if item.end > before or item.token.surface not in _TIME_WORDS:
            continue
        following = next((part.token.surface for part in ctx.tokens if part.start == item.end), "")
        if following == "の":
            continue
        found.append((item.start, item.end))
    import re
    for match in re.finditer(r"(?<![0-9０-９])[0-9０-９]{1,4}(?:年|月|日|時|分)(?:[0-9０-９]{1,2}(?:月|日|時|分))?", text[:before]):
        found.append(match.span())
    return tuple(sorted(set(found)))


def _safe_time_only_clause(clause: Clause, ctx: ConstructionContext, before: int) -> bool:
    if "unsupported source quantifier/exception/time" not in clause.unsupported:
        return False
    source = ctx.sentence_text[:before]
    if not _time_spans(ctx, before):
        return False
    return not any(word in source for word in _UNSAFE_SCOPE)


def _unmarked_time_roles(ctx: ConstructionContext, before: int, roles: tuple[Role, ...]):
    known = [(role.span.start - ctx.sentence_span.start, role.span.end - ctx.sentence_span.start)
             for role in roles]
    spans = [span for span in _time_spans(ctx, before)
             if not any(left < span[1] and span[0] < right for left, right in known)]
    if len(spans) > 1 or (spans and any(role.name == "time" for role in roles)):
        return None
    out = list(roles)
    for left, right in spans:
        span = Span(ctx.sentence_span.source, ctx.sentence_span.start + left,
                    ctx.sentence_span.start + right, ctx.sentence_text[left:right])
        out.append(Role("time", span.text, span, NAME))
    if out and not any(role.name == "manner" for role in out):
        case_marks = _case_marks(ctx, before)
        tail_start = max((end for _, _, end, _ in case_marks), default=0)
        trailing = [item for item in ctx.tokens if tail_start <= item.start and item.end <= before
                    and item.token.surface not in _PUNCT
                    and not any(left <= item.start and item.end <= right for left, right in spans)]
        manner = []
        for item in trailing:
            feature = item.token.feature
            if (feature.pos1 == "副詞" or (feature.pos1 == "形容詞"
                    and "連用形" in str(feature.cForm))):
                manner.append(item)
            elif item.token.surface.isspace():
                continue
            else:
                manner = []
                break
        if manner:
            left, right = manner[0].start, manner[-1].end
            span = Span(ctx.sentence_span.source, ctx.sentence_span.start + left,
                        ctx.sentence_span.start + right, ctx.sentence_text[left:right])
            out.append(Role("manner", span.text, span, NAME))
    return tuple(sorted(out, key=lambda role: (role.span.start, role.name)))


def _read_roles(ctx: ConstructionContext, predicate_start: int):
    marks = _case_marks(ctx, predicate_start)
    if not marks:
        return None
    phrases = []
    for item_index, start, end, particle in marks:
        chunk_start = _segment_start(ctx, marks, item_index)
        phrase = _phrase(ctx, chunk_start, start)
        if phrase is None:
            return None
        phrases.append((item_index, start, end, particle, phrase))

    object_indexes = [index for index, item in enumerate(phrases) if item[3] == "を"]
    if len(object_indexes) > 1:
        return None
    ni_indexes = [index for index, item in enumerate(phrases) if item[3] == "に"]
    if not ni_indexes:
        return None
    object_index = object_indexes[0] if object_indexes else None
    earlier_ni = [index for index in ni_indexes if object_index is None or index < object_index]
    if not earlier_ni:
        return None
    agent_index = earlier_ni[-1]
    topics = [index for index, item in enumerate(phrases) if item[3] in ("は", "が")]
    if len(topics) > 1:
        return None

    roles = []
    for index, (_, _, particle_end, particle, phrase) in enumerate(phrases):
        if index == agent_index:
            if phrase.term in _TIME_WORDS or any(char.isdigit() for char in phrase.term):
                return None
            role_name = "agent"
        elif particle in ("は", "が"):
            role_name = "causee" if object_index is not None else "patient"
        elif particle == "を":
            role_name = "patient"
        elif particle == "に":
            old_roles = tuple(
                role for clause in ctx.clauses for role in clause.roles
                if role.span == phrase.span
            )
            role_name = _strong_adjunct(phrase, particle, old_roles)
            if role_name is None:
                return None
        else:
            old_roles = tuple(role for clause in ctx.clauses for role in clause.roles
                              if role.span == phrase.span)
            possible = {role.name for role in old_roles if role.name != "ambiguous"}
            expected = {"で": ("place", "means", "time", "location"),
                        "へ": ("direction",), "と": ("companion", "quotation"),
                        "から": ("source", "origin", "time"), "まで": ("limit",)}.get(particle, ())
            choices = possible.intersection(expected)
            if len(choices) != 1:
                return None
            role_name = next(iter(choices))
        if (role_name == "agent" or (role_name == "patient" and object_index is None
                                      and particle in ("は", "が"))):
            marker_span = Span(ctx.sentence_span.source, phrase.span.start,
                               ctx.sentence_span.start + particle_end,
                               phrase.span.text + particle)
            roles.append(Role(role_name, marker_span.text, marker_span, NAME))
        else:
            roles.append(replace(phrase, name=role_name))
    if "agent" not in {role.name for role in roles}:
        return None
    roles = _unmarked_time_roles(ctx, predicate_start, tuple(roles))
    if roles is None:
        return None
    if len({role.name for role in roles}) != len(roles):
        return None
    return tuple(sorted(roles, key=lambda role: (role.span.start, role.name)))


def reads(ctx: ConstructionContext) -> Reading | None:
    if (len(ctx.tokens) > ctx.budget.max_tokens or len(ctx.clauses) > ctx.budget.max_clauses
            or len(ctx.sentence_text) > 4096 or len(ctx.clauses) > ctx.budget.max_steps):
        return None
    sentence = ctx.sentence_span
    if (sentence.text != ctx.sentence_text or sentence.start < 0
            or sentence.end <= sentence.start):
        return None
    local = tuple(clause for clause in ctx.clauses
                  if clause.span.source == sentence.source and clause.span.start < sentence.end
                  and clause.span.end > sentence.start and clause.conditions == ()
                  and clause.exceptions == () and clause.polarity == "+"
                  and clause.modality in ("assert", "possible")
                  and all(reason in _SAFE_REASONS or reason == "unsupported source quantifier/exception/time"
                          and _safe_time_only_clause(clause, ctx, len(ctx.sentence_text))
                          for reason in clause.unsupported))
    notes = []
    for clause in local:
        p0 = clause.predicate_span.start - sentence.start
        if (p0 < 0 or clause.predicate_span.end > sentence.end
                or clause.predicate_span.text != ctx.sentence_text[p0:clause.predicate_span.end-sentence.start]):
            continue
        token = next((item for item in ctx.tokens if item.start == p0), None)
        if token is None or token.token.feature.pos1 != "動詞":
            continue
        lemma = token.token.feature.lemma or token.token.surface
        available_forms = _reader_causative_forms(clause.predicate, lemma)
        source_start = _reader_source_start(ctx, p0, clause.predicate)
        matches = [(form, past) for form, past in available_forms
                   if ctx.sentence_text.startswith(form, source_start)]
        if len(matches) != 1:
            continue
        form, past = matches[0]
        end = source_start + len(form)
        remainder = ctx.sentence_text[end:]
        if any(char not in "。．.!！？?、，,)]}）』」 \t\n" for char in remainder):
            continue
        roles = _read_roles(ctx, source_start)
        if roles is None:
            notes.append(TypedNote("ambiguous frame role", clause.predicate_span,
                                   "the causative-passive source frame has an untyped or competing case phrase"))
            continue
        predicate_span = Span(sentence.source, sentence.start + source_start, sentence.start + end, form)
        new_predicate = clause.predicate
        digest = hashlib.sha256((sentence.source + ":" + str(sentence.start) + ":" +
                                 str(predicate_span.start) + ":" + new_predicate + ":" +
                                 ",".join(role.name + "=" + role.span.text for role in roles)).encode("utf-8")).hexdigest()[:24]
        built = replace(clause, id=digest,
                        event=replace(clause.event, name="event_" + digest, sort="event"),
                        predicate=new_predicate, predicate_span=predicate_span, roles=roles,
                        span=sentence, body_span=sentence, polarity="+", modality="assert",
                        time="past" if past else "nonpast", conditions=(), condition_spans=(),
                        exceptions=(), exception_spans=(), exception_of="", rule=NAME,
                        unsupported=())
        return Reading((built,), (sentence,), tuple(notes))
    return Reading((), (), tuple(notes)) if notes else None


def _license_class(lemma: str) -> tuple[str, str] | None:
    if lemma[-2:] == "する" and len(lemma) > 2:
        return "suru", lemma[:-2]
    if lemma in ("来る", "くる"):
        return "kuru", "来" if lemma == "来る" else "こ"
    if len(lemma) > 1 and lemma[-1] == "る" and lemma[-2] in _I_E:
        return "ichidan", lemma[:-1]
    final = lemma[-1:] if lemma else ""
    if final in _A_ROW:
        return "godan", lemma[:-1] + _A_ROW[final]
    return None


def _licensed_surfaces(lemma: str) -> tuple[tuple[str, str], ...]:
    parsed = _license_class(lemma)
    if parsed is None:
        return ()
    kind, stem = parsed
    if kind == "suru":
        roots = (stem + "させられ",)
    elif kind == "kuru":
        roots = (stem + "させられ", "こさせられ")
    elif kind == "ichidan":
        roots = (stem + "させられ",)
    else:
        roots = (stem + "せられ", stem + "され")
    endings = ("る", "た", "ている", "ていた", "ており", "ます", "ました", "ています", "ていました")
    result = []
    for root in roots:
        for ending in endings:
            form = root + ending
            tense = "past" if ending in ("た", "ていた", "ました", "ていました") else "nonpast"
            result.append((form, tense))
    return tuple(sorted(set(result), key=lambda item: (-len(item[0]), item[0], item[1])))


def _licensed_short_surfaces(causative: str) -> tuple[tuple[str, str], ...]:
    if (not causative.endswith("す") or len(causative) < 2
            or causative[-2] not in frozenset(_A_ROW.values())):
        return ()
    root = causative[:-1] + "され"
    endings = ("る", "た", "ている", "ていた", "ており", "ます", "ました", "ています", "ていました")
    return tuple((root + ending, "past" if ending in ("た", "ていた", "ました", "ていました") else "nonpast")
                 for ending in endings)


def _licensed_bases(causative: str) -> tuple[str, ...]:
    candidates = set()
    if causative.endswith("こさせる"):
        candidates.add("くる")
    elif causative.endswith("来させる"):
        candidates.add("来る")
    elif causative.endswith("させる") and len(causative) > 3:
        stem = causative[:-3]
        if stem and stem[-1] in _I_E:
            candidates.add(stem + "る")
        else:
            candidates.add(stem + "する")
    elif causative.endswith("せる") and len(causative) > 2:
        a_stem = causative[:-2]
        reverse = {value: key for key, value in _A_ROW.items()}
        final = a_stem[-1:]
        if final in reverse:
            candidates.add(a_stem[:-1] + reverse[final])
    return tuple(sorted(candidate for candidate in candidates if _license_class(candidate)))


def _license_marker(source: str, span: Span) -> str:
    if span.text and span.text[-1] in "にはがをでとへ":
        suffix = span.text[-1]
        if source[span.end-1:span.end] == suffix:
            return suffix
    for marker in ("によって", "により", "において", "における", "について", "に対して",
                   "による", "として", "と共に", "ともに", "では", "には", "から", "まで",
                   "が", "は", "を", "に", "へ", "で", "と"):
        if source.startswith(marker, span.end):
            return marker
    return ""


def _license_strong_location(value: str) -> bool:
    compact = value.replace(" ", "").replace("　", "")
    return compact in _PLACE_WORDS or compact.endswith(_PLACE_ENDINGS)


def _license_time_value(value: str) -> bool:
    import re
    compact = value.replace(" ", "").replace("　", "")
    return compact in _TIME_WORDS or bool(re.fullmatch(
        r"[0-9０-９]{1,4}(?:年|月|日|時|分)(?:[0-9０-９]{1,2}(?:月|日|時|分))?", compact))


def _license_manner(value: str) -> bool:
    from ..typed_edges import _tagger
    words = list(_tagger()(value))
    return bool(words) and all(
        word.feature.pos1 == "副詞" or (word.feature.pos1 == "形容詞"
                                          and "連用形" in str(word.feature.cForm))
        for word in words)


def _license_chunk_roles(clause: Clause, source: str) -> bool:
    names = [role.name for role in clause.roles]
    if len(names) != len(set(names)):
        return False
    roles = sorted(clause.roles, key=lambda role: role.span.start)
    agent = next((role for role in roles if role.name == "agent"), None)
    if agent is None or _license_marker(source, agent.span) != "に":
        return False
    patient_objects = [role for role in roles if role.name == "patient"
                       and _license_marker(source, role.span) == "を"]
    causees = [role for role in roles if role.name == "causee"]
    topic_patients = [role for role in roles if role.name == "patient"
                      and _license_marker(source, role.span) in ("は", "が")]
    if len(patient_objects) > 1 or len(causees) > 1 or len(topic_patients) > 1:
        return False
    ni_roles = [role for role in roles if _license_marker(source, role.span) == "に"]
    if agent not in ni_roles:
        return False
    if patient_objects:
        patient = patient_objects[0]
        previous_candidates = [role for role in ni_roles if role.span.end < patient.span.start]
        if not previous_candidates or previous_candidates[-1] != agent:
            return False
        if causees and _license_marker(source, causees[0].span) not in ("は", "が"):
            return False
        if topic_patients:
            return False
    else:
        previous_candidates = ni_roles
        if not previous_candidates or previous_candidates[-1] != agent:
            return False
        if causees:
            return False
        if topic_patients and _license_marker(source, topic_patients[0].span) not in ("は", "が"):
            return False
    for role in roles:
        marker = _license_marker(source, role.span)
        if role.span.text != source[role.span.start:role.span.end] or role.term != role.span.text:
            return False
        if role.name in ("agent", "causee"):
            if (role.name == "agent" and marker != "に") or (role.name == "causee" and marker not in ("は", "が")):
                return False
        elif role.name == "patient":
            if marker not in ("を", "は", "が"):
                return False
        elif role.name == "location":
            if marker != "に" or not _license_strong_location(role.term):
                return False
        elif role.name == "time":
            if marker not in ("", "に", "は") or not _license_time_value(role.term):
                return False
        elif role.name == "manner":
            if marker or not _license_manner(role.term):
                return False
        elif role.name == "place" and marker != "で":
            return False
        elif role.name == "means" and marker != "で":
            return False
        elif role.name == "direction" and marker != "へ":
            return False
        elif role.name == "companion" and marker != "と":
            return False
        elif role.name == "quotation" and marker != "と":
            return False
        elif role.name in ("source", "origin") and marker != "から":
            return False
        elif role.name == "limit" and marker != "まで":
            return False
        elif role.name not in ("agent", "causee", "patient", "location", "time", "place",
                                "means", "direction", "companion", "quotation", "source", "origin", "limit"):
            return False
    return True


def licenses(clause: Clause, source: str) -> bool:
    """Recheck the raw finite morphology and particle frame without using reads()."""
    if (clause.rule != NAME or not isinstance(source, str) or clause.unsupported
            or clause.polarity != "+" or clause.modality != "assert" or clause.conditions
            or clause.condition_spans or clause.exceptions or clause.exception_spans
            or clause.exception_of or clause.body_span != clause.span or clause.time not in ("past", "nonpast")):
        return False
    whole, body, pred = clause.span, clause.body_span, clause.predicate_span
    if (whole.source != body.source or whole.source != pred.source or whole.start < 0
            or whole.start >= whole.end or whole.end > len(source)
            or source[whole.start:whole.end] != whole.text or body != whole
            or pred.start < whole.start or pred.end > whole.end or pred.start >= pred.end
            or source[pred.start:pred.end] != pred.text):
        return False
    core = source[whole.start:whole.end]
    local_start = pred.start - whole.start
    if core[:local_start].strip(" \t\n、，,") == "":
        return False
    endings = [form for base in _licensed_bases(clause.predicate)
               for form in _licensed_surfaces(base) if form[0] == pred.text]
    endings.extend(form for form in _licensed_short_surfaces(clause.predicate)
                   if form[0] == pred.text)
    if len(endings) != 1 or endings[0][1] != clause.time:
        return False
    if core[local_start:local_start + len(pred.text)] != pred.text:
        return False
    tail = core[local_start + len(pred.text):]
    if any(char not in "。．.!！？?、，,)]}）』」 \t\n" for char in tail):
        return False
    if not _license_chunk_roles(clause, source):
        return False
    for role in clause.roles:
        span = role.span
        if (span.source != whole.source or span.start < whole.start or span.end > pred.start
                or span.start >= span.end or source[span.start:span.end] != span.text
                or not isinstance(role.term, str) or role.term != span.text):
            return False

    # Every case phrase before the predicate must be typed; only punctuation,
    # whitespace, and a closed adnominal prefix can remain between its head and marker.
    from ..typed_edges import _tagger
    words = list(_tagger()(core[:local_start]))
    positions = []
    cursor = 0
    for word in words:
        at = core.find(word.surface, cursor, local_start)
        if at < 0:
            return False
        positions.append(at)
        cursor = at + len(word.surface)
    coverage = [False] * local_start
    role_by_end = {role.span.end - whole.start: role for role in clause.roles}
    marker_spans = []
    case_tokens = []
    for role in clause.roles:
        lo, hi = role.span.start - whole.start, role.span.end - whole.start
        for index in range(lo, hi):
            coverage[index] = True
        marker = _license_marker(source, role.span)
        marker_start = hi
        marker_end = marker_start + len(marker)
        if marker and not source.startswith(marker, role.span.end) and role.span.text.endswith(marker):
            marker_start = hi - len(marker)
            marker_end = hi
        if marker:
            marker_spans.append((marker_start, marker_end))
    for left, right in marker_spans:
        for index in range(left, right):
            if index >= local_start:
                return False
            coverage[index] = True
    for word, at in zip(words, positions):
        end = at + len(word.surface)
        if (word.feature.pos1 == "助詞" and word.surface == "の"
                and not any(a <= at and end <= b for a, b in marker_spans)):
            # Genitive particles belong to the immediately following nominal span.
            following = next((role for role in clause.roles if role.span.start - whole.start > end), None)
            if following is not None and following.span.start - whole.start - end <= 2:
                for index in range(at, end):
                    coverage[index] = True
    for index, char in enumerate(core[:local_start]):
        if coverage[index] or char.isspace() or char in _PUNCT:
            continue
        if any(role.span.start - whole.start > index for role in clause.roles):
            role = min((r for r in clause.roles if r.span.start - whole.start > index),
                       key=lambda r: r.span.start)
            if _license_adnominal_prefix(words, positions, index, role.span.start - whole.start):
                continue
        return False
    return True


def _license_adnominal_prefix(words, positions, start: int, end: int) -> bool:
    picked = [(word, at) for word, at in zip(words, positions) if start <= at and at + len(word.surface) <= end]
    if not picked:
        return False
    saw_verb = False
    for index, (word, _) in enumerate(picked):
        pos = word.feature.pos1
        if pos in ("形容詞", "形状詞", "連体詞", "接頭辞", "名詞"):
            continue
        if pos == "動詞":
            saw_verb = True
            continue
        if pos == "助詞" and word.surface == "の":
            continue
        if pos == "助動詞" and ("連体形" in str(word.feature.cForm)
                                 or (index > 0 and picked[index - 1][0].feature.pos1 == "動詞"
                                     and word.surface in ("た", "だ"))):
            continue
        return False
    return not saw_verb or any("連体形" in str(word.feature.cForm) for word, _ in picked)


register(Construction(name=NAME, priority=50, reads=reads, licenses=licenses,
                      refines=("diathesis",)))


__all__ = ("licenses", "reads")
