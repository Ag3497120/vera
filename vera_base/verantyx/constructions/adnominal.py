"""Source-bounded relative clauses with an explicit nominal gap."""
from __future__ import annotations

import hashlib
import re

from . import Construction, ConstructionContext, Reading, TypedNote, register
from ..semantic_ir import Clause, Role, Span, Variable


_GAP_REASONS = ("unlocated patient", "unlocated agent")
_SAFE_UNSUPPORTED = frozenset(("multiple predicates need explicit clause scope",
                               "unrepresented source content"))
_PARTICLE_GAP = re.compile(
    r"(?:(?:における|において|に対して|によって|により|について|として|"
    r"ともに|と共に|では|には|から|まで|より|だけ|こそ|など|等|"
    r"に|で|を|が|は|へ|と|も|の|や|か))*\Z")
_PASSIVE_END = re.compile(r"(?:られ|れ)(?:た|る)?\Z")
_NEGATIVE_PASSIVE_END = re.compile(r"(?:られ|れ)(?:ない|ず|なかった)\Z")
_ACTIVE_END = re.compile(r"(?:う|く|ぐ|す|つ|ぬ|ぶ|む|る|た|だ|ない|なかった|ます|ました)\Z")
_PURPOSE_FORM = re.compile(r"(?P<relation>.+)と(?P<form>した|する)\Z")
_LOCATIVE_PREDICATES = frozenset(("ある", "存在する", "位置する", "所在する"))
_RELATIONAL_PREDICATES = {"属する": "group", "面する": "setting"}
_RELATIONAL_NAMES = frozenset(_RELATIONAL_PREDICATES)
_DATE = re.compile(
    r"(?:(?:\d{1,4}|(?:令和|平成|昭和|大正|明治)(?:元|\d{1,2}))年"
    r"(?:\d{1,2}月(?:\d{1,2}日)?)?)\Z")
_NOMINALIZERS = frozenset(("こと", "もの", "場合", "時", "とき", "ため", "よう", "例"))


def _surface(item) -> str:
    return getattr(item.token, "surface", str(item.token))


def _pos(item) -> str:
    return getattr(item.token, "pos", "")


def _noun(item) -> bool:
    return _pos(item).startswith("名詞,")


def _nominal_part(item) -> bool:
    pos = _pos(item)
    return pos.startswith(("名詞,", "接頭辞,", "接尾辞,", "形状詞,", "形容詞,", "連体詞,"))


def _nominal_group_start(tokens, last: int) -> int:
    first = last
    while first > 0:
        if _nominal_part(tokens[first - 1]):
            first -= 1
        elif (first > 1 and _surface(tokens[first - 1]) == "の"
              and _nominal_part(tokens[first - 2])):
            first -= 2
        elif (first > 1 and _surface(tokens[first - 1]) == "な"
              and _pos(tokens[first - 1]).startswith("助動詞,")
              and _nominal_part(tokens[first - 2])):
            first -= 2
        else:
            break
    return first


def _head(tokens, first: int):
    """Return a bounded prenominal phrase span and its lexical noun head."""
    if first >= len(tokens) or not _nominal_part(tokens[first]):
        return None
    has_noun = False
    last = first - 1
    head = ""
    i = first
    while i < len(tokens) and i - first < 32:
        item = tokens[i]
        if _nominal_part(item):
            if _noun(item):
                has_noun = True
                head = _surface(item)
            elif _pos(item).startswith("接尾辞,") and has_noun:
                head = _surface(item)
            last = i
            i += 1
            continue
        if (_surface(item) == "の" and _pos(item).startswith("助詞,格助詞")
                and last >= first and i + 1 < len(tokens) and _nominal_part(tokens[i + 1])):
            last = i
            i += 1
            continue
        if (_surface(item) == "な" and _pos(item).startswith("助動詞,")
                and last >= first and i + 1 < len(tokens) and _nominal_part(tokens[i + 1])):
            last = i
            i += 1
            continue
        if (_surface(item) in ("・", "＝", "=", "-", "‐", "–", "/", "&")
                and last >= first and i + 1 < len(tokens) and _nominal_part(tokens[i + 1])):
            last = i
            i += 1
            continue
        break
    if not has_noun or not head:
        return None
    return tokens[first].start, tokens[last].end, head, last + 1


def _head_is_nominalizer(tokens, first: int) -> bool:
    return first < len(tokens) and _surface(tokens[first]) in _NOMINALIZERS


