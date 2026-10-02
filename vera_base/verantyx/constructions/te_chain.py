"""Explicit scope for coordinated predicate chains.

The native frame reader supplies predicate and argument proposals.  This rule
accepts only adjacent verbal predicates joined by a て-form, 連用中止, or
ながら, and checks the source morphology and case particles again in its
independent licensor.
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import re

from fugashi import Tagger
from ..semantic_ir import Clause, Role, Span, Variable
from .. import semantic_coord
from . import Construction, ConstructionContext, Reading, TypedNote, register


_RULE = "te_chain"
_CLEARABLE = frozenset((
    "multiple predicates need explicit clause scope",
    "unrepresented source content",
    "ambiguous frame role",
))
_SUBJECT_MARKS = {"agent": ("は", "が", "も"), "topic": ("は", "では")}
_ROLE_MARKS = {
    "agent": ("が", "は", "も"), "patient": ("を",),
    "recipient": ("に", "へ"), "source": ("から", "より"),
    "place": ("で", "に"), "setting": ("において", "における", "では", "で", "に"),
    "time": ("に", "で", "は"), "by": ("によって", "により", "による", "で"),
    "topic": ("においては", "では", "は"), "subject": ("が", "は"),
    "capacity": ("として",),
    "direction": ("へ", "に"), "manner": ("によって", "で"),
    "name": ("と",),
}
_CASE_PARTICLES = frozenset(mark for marks in _ROLE_MARKS.values() for mark in marks)
_CONNECTIVE_PARTICLES = frozenset(("て", "で", "ながら"))
_ADDITIVE_MARKERS = frozenset(("また",))
_PUNCT = frozenset("、。，．・「」『』（）()［］[]【】〈〉《》“”\"'「」")
_BAD_TE_FOLLOWERS = ("ても", "ては", "てから", "てい", "ており", "ておら", "てしま", "てみ")
_BAD_DE_FOLLOWERS = ("でも", "である", "でした", "でし")
_VERB_END = re.compile(r"[一-龯々〆ヵヶぁ-んァ-ヶーA-Za-z0-9]+(?:する|した|して|される|された|ある|ない|る|た|だ|ます|ました|れる|られる|できる|できた|いる)")


def _feature(token):
    return getattr(token, "feature", None)


def _surface(token_span) -> str:
    token = token_span.token
    value = getattr(token, "surface", None)
    if isinstance(value, str):
        return value
    feature = _feature(token)
    value = getattr(feature, "orth", None)
    return value if isinstance(value, str) else str(token)


def _local(span: Span, sentence: Span) -> tuple[int, int] | None:
    if (span.source != sentence.source or type(span.start) is not int or type(span.end) is not int
            or not sentence.start <= span.start < span.end <= sentence.end):
        return None
    return span.start - sentence.start, span.end - sentence.start


def _token_for(ctx: ConstructionContext, clause: Clause):
    for token in ctx.tokens:
        if (token.start + ctx.sentence_span.start == clause.predicate_span.start
                and token.end + ctx.sentence_span.start == clause.predicate_span.end):
            return token
    return None


def _lemma_matches(clause: Clause, token, text: str, local_start: int) -> bool:
    feature = _feature(token.token)
    if feature is None or getattr(feature, "pos1", "") != "動詞":
        return False
    lemma = getattr(feature, "lemma", "")
    if lemma == clause.predicate:
        return True
    if (clause.predicate, lemma) in (("ある", "有る"), ("いる", "居る")):
        return True
    if clause.predicate.endswith("する") and lemma in ("する", "為る"):
        prefix = clause.predicate[:-2]
        return not prefix or text[max(0, local_start - len(prefix)):local_start] == prefix
    if clause.predicate.endswith("ずる") and _surface(token) in (clause.predicate[:-2] + "じ",
                                                                       clause.predicate[:-2] + "ず"):
        return True
    if clause.predicate:
        last = clause.predicate[-1]
        endings = {
            "る": ("り", "っ", ""), "う": ("い", "っ"), "く": ("き", "い"),
            "ぐ": ("ぎ", "い"), "す": ("し",), "つ": ("ち", "っ"),
            "ぬ": ("に", "ん"), "ぶ": ("び", "ん"), "む": ("み",),
        }
        stem = clause.predicate[:-1] if last in endings else clause.predicate
        if _surface(token) in {stem + suffix for suffix in endings.get(last, ("",))}:
            return True
    return False


def _connection(text: str, left: Clause, right: Clause, base: Span,
                ctx: ConstructionContext | None = None) -> tuple[int, int] | None:
    gap_start = left.predicate_span.end - base.start
    gap_end = right.predicate_span.start - base.start
    if not 0 <= gap_start < gap_end <= len(text):
        return None
    gap = text[gap_start:gap_end]
    if gap.startswith("ながら"):
        return gap_start, gap_start + 3
    if gap.startswith("て") and not gap.startswith(_BAD_TE_FOLLOWERS):
        return gap_start, gap_start + 1
    if gap.startswith("で") and not gap.startswith(_BAD_DE_FOLLOWERS):
        return gap_start, gap_start + 1
    if gap.startswith("、"):
        return gap_start, gap_start + 1
    # 連用中止 does not require a comma.  In this case the bounded token
    # stream must show an actual continuative verb, and the character coverage
    # check below accounts for every intervening argument and particle.
    if ctx is not None and gap and not gap.startswith(("た", "だ", "が", "けれど", "けど", "から", "ので", "ため", "のに", "つつ")):
        token = _token_for(ctx, left)
        form = str(getattr(_feature(token.token), "cForm", "")) if token is not None else ""
        if form.startswith("連用形"):
            return gap_start, gap_start
    return None


def _semantic_coord_ok(ctx: ConstructionContext, clauses: list[Clause], markers: list[str]) -> bool:
    if "ながら" in markers:
        return True
    if _explicit_additive_scope(ctx, clauses):
        return True
    tagged = semantic_coord.tag([token.token for token in ctx.tokens],
                                [token.start for token in ctx.tokens])
    verb_indices = [i for i, row in enumerate(tagged) if len(row) > 3 and row[1] == "動詞"]
    own_indices = []
    for clause in clauses:
        local = clause.predicate_span.start - ctx.sentence_span.start
        own = next((i for i, row in enumerate(tagged)
                    if len(row) >= 6 and row[4] == local
                    and row[5] == clause.predicate_span.end - ctx.sentence_span.start), None)
        if own is None:
            return True
        own_indices.append(own)
    if len(verb_indices) == len(own_indices) and set(verb_indices) == set(own_indices):
        return semantic_coord.coordination_ok(tagged, verb_indices)
    return True


def _explicit_additive_scope(ctx: ConstructionContext, clauses: list[Clause]) -> bool:
    if len(clauses) < 2:
        return False
    inferred_topics = _subject_roles(ctx, tuple(replace(clause, roles=()) for clause in clauses))
    shared = None
    for index, clause in enumerate(clauses):
        explicit = {str(role.term) for role in inferred_topics[index]
                    if role.name in ("topic", "subject")}
        explicit.update(str(role.term) for role in clause.roles if role.name in ("topic", "subject"))
        for role in clause.roles:
            if role.name in ("agent", "subject") and ctx.sentence_text.startswith("は", role.span.end - ctx.sentence_span.start):
                explicit.add(str(role.term))
        shared = explicit if shared is None else shared & explicit
        if not shared:
            return False
    for left, right in zip(clauses, clauses[1:]):
        lo = left.predicate_span.end - ctx.sentence_span.start
        hi = right.predicate_span.start - ctx.sentence_span.start
        if not any(lo <= token.start < token.end <= hi
                   and _surface(token) in _ADDITIVE_MARKERS
                   and getattr(_feature(token.token), "pos1", "") in ("副詞", "接続詞")
                   for token in ctx.tokens):
            return False
    return True


def _new_subject_scope_ok(ctx: ConstructionContext, clauses: list[Clause]) -> bool:
    if len(clauses) < 2:
        return True
    inferred = _subject_roles(ctx, tuple(replace(clause, roles=()) for clause in clauses))
    shared_topics = None
    for index, clause in enumerate(clauses):
        terms = {str(role.term) for role in inferred[index]
                 if role.name in ("topic", "subject")}
        for role in clause.roles:
            pos = _local(role.span, ctx.sentence_span)
            if role.name in ("topic", "subject") and pos is not None:
                if not (role.name == "topic" and ctx.sentence_text.startswith("では", pos[1])):
                    terms.add(str(role.term))
            if (role.name in ("agent", "subject") and pos is not None
                    and ctx.sentence_text.startswith("は", pos[1])):
                terms.add(str(role.term))
        shared_topics = terms if shared_topics is None else shared_topics & terms
    shared_topics = shared_topics or set()
    prior_subjects = set()
    for left, right in zip(clauses, clauses[1:]):
        prior_subjects.update(str(role.term) for role in left.roles
                              if role.name in ("agent", "subject", "topic"))
        low = left.predicate_span.end - ctx.sentence_span.start
        high = right.predicate_span.start - ctx.sentence_span.start
        for index, token in enumerate(ctx.tokens):
            surface = _surface(token)
            if (not low <= token.start < token.end <= high or surface not in ("は", "が")
                    or getattr(_feature(token.token), "pos1", "") != "助詞"):
                continue
            previous = _surface(ctx.tokens[index - 1]) if index else ""
            if previous in ("で", "に", "と", "も"):
                continue
            phrase = _phrase_before_particle(ctx, index)
            if phrase is not None and phrase[0] not in shared_topics | prior_subjects and not shared_topics:
                left_core = any(role.name in ("agent", "subject", "topic") for role in left.roles)
                right_core = any(role.name in ("agent", "subject", "topic") for role in right.roles)
                if not left_core or not right_core:
                    return False
    return True


def _role_mark(role, text: str, sentence: Span) -> tuple[int, int] | None:
    pos = _local(role.span, sentence)
    if pos is None or not isinstance(role.term, str) or role.term != role.span.text:
        return None
    if role.rule not in ("frame", "case", "literal"):
        return None
    if role.name == "nominal_head":
        end = pos[1]
        for marker in ("であった", "である", "だった", "だ"):
            if text.startswith(marker, end):
                return end, end + len(marker)
        if all(ch in _PUNCT or ch.isspace() for ch in text[end:]):
            return end, len(text)
        return None
    if role.name == "attribute" and role.rule == "literal" and text.startswith("の", pos[1]):
        return pos[1], pos[1] + 1
    if role.name == "recipient" and role.rule == "literal" and text.startswith("まで", pos[1]):
        return pos[1], pos[1] + 2
    if role.name == "manner" and role.rule == "literal" and role.span.text.endswith(("く", "に")):
        return pos[1], pos[1]
    if role.name == "source" and role.rule == "literal" and text.startswith("に", pos[1]):
        return pos[1], pos[1] + 1
    if role.name == "topic" and text.startswith("とは", pos[1]):
        return pos[1], pos[1] + 2
    allowed = _ROLE_MARKS.get(role.name)
    if not allowed:
        return None
    end = pos[1]
    for mark in sorted(allowed, key=len, reverse=True):
        if text.startswith(mark, end):
            return end, end + len(mark)
    return None


def _phrase_before_particle(ctx: ConstructionContext, index: int):
    marker = ctx.tokens[index]
    start = marker.start
    depth = 0
    opens = frozenset("（([［【「『〈《“\"")
    closes = frozenset("）)]］】」』〉》”\"")
    for prior in reversed(ctx.tokens[:index]):
        feature = _feature(prior.token)
        surface = _surface(prior)
        pos1 = getattr(feature, "pos1", "")
        if not depth and surface in ("、", "。", ",", ";"):
            break
        if any(ch in closes for ch in surface):
            depth += 1
            start = prior.start
            continue
        if any(ch in opens for ch in surface) and depth:
            depth -= 1
            start = prior.start
            continue
        if (depth or pos1 in ("名詞", "接尾辞", "形状詞", "代名詞", "補助記号")
                or pos1 == "接続詞"
                or (pos1 == "助詞" and surface in ("の", "など", "や", "または", "もしくは", "あるいは", "および"))
                or surface.isspace()):
            start = prior.start
            continue
        break
    phrase = ctx.sentence_text[start:marker.start]
    if not phrase.strip():
        return None
    source_span = Span(ctx.sentence_span.source, ctx.sentence_span.start + start,
                       ctx.sentence_span.start + marker.start, phrase)
    return phrase, source_span


def _subject_roles(ctx: ConstructionContext, clauses: tuple[Clause, ...]) -> tuple[tuple[Role, ...], ...]:
    markers = []
    depth = 0
    opens = frozenset("（([［【「『〈《“\"")
    closes = frozenset("）)]］】」』〉》”\"")
    for index, token in enumerate(ctx.tokens):
        surface = _surface(token)
        feature = _feature(token.token)
        exact_surface = ctx.sentence_text[token.start:token.end] == surface
        if (depth == 0 and surface == "は" and index > 0
                and _surface(ctx.tokens[index - 1]) == "と"):
            phrase = _phrase_before_particle(ctx, index - 1)
            if phrase is not None:
                markers.append((token.end, "とは", Role("topic", phrase[0], phrase[1], "literal")))
        if (depth == 0 and exact_surface and getattr(feature, "pos1", "") == "助詞"
                and surface in ("は", "が")):
            prior_surface = _surface(ctx.tokens[index - 1]) if index else ""
            if prior_surface not in ("で", "に", "と", "また"):
                phrase = _phrase_before_particle(ctx, index)
                if phrase is not None:
                    markers.append((token.end, surface, Role("topic" if surface == "は" else "subject",
                                                               phrase[0], phrase[1], "literal")))
        for char in surface:
            if char in opens:
                depth += 1
            elif char in closes and depth:
                depth -= 1

    roles: list[list[Role]] = [[] for _ in clauses]
    if not clauses:
        return tuple(tuple(row) for row in roles)
    active_topic = None
    active_subject = None
    marker_index = 0
    for i, clause in enumerate(clauses):
        pred = clause.predicate_span.start - ctx.sentence_span.start
        while marker_index < len(markers) and markers[marker_index][0] <= pred:
            _, particle, role = markers[marker_index]
            if particle == "は":
                active_topic = role
            else:
                active_subject = role
            marker_index += 1
        for role in (active_topic, active_subject):
            if role is None:
                continue
            if any(existing.span == role.span for existing in clause.roles + tuple(roles[i])):
                continue
            if (clause.predicate == "呼ぶ"
                    and any(str(existing.term) == str(role.term)
                            and ctx.sentence_text.startswith("と", existing.span.end - ctx.sentence_span.start)
                            for existing in clause.roles)):
                continue
            if any(existing.name == role.name for existing in clause.roles + tuple(roles[i])):
                if role.name != "topic" or any(existing.name == "subject"
                                                for existing in clause.roles + tuple(roles[i])):
                    continue
                role = replace(role, name="subject")
            roles[i].append(role)
    return tuple(tuple(row) for row in roles)


def _expand_coord_role(ctx: ConstructionContext, role):
    pos = _local(role.span, ctx.sentence_span)
    if pos is None:
        return role
    previous = [t for t in ctx.tokens if t.end <= pos[0]]
    if not previous:
        return role
    include_separator = False
    start = pos[0]
    j = len(previous) - 1
    while j >= 0:
        token = previous[j]
        feature = _feature(token.token)
        surface = _surface(token)
        pos1 = getattr(feature, "pos1", "")
        if surface == "は" and j > 0 and _surface(previous[j - 1]) == "また":
            include_separator = True
            start = previous[j - 1].start
            j -= 2
            continue
        if surface in ("や", "または", "もしくは", "あるいは", "および"):
            include_separator = True
            start = token.start
            j -= 1
            continue
        if surface == "、" and j > 0:
            before = previous[j - 1]
            before_feature = _feature(before.token)
            if (getattr(before_feature, "pos1", "") in ("名詞", "接尾辞", "形状詞", "代名詞")
                    and _surface(before) not in ("は", "が")):
                include_separator = True
                start = token.start
                j -= 1
                continue
        if (pos1 in ("名詞", "接尾辞", "形状詞", "代名詞")
                or (pos1 == "助詞" and surface in ("の", "など"))):
            start = token.start
            j -= 1
            continue
        break
    if not include_separator or start == pos[0]:
        return role
    phrase = ctx.sentence_text[start:pos[1]]
    span = Span(ctx.sentence_span.source, ctx.sentence_span.start + start,
                ctx.sentence_span.start + pos[1], phrase)
    return replace(role, term=phrase, span=span)


def _expand_modifier_role(ctx: ConstructionContext, role, other_roles):
    pos = _local(role.span, ctx.sentence_span)
    if pos is None:
        return role
    roles_before = [r.span.end - ctx.sentence_span.start for r in other_roles
                    if r.span != role.span and r.span.end <= role.span.start]
    boundary = max(roles_before, default=0)
    tokens = [t for t in ctx.tokens if boundary <= t.end <= pos[0]]
    if not tokens:
        return role
    start = pos[0]
    j = len(tokens) - 1
    while j >= 0 and tokens[j].end == start:
        token = tokens[j]
        surface = _surface(token)
        feature = _feature(token.token)
        pos1 = getattr(feature, "pos1", "")
        if (pos1 in ("形容詞", "形状詞", "連体詞")
                or (pos1 == "助詞" and surface == "の")
                or surface == "な" and pos1 in ("助詞", "助動詞")):
            start = token.start
            j -= 1
            continue
        break
    if start == pos[0]:
        return role
    phrase = ctx.sentence_text[start:pos[1]]
    span = Span(ctx.sentence_span.source, ctx.sentence_span.start + start,
                ctx.sentence_span.start + pos[1], phrase)
    return replace(role, term=phrase, span=span)


def _modifier_attributes(ctx: ConstructionContext, role, expanded) -> tuple[Role, ...]:
    if role.name != "patient" or expanded.span == role.span:
        return ()
    start = expanded.span.start - ctx.sentence_span.start
    end = role.span.start - ctx.sentence_span.start
    prefix = [token for token in ctx.tokens if start <= token.start and token.end <= end]
    result = []
    for index, token in enumerate(prefix):
        feature = _feature(token.token)
        if getattr(feature, "pos1", "") not in ("形容詞", "形状詞", "連体詞"):
            continue
        following = next((other for other in prefix if other.start == token.end), None)
        if following is None:
            following = next((other for other in ctx.tokens if other.start == token.end), None)
        if following is None or _surface(following) != "の":
            continue
        span = Span(ctx.sentence_span.source, ctx.sentence_span.start + token.start,
                    ctx.sentence_span.start + token.end, _surface(token))
        result.append(Role("attribute", span.text, span, "literal"))
    return tuple(result)


def _manner_role(ctx: ConstructionContext, clause: Clause):
    pred = _pred_range(ctx.sentence_text, clause, ctx.sentence_span)
    if pred is None:
        return None
    prior = next((t for t in reversed(ctx.tokens) if t.end <= pred[0]), None)
    if prior is None or prior.end != pred[0]:
        return None
    feature = _feature(prior.token)
    surface = _surface(prior)
    if not surface.endswith(("く", "に")) or not str(getattr(feature, "cForm", "")).startswith("連用形"):
        return None
    span = Span(ctx.sentence_span.source, ctx.sentence_span.start + prior.start,
                ctx.sentence_span.start + prior.end, surface)
    return Role("manner", surface, span, "literal")


def _learning_source(ctx: ConstructionContext, clause: Clause):
    if clause.predicate not in ("学ぶ", "習う"):
        return None
    patient = next((r for r in clause.roles if r.name == "patient"), None)
    if patient is None:
        return None
    pred_start = clause.predicate_span.start - ctx.sentence_span.start
    for index, token in enumerate(ctx.tokens):
        if token.end > pred_start:
            break
        if _surface(token) != "に" or getattr(_feature(token.token), "pos1", "") != "助詞":
            continue
        phrase = _phrase_before_particle(ctx, index)
        if phrase is None or phrase[1].end > patient.span.start:
            continue
        source_start, source_end = phrase[1].start - ctx.sentence_span.start, phrase[1].end - ctx.sentence_span.start
        proper = any(t.start < source_end and source_start < t.end
                     and getattr(_feature(t.token), "pos2", "") == "固有名詞"
                     for t in ctx.tokens)
        if proper:
            return Role("source", phrase[0], phrase[1], "literal")
    return None


def _canonical_role(ctx: ConstructionContext, role, predicate: str = ""):
    pos = _local(role.span, ctx.sentence_span)
    if pos is None:
        return role
    if role.name == "patient" and ctx.sentence_text.startswith("は", pos[1]):
        return replace(role, name="topic", rule="literal")
    if (role.name == "agent" and predicate == "呼ぶ"
            and ctx.sentence_text.startswith("と", pos[1])):
        return replace(role, name="name", rule="literal")
    return role


def _predicate_frame_roles(ctx: ConstructionContext, clause: Clause) -> tuple[Role, ...]:
    pred = _pred_range(ctx.sentence_text, clause, ctx.sentence_span)
    if pred is None:
        return ()
    roles = []
    if not any(role.name == "patient" for role in clause.roles):
        for index, token in enumerate(ctx.tokens):
            if (_surface(token) == "を" and token.end == pred[0]
                    and getattr(_feature(token.token), "pos1", "") == "助詞"):
                phrase = _phrase_before_particle(ctx, index)
                if phrase is not None:
                    patient = Role("patient", phrase[0], phrase[1], "literal")
                    roles.append(_expand_coord_role(ctx, patient))
                break
    if clause.predicate == "由来する":
        for index, token in enumerate(ctx.tokens):
            if (token.end > pred[0] or _surface(token) != "に"
                    or getattr(_feature(token.token), "pos1", "") != "助詞"):
                continue
            phrase = _phrase_before_particle(ctx, index)
            if phrase is not None and token.end == pred[0]:
                roles.append(Role("source", phrase[0], phrase[1], "literal"))
                return tuple(roles)
        return tuple(roles)
    if clause.predicate != "結ぶ":
        return tuple(roles)
    source_role = None
    target_role = None
    for index, token in enumerate(ctx.tokens):
        surface = _surface(token)
        if surface not in ("から", "まで") or getattr(_feature(token.token), "pos1", "") != "助詞":
            continue
        phrase = _phrase_before_particle(ctx, index)
        if phrase is None:
            continue
        if surface == "から" and token.start < pred[0] and source_role is None:
            source_role = Role("source", phrase[0], phrase[1], "literal")
        elif (surface == "まで" and token.start < pred[0]
              and ctx.sentence_text[token.end:pred[0]].startswith("を")):
            target_role = Role("recipient", phrase[0], phrase[1], "literal")
    return tuple(roles) + tuple(role for role in (source_role, target_role) if role is not None)


def _drop_nominal_subrole(ctx: ConstructionContext, roles):
    """Discard a false patient span nested inside an overt ``X等の種類`` head."""
    result = []
    for role in roles:
        pos = _local(role.span, ctx.sentence_span)
        redundant = False
        if role.name == "patient" and pos is not None:
            if not ctx.sentence_text.startswith("を", pos[1]):
                for head in roles:
                    if head.name != "agent" or head.span == role.span:
                        continue
                    head_pos = _local(head.span, ctx.sentence_span)
                    if head_pos is None or not (head_pos[0] <= pos[0] < pos[1] < head_pos[1]):
                        continue
                    tail = ctx.sentence_text[pos[1]:head_pos[1]]
                    if tail.endswith(("等の種類", "の種類")):
                        redundant = True
                        break
        if not redundant:
            result.append(role)
    return tuple(result)


def _nominal_tokens(ctx: ConstructionContext, tokens) -> bool:
    if not tokens:
        return False
    for token in tokens:
        feature = _feature(token.token)
        surface = _surface(token)
        pos1 = getattr(feature, "pos1", "")
        if (pos1 in ("名詞", "接尾辞", "形状詞", "代名詞")
                or (pos1 == "助詞" and surface in ("の", "と", "や", "または"))
                or (pos1 == "補助記号" and (all(ch in _PUNCT for ch in surface) or surface.isspace()))
                or surface.isspace()):
            continue
        return False
    return True


def _tail_head(ctx: ConstructionContext, final: Clause, chain_end: int) -> Role | None:
    tail = [t for t in ctx.tokens if t.end > chain_end]
    if not tail:
        return None
    punctuation = []
    while tail:
        token = tail[-1]
        feature = _feature(token.token)
        surface = _surface(token)
        if getattr(feature, "pos1", "") == "補助記号" and surface and all(ch in _PUNCT for ch in surface):
            punctuation.insert(0, tail.pop())
            continue
        break
    if not tail:
        return None
    last_feature = _feature(tail[-1].token)
    if (getattr(last_feature, "pos1", "") == "動詞"
            and getattr(last_feature, "lemma", "") in ("有る", "ある") and len(tail) >= 3
            and _surface(tail[-2]) == "で"):
        head = tail[:-2]
        if not _nominal_tokens(ctx, head):
            return None
        start, end = head[0].start, head[-1].end
        phrase = ctx.sentence_text[start:end]
        return Role("nominal_head", phrase,
                    Span(ctx.sentence_span.source, ctx.sentence_span.start + start,
                         ctx.sentence_span.start + end, phrase), "literal")
    if not _nominal_tokens(ctx, tail):
        return None
    prior = next((t for t in reversed(ctx.tokens) if t.end <= chain_end), None)
    prior_feature = _feature(prior.token) if prior is not None else None
    if prior_feature is None or not str(getattr(prior_feature, "cForm", "")).startswith("連体形"):
        return None
    start, end = tail[0].start, tail[-1].end
    phrase = ctx.sentence_text[start:end]
    return Role("nominal_head", phrase,
                Span(ctx.sentence_span.source, ctx.sentence_span.start + start,
                     ctx.sentence_span.start + end, phrase), "literal")


def _pred_range(text: str, clause: Clause, sentence: Span) -> tuple[int, int] | None:
    pos = _local(clause.predicate_span, sentence)
    if pos is None or text[pos[0]:pos[1]] != clause.predicate_span.text:
        return None
    if clause.predicate_span.text == clause.predicate:
        return pos
    if clause.predicate.endswith("する"):
        prefix = clause.predicate[:-2]
        if prefix:
            start = pos[0] - len(prefix)
            if start < 0 or text[start:pos[0]] != prefix:
                return None
            return start, pos[1]
    return pos


def _morphology_ok(ctx: ConstructionContext, clause: Clause, following: str = "") -> bool:
    token = _token_for(ctx, clause)
    if token is None or not _lemma_matches(clause, token, ctx.sentence_text,
                                             clause.predicate_span.start - ctx.sentence_span.start):
        return False
    form = str(getattr(_feature(token.token), "cForm", ""))
    if following in ("て", "で", "ながら", "、", "連用中止"):
        return form.startswith("連用形")
    if clause.time == "past":
        pos = clause.predicate_span.end - ctx.sentence_span.start
        return form.startswith("連用形") and ctx.sentence_text.startswith(("た", "だ"), pos)
    if clause.time not in ("", "nonpast"):
        return False
    if form.startswith(("連用形", "終止形", "連体形")):
        return True
    return form.startswith("未然形") and _passive_aux(ctx, clause) is not None


def _passive_aux(ctx: ConstructionContext, clause: Clause) -> tuple[int, int] | None:
    token = _token_for(ctx, clause)
    if token is None:
        return None
    for following in ctx.tokens:
        if following.start < token.end:
            continue
        if following.start != token.end:
            return None
        feature = _feature(following.token)
        surface = _surface(following)
        if (getattr(feature, "pos1", "") == "助動詞"
                and surface in ("れる", "られる")):
            return following.start, following.end
        return None
    return None


def _chain_end(ctx: ConstructionContext, clause: Clause) -> int | None:
    end = clause.predicate_span.end - ctx.sentence_span.start
    if not 0 <= end <= len(ctx.sentence_text):
        return None
    if clause.time == "past":
        if ctx.sentence_text.startswith("た", end) or ctx.sentence_text.startswith("だ", end):
            return end + 1
        return None
    if clause.time not in ("", "nonpast"):
        return None
    return end


def _covered(ctx: ConstructionContext, clauses: tuple[Clause, ...], links: tuple[tuple[int, int], ...],
             chain_start: int, chain_end: int) -> bool:
    text = ctx.sentence_text
    if not 0 <= chain_start < chain_end <= len(text):
        return False
    covered = [False] * (chain_end - chain_start)

    def mark(start: int, end: int) -> bool:
        if start == end:
            return chain_start <= start <= chain_end
        if not chain_start <= start < end <= chain_end:
            return False
        for i in range(start - chain_start, end - chain_start):
            covered[i] = True
        return True

    for clause in clauses:
        pred = _pred_range(text, clause, ctx.sentence_span)
        if pred is None or not mark(*pred):
            return False
        for role in clause.roles:
            rp = _local(role.span, ctx.sentence_span)
            pm = _role_mark(role, text, ctx.sentence_span)
            if rp is None or pm is None or not mark(*rp) or not mark(*pm):
                return False
    for start, end in links:
        if not mark(start, end):
            return False

    for left, right in zip(clauses, clauses[1:]):
        left_end = left.predicate_span.end - ctx.sentence_span.start
        right_start = right.predicate_span.start - ctx.sentence_span.start
        for token in ctx.tokens:
            feature = _feature(token.token)
            if (left_end <= token.start and token.end <= right_start
                    and _surface(token) in _ADDITIVE_MARKERS
                    and getattr(feature, "pos1", "") in ("副詞", "接続詞")):
                mark(token.start, token.end)

    for token in ctx.tokens:
        start, end = max(token.start, chain_start), min(token.end, chain_end)
        if end <= start:
            continue
        local_start, local_end = start - chain_start, end - chain_start
        if all(covered[local_start:local_end]):
            continue
        feature = _feature(token.token)
        pos1 = getattr(feature, "pos1", "")
        surf = _surface(token)
        if pos1 in ("補助記号", "記号") and surf and all(ch in _PUNCT for ch in surf):
            mark(start, end)
            continue
        if not surf.strip():
            mark(start, end)
            continue
        if pos1 == "助詞" and surf in _CASE_PARTICLES | _CONNECTIVE_PARTICLES:
            mark(start, end)
            continue
        if pos1 == "助動詞" and token.start >= 0 and token.end <= chain_end:
            raw = text[start:end]
            if raw in ("た", "だ") and clauses[-1].time == "past":
                mark(start, end)
                continue
            if raw in ("れる", "られる") and any(_passive_aux(ctx, clause) == (token.start, token.end)
                                                    for clause in clauses):
                mark(start, end)
                continue
        return False
    return all(covered)


def _reads(ctx: ConstructionContext) -> Reading | None:
    if len(ctx.tokens) > ctx.budget.max_tokens:
        return None
    sentence = ctx.sentence_span
    if (sentence.text != ctx.sentence_text or sentence.start < 0 or sentence.end - sentence.start != len(ctx.sentence_text)):
        return None
    native = [c for c in ctx.clauses if c.rule == "frame" and c.span.source == sentence.source
              and c.span.start == sentence.start and c.span.end == sentence.end and c.span.text == sentence.text]
    if len(native) < 2 or len(native) > ctx.budget.max_clauses:
        return None
    native.sort(key=lambda c: (c.predicate_span.start, c.predicate_span.end, c.predicate))
    if any(a.predicate_span.start == b.predicate_span.start for a, b in zip(native, native[1:])):
        return None
    if any(not c.unsupported or not set(c.unsupported).issubset(_CLEARABLE) for c in native):
        return None
    if any(c.span.source == sentence.source and c.span.start == sentence.start
           and c.span.end == sentence.end and not c.unsupported for c in ctx.clauses):
        return None
    if any(c.polarity != "+" or c.modality != "assert" or c.conditions or c.exceptions for c in native):
        return None
    if len(ctx.tokens) * (len(native) + 1) > ctx.budget.max_steps:
        return None

    links: list[tuple[int, int]] = []
    markers: list[str] = []
    for left, right in zip(native, native[1:]):
        link = _connection(ctx.sentence_text, left, right, sentence, ctx)
        if link is None:
            return None
        begin, finish = link
        prefix = ctx.sentence_text[begin:finish] if begin < finish else "連用中止"
        if not _morphology_ok(ctx, left, prefix):
            return None
        links.append(link)
        markers.append(prefix)
    if not _semantic_coord_ok(ctx, native, markers):
        return None
    if not _new_subject_scope_ok(ctx, native):
        return None

    final_end = _chain_end(ctx, native[-1])
    if final_end is None or final_end <= 0:
        return None
    if not _morphology_ok(ctx, native[-1]):
        return None

    subject_roles = _subject_roles(ctx, tuple(native))
    scoped = []
    for index, base in enumerate(native):
        roles = ()
        for role in base.roles:
            role = _expand_coord_role(ctx, _canonical_role(ctx, role, base.predicate))
            expanded = _expand_modifier_role(ctx, role, base.roles)
            attributes = _modifier_attributes(ctx, role, expanded)
            roles += (role if attributes else expanded,)
            roles += attributes
        for role in subject_roles[index]:
            if not any(existing.span == role.span for existing in roles):
                roles += (role,)
        manner = _manner_role(ctx, base)
        if manner is not None and not any(r.name == "manner" and r.span == manner.span for r in roles):
            roles += (manner,)
        learning_source = _learning_source(ctx, base)
        if learning_source is not None and not any(r.name == "source" and r.span == learning_source.span for r in roles):
            roles += (learning_source,)
        for frame_role in _predicate_frame_roles(ctx, base):
            if not any(r.name == frame_role.name and r.span == frame_role.span for r in roles):
                roles += (frame_role,)
        if not roles:
            return None
        scoped.append(replace(base, roles=_drop_nominal_subrole(ctx, roles)))

    head = _tail_head(ctx, native[-1], final_end)
    if head is not None:
        scoped[-1] = replace(scoped[-1], roles=scoped[-1].roles + (head,))

    # The source prefix must begin at the sentence boundary and every content
    # token inside the chain must be an overt role, a predicate, or grammar.
    # This makes the chain span a real scope boundary instead of borrowing
    # nearby material.
    if not _covered(ctx, tuple(scoped), tuple(links), 0, len(ctx.sentence_text)):
        return None

    chain_span = Span(sentence.source, sentence.start, sentence.end, sentence.text)
    clauses: list[Clause] = []
    for base in scoped:
        digest = sha256((base.span.source + ":" + str(base.span.start) + ":" +
                         str(base.predicate_span.start) + ":" + base.predicate).encode("utf-8")).hexdigest()[:24]
        event = Variable(name="event_" + digest, sort="event")
        clauses.append(replace(base, id=digest, event=event, span=sentence, body_span=sentence,
                               rule=_RULE, unsupported=()))
    note = TypedNote("clause_scope", chain_span,
                     "connected predicates retain source-local roles over one explicit chain span")
    return Reading(tuple(clauses), (sentence,), (note,))


def _surface_matches(clause: Clause, source: str) -> bool:
    span = clause.predicate_span
    if (span.source != clause.span.source or not clause.span.start <= span.start < span.end <= clause.span.end
            or source[span.start:span.end] != span.text):
        return False
    form = span.text
    lemma = clause.predicate
    if form == lemma:
        return True
    if lemma.endswith("する"):
        prefix = lemma[:-2]
        return form in ("し", "する") and (not prefix or source[span.start - len(prefix):span.start] == prefix)
    if lemma.endswith("ずる"):
        return form in (lemma[:-2] + "じ", lemma[:-2] + "ず")
    if not lemma:
        return False
    last = lemma[-1]
    stem = lemma[:-1] if last in "るうくぐすつぬぶむ" else lemma
    endings = {
        "る": ("り", "っ", ""), "う": ("い", "っ"), "く": ("き", "い"),
        "ぐ": ("ぎ", "い"), "す": ("し",), "つ": ("ち", "っ"),
        "ぬ": ("に", "ん"), "ぶ": ("び", "ん"), "む": ("み", "ん"),
    }
    possible = {stem + suffix for suffix in endings.get(last, ("",))}
    possible.add(lemma)
    return form in possible


def _license_mark(role, source: str, boundary: int | None = None) -> bool:
    span = role.span
    if (span.source == "" or not isinstance(role.term, str) or role.term != span.text
            or role.rule not in ("frame", "case", "literal") or not 0 <= span.start < span.end <= len(source)
            or source[span.start:span.end] != span.text):
        return False
    if role.name == "nominal_head":
        tail = source[span.end:boundary] if boundary is not None else source[span.end:]
        return (tail.startswith(("であった", "である", "だった", "だ"))
                or all(ch in _PUNCT or ch.isspace() for ch in tail))
    if role.name == "attribute" and role.rule == "literal":
        return source.startswith("の", span.end)
    if role.name == "recipient" and role.rule == "literal" and source.startswith("まで", span.end):
        return True
    if role.name == "manner" and role.rule == "literal" and span.text.endswith(("く", "に")):
        return True
    if role.name == "source" and role.rule == "literal":
        return any(source.startswith(mark, span.end) for mark in ("に", "から", "より"))
    if role.name == "topic" and source.startswith("とは", span.end):
        return True
    allowed = _ROLE_MARKS.get(role.name, ())
    if not allowed:
        return False
    return any(source.startswith(mark, span.end) for mark in sorted(allowed, key=len, reverse=True))


def _source_has_chain(clause: Clause, source: str) -> bool:
    body = clause.body_span
    if body is None:
        return False
    raw = body.text
    start, end = body.start, body.end
    local_start = clause.predicate_span.start - start
    local_end = clause.predicate_span.end - start
    if raw != source[start:end] or not body.start <= clause.predicate_span.start < clause.predicate_span.end <= body.end:
        return False
    if not _surface_matches(clause, source):
        return False
    before = raw[:local_start]
    after = raw[local_end:]
    # The linked event must sit beside another finite predicate in the bounded
    # source scope.  The reader uses tagged morphology; this pass uses only the
    # independent source spelling and conjugation boundaries.
    edge = re.compile(r"[一-龯々〆ヵヶぁ-んァ-ヶーA-Za-z0-9]+(?:ながら|て|で|、)[^。]*\Z")
    if edge.search(before):
        return True
    marker = next((m for m in ("ながら", "て", "で", "、") if after.startswith(m)), "")
    if marker and _VERB_END.search(after[len(marker):]):
        return True
    # Bare 連用中止 can be followed by an overt case phrase before the next
    # predicate.  This independent check does not depend on the reader's token
    # match and requires a later finite predicate in the same body span.
    bare = re.compile(r"[一-龯々〆ヵヶぁ-んァ-ヶーA-Za-z0-9]+(?:り|き|ぎ|し|ち|に|び|み|い|っ|ん)[^。]*(?:を|に|で|へ|が|は)[^。]*\Z")
    return bool(bare.search(before) or _VERB_END.search(after))


def _attribute_licensed(clause: Clause, role: Role, source: str) -> bool:
    body = clause.body_span
    span = role.span
    if (body is None or role.rule != "literal" or not isinstance(role.term, str)
            or role.term != span.text or source[span.start:span.end] != span.text
            or not source.startswith("の", span.end)):
        return False
    if not any(other.name != "attribute" and other.span.start == span.end + 1
               for other in clause.roles):
        return False
    raw = source[body.start:body.end]
    cursor = body.start
    for token in Tagger()(raw):
        end = cursor + len(token.surface)
        feature = _feature(token)
        if (cursor == span.start and end == span.end and token.surface == role.term
                and getattr(feature, "pos1", "") in ("形容詞", "形状詞", "連体詞")):
            return True
        cursor = end
    return False


def _licenses(clause: Clause, source: str) -> bool:
    if (clause.rule != _RULE or clause.unsupported or clause.polarity != "+"
            or clause.modality != "assert" or clause.time not in ("past", "nonpast", "")
            or clause.conditions or clause.exceptions or clause.exception_of):
        return False
    span = clause.span
    if (not isinstance(source, str) or not isinstance(span.source, str) or span.source == ""
            or type(span.start) is not int or type(span.end) is not int
            or not 0 <= span.start < span.end <= len(source) or source[span.start:span.end] != span.text):
        return False
    body = clause.body_span
    if (body is None or body != span or body.source != span.source
            or source[body.start:body.end] != body.text or not _source_has_chain(clause, source)):
        return False
    if not clause.roles or len(clause.roles) > 32:
        return False
    seen = set()
    for role in clause.roles:
        key = (role.name, role.span.start, role.span.end)
        if (role.name == "source" and role.rule == "literal"
                and clause.predicate not in ("学ぶ", "習う", "由来する", "結ぶ")):
            return False
        if role.name == "attribute" and not _attribute_licensed(clause, role, source):
            return False
        if key in seen or not _license_mark(role, source, body.end):
            return False
        if not body.start <= role.span.start < role.span.end <= body.end:
            return False
        seen.add(key)
    return True


register(Construction(name=_RULE, priority=80, reads=_reads, licenses=_licenses))