def _negative_matrix(tokens, after: int) -> bool:
    for item in tokens[after:]:
        if _pos(item).startswith("補助記号,") and _surface(item) in ("。", "！", "？", "、"):
            break
        if _surface(item) in ("ない", "なかった", "ぬ", "ず", "ません", "ませんでした"):
            return True
    return False


def _span(source: str, start: int, end: int, text: str) -> Span:
    return Span(source, start, end, text)


def _make_clause(ctx: ConstructionContext, base: Clause | None, predicate: str,
                 predicate_span: Span, body_start: int, head_span: Span,
                 head: str, gap_name: str, gap_term, extra_roles: tuple[Role, ...],
                 time: str, polarity: str = "+") -> Clause:
    digest = hashlib.sha256(
        f"{ctx.sentence_span.source}:{predicate_span.start}:{predicate}".encode("utf-8")
    ).hexdigest()[:24]
    event = Variable("event_" + digest, "event")
    head_nominal = head_span.text
    roles = (Role(gap_name, head_nominal, head_span, "nominal"),
             Role("modifier", head_nominal, head_span, "nominal")) + extra_roles
    return Clause(
        id=digest, event=event, predicate=predicate, predicate_span=predicate_span,
        roles=roles, span=ctx.sentence_span,
        body_span=ctx.sentence_span,
        polarity=polarity, modality="assert", time=time, rule="adnominal",
        sovereign=base.sovereign if base else "document",
        family=base.family if base else "document", unsupported=())


def _role_source_ok(role: Role, ctx: ConstructionContext) -> bool:
    s = ctx.sentence_span
    return (role.span.source == s.source and s.start <= role.span.start < role.span.end <= s.end
            and role.span.text == s.text[role.span.start - s.start:role.span.end - s.start]
            and role.name != "ambiguous")


def _case_text_after(role: Role, roles: tuple[Role, ...], predicate_start: int,
                     source: str, offset: int = 0) -> str:
    following = min((r.span.start for r in roles
                     if r is not role and r.span.start >= role.span.end),
                    default=predicate_start)
    return source[role.span.end - offset:following - offset]


def _body_gaps_are_particles(ctx: ConstructionContext, body_start: int,
                             pred_start: int, roles: tuple[Role, ...]) -> bool:
    intervals = sorted((r.span.start, r.span.end) for r in roles)
    intervals.append((pred_start, pred_start))
    intervals.sort()
    cursor = body_start
    for start, end in intervals:
        if start < cursor:
            return False
        gap = ctx.sentence_span.text[cursor - ctx.sentence_span.start:
                                     start - ctx.sentence_span.start]
        if gap.strip() and not _PARTICLE_GAP.fullmatch(gap):
            return False
        cursor = end
    return True


def _finite_tail(tokens, pred_end: int):
    """Return end token, passive marker and tense for a bounded auxiliary tail."""
    i = next((j for j, t in enumerate(tokens) if t.start >= pred_end), len(tokens))
    if i < len(tokens) and tokens[i].start != pred_end:
        return None
    first = i
    surfaces = []
    while i < len(tokens) and _pos(tokens[i]).startswith("助動詞,") and i - first < 4:
        surfaces.append(_surface(tokens[i]))
        i += 1
    chain = "".join(surfaces)
    passive = bool(surfaces and surfaces[0] in ("れ", "られ", "れる", "られる"))
    if passive:
        if _NEGATIVE_PASSIVE_END.fullmatch(chain):
            return (i, True, "past" if chain.endswith("なかった") else "nonpast", "-")
        if not _PASSIVE_END.fullmatch(chain):
            return None
        return (i, True, "past" if chain.endswith(("た", "だ")) else "nonpast", "+")
    if chain and chain not in ("た", "だ", "る", "ない", "なかった"):
        return None
    negative = chain in ("ない", "なかった")
    return (i, False, "past" if chain in ("た", "だ", "なかった") else "nonpast",
            "-" if negative else "+")


def _predicate_start(ctx: ConstructionContext, clause: Clause, token_starts: list[int]) -> int:
    start = clause.predicate_span.start - ctx.sentence_span.start
    if not clause.predicate.endswith("する"):
        return start
    # The tagger separates verbal nouns from their する inflection.
    i = next((i for i, at in enumerate(token_starts) if at == start), -1)
    if i <= 0:
        return start
    j = i - 1
    while j >= 0 and _noun(ctx.tokens[j]):
        start = ctx.tokens[j].start
        j -= 1
    return start


def _passive_readings(ctx: ConstructionContext) -> tuple[list[Clause], list[Span], list[TypedNote]]:
    out: list[Clause] = []
    consumed: list[Span] = []
    notes: list[TypedNote] = []
    sentence = ctx.sentence_span
    tokens = ctx.tokens
    starts = [t.start for t in tokens]
    local_clauses = [c for c in ctx.clauses if c.span.source == sentence.source
                     and c.span.start == sentence.start]
    for base in local_clauses:
        gaps = [name.removeprefix("unlocated ") for name in _GAP_REASONS
                if name in base.unsupported]
        if len(gaps) != 1:
            continue
        gap_name = gaps[0]
        stem_start = _predicate_start(ctx, base, starts)
        stem_end = base.predicate_span.end - sentence.start
        if not (0 <= stem_start < stem_end <= len(sentence.text)):
            continue
        if sentence.text[base.predicate_span.start - sentence.start:stem_end] != base.predicate_span.text:
            continue
        after = _finite_tail(tokens, stem_end)
        if after is None:
            continue
        after_i, passive, time, polarity = after
        if ((gap_name == "patient" and not passive)
                or (gap_name == "agent" and passive)):
            continue
        if after_i >= len(tokens):
            continue
        head_info = _head(tokens, after_i)
        if head_info is None or _head_is_nominalizer(tokens, after_i):
            continue
        head_start, head_end, head, _ = head_info
        if (_negative_matrix(tokens, head_info[3])
                or (head_info[3] < len(tokens) and _surface(tokens[head_info[3]]) == "と")):
            continue
        pred_end = tokens[after_i - 1].end if after_i > 0 else stem_end
        pred_start = stem_start
        pred_span = _span(sentence.source, sentence.start + pred_start,
                          sentence.start + pred_end, sentence.text[pred_start:pred_end])
        head_span = _span(sentence.source, sentence.start + head_start,
                          sentence.start + head_end, sentence.text[head_start:head_end])
        local_roles_list = []
        special_reasons = set()
        local_notes = []
        date_role = False
        adjunct_index = 0
        source_roles = tuple(r for r in base.roles if r.span.end <= sentence.start + pred_start)
        for role in base.roles:
            if role.span.end > sentence.start + pred_start:
                continue
            surface_gap = _case_text_after(role, source_roles, sentence.start + pred_start,
                                           sentence.text, sentence.start)
            exact_date = bool(_DATE.fullmatch(role.span.text))
            if exact_date and surface_gap == "に":
                local_roles_list.append(Role("time", role.span.text, role.span, "literal"))
                date_role = True
            elif role.name == "ambiguous":
                particle = surface_gap
                if (base.predicate == "呼ぶ" and role.rule == "case:と:companion|quotation"
                        and particle == "と"):
                    local_roles_list.append(Role("label", role.span.text, role.span, "case"))
                    special_reasons.add("ambiguous case role: と")
                elif (base.predicate == "知る" and role.rule == "case:で:place|means"
                      and particle == "で"):
                    local_roles_list.append(Role("basis", role.span.text, role.span, "case"))
                    special_reasons.add("ambiguous case role: で")
                else:
                    fields = role.rule.split(":")
                    marker = fields[1] if len(fields) > 1 and fields[0] == "case" else ""
                    if not marker or not _PARTICLE_GAP.fullmatch(surface_gap) or not surface_gap:
                        local_roles_list = []
                        break
                    adjunct_index += 1
                    local_roles_list.append(Role(f"adjunct_{adjunct_index}", role.span.text,
                                                 role.span, "case"))
                    special_reasons.add("ambiguous case role: " + marker)
                    local_notes.append(TypedNote(
                        "ambiguous_adnominal_case", role.span,
                        "case phrase retained as a source-bounded adjunct; semantic case unresolved"))
            else:
                local_roles_list.append(role)
        local_roles = tuple(local_roles_list)
        unsupported = set(base.unsupported)
        allowed = set(_SAFE_UNSUPPORTED) | set(_GAP_REASONS) | special_reasons
        if adjunct_index > 1:
            allowed.add("duplicate role in clause")
        time_reason = "unsupported source quantifier/exception/time"
        body_start = min((r.span.start for r in local_roles), default=sentence.start + pred_start)
        prefix = sentence.text[:body_start - sentence.start]
        local_scope = sentence.text[body_start - sentence.start:head_end]
        date_outside = bool(_DATE.search(prefix) and not _DATE.search(local_scope))
        if date_role or date_outside:
            allowed.add(time_reason)
        if any(reason not in allowed for reason in unsupported):
            continue
        if any(not _role_source_ok(r, ctx) for r in local_roles):
            continue
        if any(r.span.start < sentence.start + head_end and r.span.end > sentence.start + head_start
               for r in base.roles):
            continue
        if any(r.name == "modifier" for r in local_roles):
            continue
        if gap_name in {r.name for r in local_roles}:
            continue
        if len({r.name for r in local_roles}) != len(local_roles):
            continue
        body_start = min((r.span.start for r in local_roles), default=sentence.start + pred_start)
        if body_start < sentence.start + pred_start and not _body_gaps_are_particles(
                ctx, body_start, sentence.start + pred_start, local_roles):
            continue
        if body_start == sentence.start + pred_start and pred_start:
            previous = next((t for t in reversed(tokens) if t.end == pred_start), None)
            if previous is not None and not (_pos(previous).startswith("補助記号,")
                                             and _surface(previous) in "、。）」』】"):
                continue
        clause = _make_clause(ctx, base, base.predicate, pred_span,
                              body_start, head_span, head, gap_name,
                              None, local_roles, time, polarity)
        if not _colon_scope_ok(clause):
            continue
        if not licenses(clause, sentence.text if sentence.start == 0 else ""):
            # The public licensor takes the whole document; local validation below
            # mirrors its grammar on the sentence-local offsets.
            if not _local_gap_shape(clause, sentence.text, sentence.start):
                continue
        out.append(clause)
        consumed.append(sentence)
        notes.extend(local_notes)
    return out, consumed, notes


def _locative_form_ok(clause: Clause, source: str, offset: int) -> bool:
    raw = clause.predicate_span.text
    if clause.predicate == "ある":
        forms = ("ある", "あった", "ない", "なかった")
    elif clause.predicate in _LOCATIVE_PREDICATES | _RELATIONAL_NAMES:
        stem = clause.predicate[:-2]
        forms = tuple(stem + ending for ending in ("する", "した", "しない", "しなかった"))
    else:
        return False
    if raw not in forms:
        return False
    negative = raw.endswith(("ない", "なかった"))
    past = raw.endswith(("た", "だ", "なかった"))
    return clause.polarity == ("-" if negative else "+") and clause.time == ("past" if past else "nonpast")


def _locative_readings(ctx: ConstructionContext) -> tuple[list[Clause], list[Span]]:
    out: list[Clause] = []
    consumed: list[Span] = []
    sentence = ctx.sentence_span
    tokens = ctx.tokens
    starts = [t.start for t in tokens]
    local = [c for c in ctx.clauses if c.span.source == sentence.source
             and c.span.start == sentence.start]
    for base in local:
        if base.predicate not in _LOCATIVE_PREDICATES | _RELATIONAL_NAMES:
            continue
        stem_start = _predicate_start(ctx, base, starts)
        stem_end = base.predicate_span.end - sentence.start
        if not (0 <= stem_start < stem_end <= len(sentence.text)):
            continue
        tail = _finite_tail(tokens, stem_end)
        if tail is None:
            continue
        after_i, passive, time, polarity = tail
        if passive or after_i >= len(tokens):
            continue
        head_info = _head(tokens, after_i)
        if (head_info is None or _head_is_nominalizer(tokens, after_i)
                or _negative_matrix(tokens, head_info[3])
                or (head_info[3] < len(tokens) and _surface(tokens[head_info[3]]) == "と")):
            continue
        head_start, head_end, head, _ = head_info
        pred_end = tokens[after_i - 1].end if after_i > 0 else stem_end
        pred_start = stem_start
        pred_span = _span(sentence.source, sentence.start + pred_start,
                          sentence.start + pred_end, sentence.text[pred_start:pred_end])
        head_span = _span(sentence.source, sentence.start + head_start,
                          sentence.start + head_end, sentence.text[head_start:head_end])
        raw_roles = tuple(r for r in base.roles if r.span.end <= sentence.start + pred_start)
        setting = None
        extra: list[Role] = []
        invalid = False
        for role in raw_roles:
            following = _case_text_after(role, raw_roles, sentence.start + pred_start,
                                         sentence.text, sentence.start)
            marker = role.rule.split(":")[1] if role.rule.startswith("case:") and ":" in role.rule else ""
            if role.name == "ambiguous":
                if marker != "に" or following != "に":
                    invalid = True
                    break
                if setting is not None:
                    # The full ambiguous source span supersedes a parser subspan.
                    if role.span.start <= setting.span.start and role.span.end >= setting.span.end:
                        setting = Role(_RELATIONAL_PREDICATES.get(base.predicate, "setting"),
                                       role.span.text, role.span, "case")
                        continue
                    if setting.span.start <= role.span.start and setting.span.end >= role.span.end:
                        continue
                    invalid = True
                    break
                setting = Role(_RELATIONAL_PREDICATES.get(base.predicate, "setting"),
                               role.span.text, role.span, "case")
            elif role.name in ("recipient", "setting", "location") and following == "に":   # location: W1-a typed re-read of a locative に
                candidate = Role(_RELATIONAL_PREDICATES.get(base.predicate, "setting"),
                                 role.span.text, role.span, "case")
                if setting is not None:
                    if role.span.start <= setting.span.start and role.span.end >= setting.span.end:
                        setting = candidate
                    elif setting.span.start <= role.span.start and setting.span.end >= role.span.end:
                        continue
                    else:
                        invalid = True
                        break
                else:
                    setting = candidate
            else:
                extra.append(role)
        if invalid or setting is None:
            continue
        extras = (setting, *extra)
        if any(not _role_source_ok(r, ctx) for r in extras):
            continue
        if any(r.name in ("agent", "modifier", "patient") for r in extras):
            continue
        if len({r.name for r in extras}) != len(extras):
            continue
        unsupported = set(base.unsupported)
        allowed = {"unrepresented source content", "ambiguous frame role",
                   "multiple predicates need explicit clause scope",
                   "ambiguous case role: に"}
        if any(r not in allowed for r in unsupported):
            continue
        if any(r.span.start < sentence.start + head_end and r.span.end > sentence.start + head_start
               for r in base.roles):
            continue
        body_start = min((r.span.start for r in extras), default=sentence.start + pred_start)
        if body_start < sentence.start + pred_start and not _body_gaps_are_particles(
                ctx, body_start, sentence.start + pred_start, extras):
            continue
        if body_start == sentence.start + pred_start and pred_start:
            previous = next((t for t in reversed(tokens) if t.end == pred_start), None)
            if previous is not None and not (_pos(previous).startswith("補助記号,")
                                             and _surface(previous) in "、。）」』】"):
                continue
        clause = _make_clause(ctx, base, base.predicate, pred_span, body_start,
                              head_span, head, "agent", None, tuple(extras), time, polarity)
        if not _colon_scope_ok(clause):
            continue
        if sentence.start == 0:
            if not licenses(clause, sentence.text):
                continue
        elif not _local_locative_shape(clause, sentence.text, sentence.start):
            continue
        out.append(clause)
        consumed.append(sentence)
    return out, consumed


def _purpose_readings(ctx: ConstructionContext) -> tuple[list[Clause], list[Span]]:
    out: list[Clause] = []
    consumed: list[Span] = []
    sentence = ctx.sentence_span
    tokens = ctx.tokens
    for i in range(2, len(tokens) - 3):
        if (_surface(tokens[i]) != "と" or not _pos(tokens[i]).startswith("助詞,格助詞")
                or not _noun(tokens[i - 1]) or _surface(tokens[i + 1]) not in ("し", "する")):
            continue
        verb_i = i + 1
        tail_i = verb_i + 1
        if _surface(tokens[verb_i]) == "し":
            if tail_i >= len(tokens) or _surface(tokens[tail_i]) != "た":
                continue
            tail_i += 1
            time = "past"
        else:
            time = "nonpast"
        relation_first = _nominal_group_start(tokens, i - 1)
        object_particle_i = relation_first - 1
        if (object_particle_i < 0 or _surface(tokens[object_particle_i]) != "を"
                or not _pos(tokens[object_particle_i]).startswith("助詞,格助詞")):
            continue
        head_info = _head(tokens, tail_i)
        if (head_info is None or _head_is_nominalizer(tokens, tail_i)
                or _negative_matrix(tokens, head_info[3])
                or (head_info[3] < len(tokens) and _surface(tokens[head_info[3]]) == "と")):
            continue
        head_start, head_end, head, _ = head_info
        if tokens[object_particle_i].end != tokens[i - 1].start:
            continue
        goal_end = tokens[object_particle_i].start
        goal_start = goal_end
        # A nominalized event immediately before を keeps its entire local
        # source phrase as a literal goal term; its internal roles stay opaque.
        if _surface(tokens[object_particle_i - 1]) == "こと":
            nominalizer = tokens[object_particle_i - 1]
            inner = [c for c in ctx.clauses if c.span.source == sentence.source
                     and c.span.start == sentence.start
                     and c.predicate_span.end == sentence.start + nominalizer.start]
            if inner:
                child = max(inner, key=lambda c: c.predicate_span.start)
                starts = [r.span.start for r in child.roles if r.span.end <= child.predicate_span.start]
                goal_start = min(starts + [child.predicate_span.start]) - sentence.start
            else:
                goal_start = nominalizer.start
            goal_end = nominalizer.end
        else:
            # Capture the immediately preceding nominal group without crossing a case marker.
            j = object_particle_i - 1
            if j < 0 or not _nominal_part(tokens[j]):
                continue
            first = j
            while first > 0:
                if _nominal_part(tokens[first - 1]):
                    first -= 1
                elif (first > 1 and _surface(tokens[first - 1]) == "の"
                      and _nominal_part(tokens[first - 2])):
                    first -= 2
                else:
                    break
            goal_start = tokens[first].start
        if not (0 <= goal_start < goal_end and goal_end == tokens[object_particle_i].start):
            continue
        rel_start = tokens[relation_first].start
        pred_end = tokens[tail_i - 1].end
        predicate_span = _span(sentence.source, sentence.start + rel_start,
                               sentence.start + pred_end, sentence.text[rel_start:pred_end])
        goal_span = _span(sentence.source, sentence.start + goal_start,
                          sentence.start + goal_end, sentence.text[goal_start:goal_end])
        head_span = _span(sentence.source, sentence.start + head_start,
                          sentence.start + head_end, sentence.text[head_start:head_end])
        relation = sentence.text[rel_start:tokens[i - 1].end]
        predicate = relation + "とする"
        extra = (Role("patient", goal_span.text, goal_span, "literal"),)
        clause = _make_clause(ctx, None, predicate, predicate_span,
                              goal_span.start, head_span, head, "agent", None,
                              extra, time)
        if not _colon_scope_ok(clause):
            continue
        if not _local_purpose_shape(clause, sentence.text, sentence.start):
            continue
        out.append(clause)
        consumed.append(sentence)
    return out, consumed


def reads(ctx: ConstructionContext) -> Reading | None:
    if (len(ctx.tokens) > ctx.budget.max_tokens
            or len(ctx.clauses) * 2 + len(ctx.tokens) * 4 > ctx.budget.max_steps):
        return None
    if sum(1 for c in ctx.clauses if c.span.source == ctx.sentence_span.source
           and c.span.start == ctx.sentence_span.start) > ctx.budget.max_clauses:
        return None
    purpose, purpose_spans = _purpose_readings(ctx)
    passive, passive_spans, notes = _passive_readings(ctx)
    locative, locative_spans = _locative_readings(ctx)
    clauses = purpose + passive + locative
    if not clauses or len(clauses) > ctx.budget.max_clauses:
        return None
    return Reading(tuple(clauses), tuple(purpose_spans + passive_spans + locative_spans), tuple(notes))


def _same_source_span(span: Span | None, source_id: str, source: str,
                      outer: Span) -> bool:
    return (isinstance(span, Span) and span.source == source_id
            and outer.start <= span.start < span.end <= outer.end
            and source[span.start:span.end] == span.text)


def _colon_scope_ok(clause: Clause) -> bool:
    owned = [clause.predicate_span] + [r.span for r in clause.roles]
    text = clause.span.text
    for mark in (":", "："):
        pos = text.find(mark)
        while pos >= 0:
            absolute = clause.span.start + pos
            if not any(span.start <= absolute < span.end for span in owned):
                return False
            pos = text.find(mark, pos + 1)
    return True


def _event_shape(clause: Clause) -> bool:
    return (isinstance(clause.event, Variable) and clause.event.sort == "event"
            and clause.polarity in ("+", "-") and clause.modality == "assert"
            and not clause.conditions and not clause.condition_spans
            and not clause.exceptions and not clause.exception_spans
            and not clause.exception_of and not clause.unsupported)


def _head_roles(clause: Clause):
    modifiers = [r for r in clause.roles if r.name == "modifier"]
    gaps = [r for r in clause.roles if r.name in ("patient", "agent")
            and r.rule == "nominal" and isinstance(r.term, str)]
    if len(modifiers) != 1 or len(gaps) != 1:
        return None
    gap = gaps[0]
    modifier = modifiers[0]
    if (not isinstance(modifier.term, str) or modifier.term != gap.term
            or modifier.term != gap.span.text
            or modifier.span != gap.span):
        return None
    return gap, modifier


def _complete_body(clause: Clause, source: str, outer: Span,
                   explicit_roles: tuple[Role, ...], gap: Role,
                   predicate_start: int) -> bool:
    body = clause.body_span
    if (not _same_source_span(body, outer.source, source, outer)
            or body.start != outer.start or body.end != outer.end):
        return False
    if gap.span.end > outer.end or gap.span.start >= gap.span.end:
        return False
    scope_start = min((r.span.start for r in explicit_roles), default=clause.predicate_span.start)
    scope_end = gap.span.end
    intervals = [(r.span.start, r.span.end) for r in explicit_roles]
    intervals.append((clause.predicate_span.start, clause.predicate_span.end))
    intervals.sort()
    cursor = scope_start
    for start, end in intervals:
        if start < cursor or start >= scope_end:
            return False
        gap_text = source[cursor:start]
        if gap_text.strip() and not _PARTICLE_GAP.fullmatch(gap_text):
            return False
        cursor = end
    if cursor != predicate_start and cursor > predicate_start:
        return False
    bridge = source[cursor:gap.span.start]
    if bridge.strip() or gap.span.start != clause.predicate_span.end:
        return False
    return True


def _local_gap_shape(clause: Clause, sentence: str, offset: int) -> bool:
    """The local half of the independent licensor used before constructing a reading."""
    gap_link = _head_roles(clause)
    if gap_link is None:
        return False
    gap, _ = gap_link
    pred = clause.predicate_span.text
    if gap.name == "patient":
        ending = _NEGATIVE_PASSIVE_END if clause.polarity == "-" else _PASSIVE_END
        return bool(ending.search(pred)
                    and clause.time == ("past" if pred.endswith(("た", "だ")) else "nonpast"))
    negative = pred.endswith(("ない", "なかった"))
    return bool(_ACTIVE_END.search(pred) and not _PASSIVE_END.search(pred)
                and clause.polarity == ("-" if negative else "+")
                and clause.time == ("past" if pred.endswith(("た", "だ", "なかった")) else "nonpast"))


def _local_locative_shape(clause: Clause, sentence: str, offset: int) -> bool:
    linked = _head_roles(clause)
    if linked is None:
        return False
    gap, _ = linked
    role_name = _RELATIONAL_PREDICATES.get(clause.predicate, "setting")
    settings = [r for r in clause.roles if r.name == role_name]
    if (gap.name != "agent" or len(settings) != 1 or len(clause.roles) != 3
            or settings[0].rule != "case" or settings[0].term != settings[0].span.text
            or clause.predicate_span.end != gap.span.start):
        return False
    setting = settings[0]
    return (sentence[setting.span.end - offset:clause.predicate_span.start - offset] == "に"
            and setting.span.start < clause.predicate_span.start
            and _locative_form_ok(clause, sentence, offset))


def _local_purpose_shape(clause: Clause, sentence: str, offset: int) -> bool:
    gap_link = _head_roles(clause)
    if gap_link is None:
        return False
    gap, _ = gap_link
    goals = [r for r in clause.roles if r.name == "patient" and r.rule == "literal"]
    match = _PURPOSE_FORM.fullmatch(clause.predicate_span.text)
    if (gap.name != "agent" or len(goals) != 1 or match is None
            or clause.predicate != match.group("relation") + "とする"
            or clause.polarity != "+"):
        return False
    goal = goals[0]
    relstart = clause.predicate_span.start - offset
    goalend = goal.span.end - offset
    return (goal.span.start <= goal.span.end and goalend <= relstart
            and sentence[goalend:relstart] == "を"
            and clause.predicate_span.end == gap.span.start
            and clause.time == ("past" if match.group("form") == "した" else "nonpast"))


def licenses(clause: Clause, source: str) -> bool:
    """Verify source morphology, exact role spans and the unique head gap independently."""
    if (not isinstance(clause, Clause) or clause.rule != "adnominal"
            or not isinstance(source, str) or not _event_shape(clause)):
        return False
    outer = clause.span
    if (not isinstance(outer, Span) or outer.start < 0 or outer.end > len(source)
            or outer.start >= outer.end or source[outer.start:outer.end] != outer.text):
        return False
    if not _same_source_span(clause.predicate_span, outer.source, source, outer):
        return False
    linked = _head_roles(clause)
    if linked is None:
        return False
    gap, modifier = linked
    if not _same_source_span(gap.span, outer.source, source, outer):
        return False
    if (not gap.term or not gap.span.text.endswith(gap.term)
            or any(ch in gap.span.text for ch in "。！？、;；")):
        return False
    if (not isinstance(clause.body_span, Span)
            or not _same_source_span(clause.body_span, outer.source, source, outer)
            or clause.body_span != outer):
        return False
    if not _colon_scope_ok(clause):
        return False
    if len({r.name for r in clause.roles}) != len(clause.roles):
        return False

    if clause.predicate in _LOCATIVE_PREDICATES | _RELATIONAL_NAMES:
        if (gap.name != "agent" or len(clause.roles) != 3
                or not _locative_form_ok(clause, source, 0)):
            return False
        role_name = _RELATIONAL_PREDICATES.get(clause.predicate, "setting")
        settings = [r for r in clause.roles if r.name == role_name]
        if (len(settings) != 1 or settings[0].rule != "case"
                or settings[0].term != settings[0].span.text
                or not _same_source_span(settings[0].span, outer.source, source, outer)
                or _case_text_after(settings[0], (settings[0],), clause.predicate_span.start,
                                    source) != "に"
                or clause.predicate_span.end != gap.span.start):
            return False
        return _complete_body(clause, source, outer, tuple(settings), gap,
                              clause.predicate_span.end)

    purpose = _PURPOSE_FORM.fullmatch(clause.predicate_span.text)
    if purpose is not None:
        if not _local_purpose_shape(clause, source, 0):
            return False
        goals = [r for r in clause.roles if r.name == "patient" and r.rule == "literal"]
        goal = goals[0]
        if (not _same_source_span(goal.span, outer.source, source, outer)
                or goal.term != goal.span.text
                or clause.predicate != purpose.group("relation") + "とする"
                or source[goal.span.end:clause.predicate_span.start] != "を"
                or clause.predicate_span.end != gap.span.start):
            return False
        return clause.time == ("past" if purpose.group("form") == "した" else "nonpast")

    if gap.name == "patient":
        ending = _NEGATIVE_PASSIVE_END if clause.polarity == "-" else _PASSIVE_END
        if not ending.search(clause.predicate_span.text):
            return False
    elif gap.name == "agent":
        if not _ACTIVE_END.search(clause.predicate_span.text):
            return False
        if _PASSIVE_END.search(clause.predicate_span.text):
            return False
        if clause.polarity != ("-" if clause.predicate_span.text.endswith(("ない", "なかった")) else "+"):
            return False
    else:
        return False
    expected_time = "past" if clause.predicate_span.text.endswith(("た", "だ", "なかった")) else "nonpast"
    if clause.time != expected_time:
        return False
    explicit = tuple(r for r in clause.roles if r not in (gap, modifier))
    if any(not _same_source_span(r.span, outer.source, source, outer)
           or r.span.end > clause.predicate_span.start
           or r.name == "ambiguous" or r.rule not in ("frame", "case", "literal", "quantity", "nominal")
           for r in explicit):
        return False
    labels = [r for r in explicit if r.name == "label"]
    bases = [r for r in explicit if r.name == "basis"]
    times = [r for r in explicit if r.name == "time"]
    adjuncts = [r for r in explicit if re.fullmatch(r"adjunct_\d+", r.name)]
    if labels and (len(labels) != 1 or clause.predicate != "呼ぶ"
                   or labels[0].rule != "case"
                   or _case_text_after(labels[0], explicit, clause.predicate_span.start,
                                       source) != "と"):
        return False
    if bases and (len(bases) != 1 or clause.predicate != "知る"
                  or bases[0].rule != "case"
                  or _case_text_after(bases[0], explicit, clause.predicate_span.start,
                                      source) != "で"):
        return False
    if any(r.rule != "literal" or not _DATE.fullmatch(r.span.text)
           or _case_text_after(r, explicit, clause.predicate_span.start, source) != "に"
           for r in times):
        return False
    if any(r.rule != "case" or r.term != r.span.text
           or not _PARTICLE_GAP.fullmatch(_case_text_after(r, explicit,
                                                         clause.predicate_span.start, source))
           or not _case_text_after(r, explicit, clause.predicate_span.start, source)
           for r in adjuncts):
        return False
    return _complete_body(clause, source, outer, explicit, gap, clause.predicate_span.end)


register(Construction(name="adnominal", priority=60, reads=reads,
                      licenses=licenses, refines=()))


__all__ = ("licenses", "reads")
