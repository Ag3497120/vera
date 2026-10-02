"""Source-bounded event negation, independently licensed from the reader."""
from __future__ import annotations

import hashlib
import re

from . import Construction, ConstructionContext, Reading, TypedNote, register
from ..frames import _frame as _read_prefix_frame, _predicates, canonical
from ..semantic_ir import Clause, Role, Span, Variable
from ..typed_edges import _base, _tagger


_DOUBLE = re.compile(r"(?:なくはない|なくもない|ないわけではない|ないわけじゃない|"
                     r"ないことはない|ないこともない)\Z")
_SINGLE = re.compile(r"(?:ませんでした|なかった|ません|ない|ず|ぬ)\Z")
_COPULA_NEGATIVE = re.compile(
    r"(?P<entity>[^、,。！？!?\n]+?)[はが](?P<value>[^、,。！？!?\n]+?)"
    r"(?P<negative>ではありませんでした|じゃありませんでした|ではなかった|"
    r"でなかった|じゃなかった|ではありません|じゃありません|ではない|でない|じゃない)"
    r"[。！？!?]*\Z"
)
_BLOCKED = re.compile(
    r"(?:もし|場合|ならば|なら(?!な)|たら|れば|とき|時|際|ただし|"
    r"はず|かもしれ|だろう|でしょう|らしい|そうだ|つもり|"
    r"全部|すべて|それぞれ|以外|同時|以前|以後|最新|現在)"
)
_PUNCT = " \t\r\n。！？!?"
_AFFIRMATIVE_DOUBLE = "affirmative_by_double_negation"
_CONTENT_POS = frozenset(("名詞", "代名詞", "形容詞", "形状詞", "副詞", "接頭辞", "接尾辞"))
_ROLE_PARTICLES = {
    "agent": frozenset(("が", "は", "に", "から", "へ")),
    "patient": frozenset(("を", "が", "は")),
    "recipient": frozenset(("に", "へ", "が", "は", "から")),
}
_RECIPIENT_PREDICATES = frozenset((
    "あげる", "与える", "預ける", "教える", "貸す", "くれる", "届ける", "伝える",
    "手渡す", "送る", "渡す", "返す", "もらう", "貰う", "授ける",
))
_GOAL_PREDICATES = frozenset(("行く", "来る", "帰る", "戻る", "向かう", "着く", "入る", "出る", "進む", "移る", "渡る", "送る", "届ける"))
_LOCATION_PREDICATES = frozenset(("住む", "滞在する", "位置する", "存在する"))
_PLACES = frozenset(("学校", "家", "駅", "公園", "部屋", "店", "会社", "図書館", "病院", "工場", "東京", "大阪", "京都", "日本", "教室", "庭", "海", "山"))
_MEANS = frozenset(("車", "電車", "バス", "飛行機", "船", "自転車", "徒歩", "手", "指", "箸", "包丁", "ペン", "鉛筆", "電話", "メール", "日本語", "英語", "道具", "方法", "手段"))
_TIME = re.compile(r"(?:[0-9０-９]+年(?:[0-9０-９]{1,2}月(?:[0-9０-９]{1,2}日)?)?|"
                   r"(?:明治|大正|昭和|平成|令和)[0-9０-９]+年(?:[0-9０-９]{1,2}月(?:[0-9０-９]{1,2}日)?)?|"
                   r"[0-9０-９]+\s*(?:月|日|時|分|秒|曜日)|頃|ごろ|午前|午後|朝|昼|夜)\Z")
_COMPOUND_ROLES = {
    "capacity": ("として",), "topic": ("について", "では"),
    "by": ("によって", "による", "により"), "setting": ("における", "において"),
    "target": ("に対して",), "accompaniment": ("と共に", "ともに"),
}


def _span(source: str, start: int, end: int, raw: str) -> Span:
    return Span(source, start, end, raw[start:end])


def _context_span(ctx: ConstructionContext, start: int, end: int) -> Span:
    left = start - ctx.sentence_span.start
    right = end - ctx.sentence_span.start
    return Span(ctx.document_id, start, end, ctx.sentence_text[left:right])


def _body_start(text: str) -> int:
    left = len(text) - len(text.lstrip())
    while left < len(text) and text[left] in " 、,":
        left += 1
    return left


def _tagged(text: str):
    out = []
    cursor = 0
    for word in _tagger()(text):
        at = text.find(word.surface, cursor)
        if at < 0:
            return ()
        end = at + len(word.surface)
        out.append((word, at, end))
        cursor = end
    return tuple(out)


def _reader_gap_ok(tagged, event_index, event_end, scope_start):
    for index, (word, start, end) in enumerate(tagged):
        if index <= event_index or end <= event_end or start >= scope_start:
            continue
        if (word.feature.pos1 == "助動詞"
                or (word.feature.pos1 == "動詞" and word.feature.pos2 == "非自立可能")
                or (word.feature.pos1 == "助詞" and word.surface in ("て", "で", "は", "も"))):
            continue
        return False
    return True


def _scope(text: str, tagged, event_index: int):
    """Read one exact terminal scope; absence of a cue produces no polarity."""
    end = len(text.rstrip(_PUNCT))
    core = text[:end]
    event_start, event_end = tagged[event_index][1:]
    double = _DOUBLE.search(core)
    if double and double.end() == len(core):
        start, stop = double.span()
        if (start < event_start or (start >= event_end and text[event_end:start].strip())
                or not _reader_gap_ok(tagged, event_index, event_end, start)):
            return None
        observed = ((start, start + 2), (stop - 2, stop))
        return "double", (start, stop), observed
    single = _SINGLE.search(core)
    if single and single.end() == len(core):
        start, stop = single.span()
        if (start < event_start or (start >= event_end and text[event_end:start].strip())
                or not _reader_gap_ok(tagged, event_index, event_end, start)):
            return None
        return "negative", (start, stop), ((start, stop),)
    return None


def _copula_scope(text: str):
    end = len(text.rstrip(_PUNCT))
    match = _COPULA_NEGATIVE.search(text[:end])
    if not match or match.end() != end:
        return None
    if _BLOCKED.search(text):
        return None
    lhs, value, negative = match["entity"].strip(), match["value"].strip(), match["negative"]
    if not lhs or not value or "の" in lhs or "の" in value or not _nominal_value(value):
        return None
    entity_at = text.find(lhs, 0, match.start("value"))
    value_at = text.find(value, match.start("value"), match.start("negative"))
    if entity_at < 0 or value_at < 0:
        return None
    return lhs, value, negative, (entity_at, entity_at + len(lhs)), (value_at, value_at + len(value)), match.span("negative")


_CASE_PARTICLES = frozenset(("が", "を", "に", "で", "へ", "から", "より", "まで"))
_FORMAL_NOUNS = frozenset(("わけ", "こと", "もの", "はず", "ところ", "ため", "つもり"))


def _nominal_value(value: str) -> bool:
    """`AはBではない` denies an identity: B must be a noun phrase. A value such as <object>を<verb>ないわけ (a clause
    that ends in a formal noun, here inside ないわけではない) is a negated predicate, not an identity (reader side)."""
    tagged = _tagged(value)
    if not tagged:
        return False
    if any(word.feature.pos1 == "助詞" and word.surface in _CASE_PARTICLES for word, _, _ in tagged):
        return False
    content = [word for word, _, _ in tagged if word.feature.pos1 not in ("助詞", "助動詞", "補助記号", "記号")]
    if not content or content[-1].feature.pos1 in ("動詞", "形容詞"):
        return False
    last = tagged[-1][0]
    if last.surface in _FORMAL_NOUNS and len(tagged) > 1 and tagged[-2][0].feature.pos1 in ("動詞", "助動詞", "形容詞"):
        return False
    return True


def _role_spans(text, tagged, event_index, frame):
    words = [word for word, _, _ in tagged]
    starts = {start: (word, end) for word, start, end in tagged}
    roles = []
    for name in ("agent", "patient", "recipient"):
        value = getattr(frame, name)
        if not value:
            continue
        hits = set()
        cursor = 0
        while True:
            start = text.find(value, cursor)
            if start < 0:
                break
            end = start + len(value)
            following = starts.get(end)
            if (start < tagged[event_index][1] and start in starts and following
                    and following[0].feature.pos1 == "助詞"
                    and following[0].surface in _ROLE_PARTICLES[name]
                    and canonical(text[start:end]) == canonical(value)):
                hits.add((start, end, text[start:end]))
            cursor = start + 1
        if len(hits) != 1:
            return None
        start, end, phrase = next(iter(hits))
        roles.append(Role(name, canonical(phrase), _span("", start, end, text), "frame"))
    if len({(role.span.start, role.span.end) for role in roles}) != len(roles):
        return None
    return tuple(roles)


def _all_event_coverage(tagged, predicates, records, scope):
    covered = [(role.span.start, role.span.end)
               for record in records for role in record["roles"]]
    for index, predicate in predicates:
        start, end = tagged[index][1:]
        if (index and _base(tagged[index][0]) in ("する", "できる")
                and tagged[index - 1][0].feature.pos1 == "名詞"
                and tagged[index - 1][0].surface + _base(tagged[index][0]) == predicate):
            start = tagged[index - 1][1]
        covered.append((start, end))
    covered.append(scope)
    return all(word.feature.pos1 not in _CONTENT_POS
               or any(a <= start and end <= b for a, b in covered)
               for word, start, end in tagged)


def _event_reading(ctx: ConstructionContext, body_start: int, body: str):
    if (not body or _BLOCKED.search(body) or any(mark in body for mark in "「」『』:：")
            or body.rstrip().endswith(("?", "？"))):
        return None
    tagged = _tagged(body)
    if not tagged or len(tagged) > ctx.budget.max_tokens:
        return None
    words = [word for word, _, _ in tagged]
    predicates = _predicates(words)
    if not predicates:
        return None
    scoped = [(index, _scope(body, tagged, index)) for index, _ in predicates]
    scoped = [(index, scope) for index, scope in scoped if scope is not None]
    if len(scoped) != 1:
        return None
    event_index, (kind, (scope_start, scope_end), observed) = scoped[0]
    predicate = next(value for index, value in predicates if index == event_index)
    records = []
    previous = -1
    for index, lemma in predicates:
        prefix_end = index + 1
        if index == event_index:
            for later in range(index + 1, len(tagged)):
                if tagged[later][1] < scope_start:
                    prefix_end = later + 1
                else:
                    break
        frame = _read_prefix_frame(words[:prefix_end], index, lemma, previous)
        if (frame is None or frame.predicate != lemma or frame.ambiguous
                or (frame.recipient and lemma not in _RECIPIENT_PREDICATES)):
            return None
        roles = _role_spans(body, tagged, index, frame)
        if roles is None:
            return None
        if index == event_index:
            from ..semantic_reader import _case_roles
            lower = tagged[previous][2] if previous >= 0 else 0
            adjuncts, issues = _case_roles(body, tagged, index, lower=lower, existing=roles)
            if issues:
                return None
            extra_roles = tuple(Role(name, term, _span("", start, end, body), role_rule)
                                for name, term, (start, end), role_rule in adjuncts
                                if name != "ambiguous")
            if len(extra_roles) != len(adjuncts):
                return None
            roles = (*roles, *extra_roles)
        records.append({"index": index, "predicate": lemma, "frame": frame, "roles": roles})
        previous = index
    target = next(record for record in records if record["index"] == event_index)
    if not _all_event_coverage(tagged, predicates, records, (scope_start, scope_end)):
        return None
    sentence = ctx.sentence_span
    body_absolute = sentence.start + body_start
    predicate_start, predicate_end = tagged[event_index][1:]
    predicate_span = _context_span(ctx, body_absolute + predicate_start,
                                   body_absolute + predicate_end)
    roles = target["roles"]
    absolute_roles = tuple(Role(role.name, role.term,
                                _context_span(ctx, body_absolute + role.span.start,
                                              body_absolute + role.span.end), role.rule)
                           for role in roles)
    ident = hashlib.sha256(
        f"negation:{ctx.document_id}:{sentence.start}:{sentence.end}:{predicate_start}:{kind}".encode()
    ).hexdigest()[:24]
    clause = Clause(
        ident, Variable("event_" + ident, "event"), predicate, predicate_span,
        absolute_roles, sentence,
        _context_span(ctx, body_absolute, sentence.end),
        polarity="+" if kind == "double" else "-",
        modality=_AFFIRMATIVE_DOUBLE if kind == "double" else "assert",
        time="past" if body.rstrip(_PUNCT).endswith(("なかった", "ませんでした")) else "nonpast",
        rule="negation",
        sovereign=ctx.clauses[-1].sovereign if ctx.clauses else "document",
        family=ctx.clauses[-1].family if ctx.clauses else "document",
    )
    notes = tuple(TypedNote(
        "observed_negation", _context_span(ctx, body_absolute + start,
                                           body_absolute + end),
        "written negation in the event scope") for start, end in observed)
    if kind == "double":
        notes += (TypedNote(
            "affirmative_by_double_negation",
            _context_span(ctx, body_absolute + scope_start, body_absolute + scope_end),
            "two written negations explicitly license affirmative polarity"),)
    return clause, notes, sentence


def reads(ctx: ConstructionContext) -> Reading | None:
    if (len(ctx.tokens) > ctx.budget.max_tokens or len(ctx.clauses) >= ctx.budget.max_clauses
            or len(ctx.sentence_text) > 4096):
        return None
    body_start = _body_start(ctx.sentence_text)
    body = ctx.sentence_text[body_start:]
    event = _event_reading(ctx, body_start, body)
    if event is not None:
        clause, notes, consumed = event
        return Reading((clause,), (consumed,), notes)

    copula = _copula_scope(body)
    if not copula:
        return None
    entity, value, negative, (entity_start, entity_end), (value_start, value_end), cue = copula
    absolute = ctx.sentence_span.start + body_start
    sentence = ctx.sentence_span
    ident = hashlib.sha256(
        f"negation:{ctx.document_id}:{sentence.start}:{sentence.end}:copula".encode()
    ).hexdigest()[:24]
    roles = (
        Role("entity", entity, _context_span(ctx, absolute + entity_start,
                                              absolute + entity_end)),
        Role("value", value, _context_span(ctx, absolute + value_start,
                                            absolute + value_end)),
    )
    predicate_span = roles[1].span
    past = negative in ("ではありませんでした", "じゃありませんでした", "ではなかった", "でなかった", "じゃなかった")
    clause = Clause(
        ident, Variable("event_" + ident, "event"), "identity", predicate_span,
        roles, sentence, _context_span(ctx, absolute, sentence.end),
        polarity="-", modality="assert", time="past" if past else "nonpast",
        rule="negation", sovereign=ctx.clauses[-1].sovereign if ctx.clauses else "document",
        family=ctx.clauses[-1].family if ctx.clauses else "document",
    )
    note = TypedNote("observed_negation",
                     _context_span(ctx, absolute + cue[0], absolute + cue[1]),
                     "written negative copula")
    return Reading((clause,), (sentence,), (note,))


def _license_tokens(text):
    result = []
    cursor = 0
    for token in _tagger()(text):
        start = text.find(token.surface, cursor)
        if start < 0:
            return ()
        end = start + len(token.surface)
        result.append((token, start, end))
        cursor = end
    return tuple(result)


def _license_gap_ok(body, tagged, event_index, event_end, scope_start):
    for index in range(event_index + 1, len(tagged)):
        word, start, end = tagged[index]
        if end <= event_end or start >= scope_start:
            continue
        if (word.feature.pos1 == "助動詞"
                or (word.feature.pos1 == "動詞" and word.feature.pos2 == "非自立可能")
                or (word.feature.pos1 == "助詞" and word.surface in ("て", "で", "は", "も"))):
            continue
        return False
    return not body[event_end:scope_start].strip() or scope_start < event_end


def _licensed_scope(body, tagged, event_index, event_start, event_end):
    end = len(body)
    while end and body[end - 1] in _PUNCT:
        end -= 1
    doubles = ("なくはない", "なくもない", "ないわけではない", "ないわけじゃない",
               "ないことはない", "ないこともない")
    singles = ("ませんでした", "なかった", "ません", "ない", "ず", "ぬ")
    double = next((form for form in doubles if body[:end].endswith(form)), None)
    if double:
        start = end - len(double)
        if (start < event_start or (start >= event_end and body[event_end:start].strip())
                or not _license_gap_ok(body, tagged, event_index, event_end, start)):
            return None
        return "double", (start, end), ((start, start + 2), (end - 2, end))
    single = next((form for form in singles if body[:end].endswith(form)), None)
    if single:
        start = end - len(single)
        if (start < event_start or (start >= event_end and body[event_end:start].strip())
                or not _license_gap_ok(body, tagged, event_index, event_end, start)):
            return None
        return "negative", (start, end), ((start, end),)
    return None


def _role_surface_licensed(body, tagged, role, body_start, event_start):
    start, end = role.span.start - body_start, role.span.end - body_start
    if not (0 <= start < end <= len(body)) or body[start:end] != role.span.text:
        return False
    allowed = _ROLE_PARTICLES.get(role.name, frozenset())
    token_at = {left: token for token, left, _ in tagged}
    candidates = []
    for at in range(len(body) - len(role.span.text) + 1):
        if not body.startswith(role.span.text, at):
            continue
        finish = at + len(role.span.text)
        next_token = token_at.get(finish)
        if (at < event_start and next_token is not None and next_token.feature.pos1 == "助詞"
                and next_token.surface in allowed):
            candidates.append((at, finish))
    return candidates == [(start, end)]


def _frame_role_positions(body, tagged, frame, event_start):
    token_at = {left: token for token, left, _ in tagged}
    found = []
    for name in ("agent", "patient", "recipient"):
        value = getattr(frame, name)
        if not value:
            continue
        hits = set()
        cursor = 0
        while True:
            start = body.find(value, cursor)
            if start < 0:
                break
            end = start + len(value)
            next_token = token_at.get(end)
            if (start in token_at and start < event_start and next_token is not None
                    and next_token.feature.pos1 == "助詞"
                    and next_token.surface in _ROLE_PARTICLES[name]):
                hits.add((start, end))
            cursor = start + 1
        if len(hits) != 1:
            return None
        start, end = next(iter(hits))
        found.append((name, canonical(value), start, end))
    if len({(start, end) for _, _, start, end in found}) != len(found):
        return None
    return tuple(found)


def _particle_after(body, tagged, end, choices):
    token_at = {left: token for token, left, _ in tagged}
    for choice in sorted(choices, key=len, reverse=True):
        cursor = end
        pieces = ""
        while cursor in token_at and len(pieces) < len(choice):
            token = token_at[cursor]
            if token.feature.pos1 != "助詞":
                break
            pieces += token.surface
            cursor += len(token.surface)
            if pieces == choice:
                return choice
            if not choice.startswith(pieces):
                break
    return None


def _extra_role_licensed(body, tagged, role, clause, predicate):
    start, end = role.span.start - clause.body_span.start, role.span.end - clause.body_span.start
    if (role.rule not in ("case", "adverbial") or not (0 <= start < end <= len(body))
            or body[start:end] != role.span.text or role.term != role.span.text):
        return False
    if role.rule == "adverbial":
        return role.name == "time" and bool(_TIME.fullmatch(role.term)) and body[end:end + 1] in ("、", ",")
    compound = _COMPOUND_ROLES.get(role.name)
    if compound:
        return _particle_after(body, tagged, end, compound) is not None
    particle = _particle_after(body, tagged, end, ("に", "で", "から", "まで", "へ", "と"))
    compact = role.term.replace(" ", "").replace("　", "")
    if role.name == "time":
        return bool(_TIME.fullmatch(compact)) and particle == "に" or compact == "同日付" and particle == "で"
    if role.name == "goal":
        return predicate in _GOAL_PREDICATES and particle == "に"
    if role.name == "location":
        return predicate in _LOCATION_PREDICATES and particle == "に"
    if role.name in ("source", "origin"):
        return particle == "から" and not _TIME.fullmatch(compact)
    if role.name in ("limit", "direction"):
        return particle == ("まで" if role.name == "limit" else "へ")
    if role.name in ("place", "means"):
        head = compact.split("の")[-1]
        allowed = _PLACES if role.name == "place" else _MEANS
        return particle == "で" and (head in allowed or role.name == "place" and
                                      any(head.endswith(x) for x in ("学校", "駅", "公園", "会社", "図書館", "病院", "市", "町", "県", "国", "室"))
                                      or role.name == "means" and head.endswith("語"))
    if role.name == "companion":
        role_tokens = [word for word, left, right in tagged if start <= left and right <= end]
        person = role.term.endswith(("さん", "氏")) or any(
            getattr(word.feature, "pos3", "") == "人名" for word in role_tokens)
        return particle == "と" and person
    return False


def _license_coverage(body, tagged, clause, predicates, records, scope):
    covered = [(start, end) for record in records
               for _, _, start, end in record["roles"]]
    for index, predicate in predicates:
        start, end = tagged[index][1:]
        if (index and _base(tagged[index][0]) in ("する", "できる")
                and tagged[index - 1][0].feature.pos1 == "名詞"
                and tagged[index - 1][0].surface + _base(tagged[index][0]) == predicate):
            start = tagged[index - 1][1]
        covered.append((start, end))
    covered.extend((role.span.start - clause.body_span.start,
                    role.span.end - clause.body_span.start)
                   for role in clause.roles if role.name not in ("agent", "patient", "recipient"))
    covered.append(scope)
    for token, start, end in tagged:
        if token.feature.pos1 in _CONTENT_POS and not any(a <= start and end <= b for a, b in covered):
            return False
    return True


def _licenses_event(clause, source):
    if (clause.span.end > len(source) or source[clause.span.start:clause.span.end] != clause.span.text
            or clause.body_span is None or clause.body_span.source != clause.span.source
            or clause.body_span.end != clause.span.end):
        return False
    full = clause.span.text
    left = _body_start(full)
    if clause.body_span.start != clause.span.start + left:
        return False
    body = source[clause.body_span.start:clause.body_span.end]
    if (not body or _BLOCKED.search(body) or any(mark in body for mark in "「」『』:：")
            or body.rstrip().endswith(("?", "？"))):
        return False
    tagged = _license_tokens(body)
    if not tagged:
        return False
    words = [word for word, _, _ in tagged]
    predicates = _predicates(words)
    if not predicates:
        return False
    scopes = [(index, _licensed_scope(body, tagged, index, tagged[index][1], tagged[index][2]))
              for index, _ in predicates]
    scopes = [(index, scope) for index, scope in scopes if scope is not None]
    if len(scopes) != 1:
        return False
    event_index, (kind, (scope_start, scope_end), _observed) = scopes[0]
    predicate = next(value for index, value in predicates if index == event_index)
    event_start, event_end = tagged[event_index][1:]
    records = []
    previous = -1
    for index, lemma in predicates:
        prefix_end = index + 1
        if index == event_index:
            for later in range(index + 1, len(tagged)):
                if tagged[later][1] < scope_start:
                    prefix_end = later + 1
                else:
                    break
        frame = _read_prefix_frame(words[:prefix_end], index, lemma, previous)
        if (frame is None or frame.predicate != lemma or frame.ambiguous
                or (frame.recipient and lemma not in _RECIPIENT_PREDICATES)):
            return False
        role_positions = _frame_role_positions(body, tagged, frame, tagged[index][1])
        if role_positions is None:
            return False
        records.append({"index": index, "predicate": lemma, "frame": frame,
                        "roles": role_positions})
        previous = index
    target = next(record for record in records if record["index"] == event_index)
    expected_modality = _AFFIRMATIVE_DOUBLE if kind == "double" else "assert"
    expected_polarity = "+" if kind == "double" else "-"
    if (clause.predicate != predicate or clause.predicate_span.text != body[event_start:event_end]
            or clause.predicate_span.start != clause.body_span.start + event_start
            or (clause.polarity, clause.modality, clause.time) != (
                expected_polarity, expected_modality,
                "past" if body.rstrip(_PUNCT).endswith(("なかった", "ませんでした")) else "nonpast")
            or clause.conditions or clause.exceptions or clause.condition_spans or clause.exception_spans):
        return False
    actual = {role.name: role for role in clause.roles}
    expected = {name: (value, start, end) for name, value, start, end in target["roles"]}
    core_names = {name for name in actual if name in ("agent", "patient", "recipient")}
    if core_names != set(expected):
        return False
    for name in core_names:
        role = actual[name]
        value, start, end = expected[name]
        if (role.rule != "frame" or role.term != value
                or canonical(role.span.text) != value
                or (role.span.start - clause.body_span.start,
                    role.span.end - clause.body_span.start) != (start, end)
                or not _role_surface_licensed(body, tagged, role,
                                              clause.body_span.start, event_start)):
            return False
    for name, role in actual.items():
        if name not in core_names and not _extra_role_licensed(body, tagged, role, clause, predicate):
            return False
    if not _license_coverage(body, tagged, clause, predicates, records,
                             (scope_start, scope_end)):
        return False
    return True


def _licenses_copula(clause, source):
    if (clause.body_span is None or clause.span.end > len(source)
            or source[clause.span.start:clause.span.end] != clause.span.text):
        return False
    full = clause.span.text
    left = _body_start(full)
    if clause.body_span.start != clause.span.start + left or clause.body_span.end != clause.span.end:
        return False
    body = source[clause.body_span.start:clause.body_span.end]
    terminal = len(body.rstrip(" \t\r\n。！？!?"))
    core = body[:terminal]
    forms = ("ではありませんでした", "じゃありませんでした", "ではなかった", "でなかった",
             "じゃなかった", "ではありません", "じゃありません", "ではない", "でない", "じゃない")
    negative = next((form for form in forms if core.endswith(form)), None)
    if not negative:
        return False
    prefix = core[:-len(negative)]
    tagged_prefix = _license_tokens(prefix)
    separators = [(word, start, end) for word, start, end in tagged_prefix
                  if word.feature.pos1 == "助詞" and word.surface in ("は", "が")]
    if len(separators) != 1:
        return False
    _particle, split_start, split_end = separators[0]
    entity_left = len(prefix[:split_start]) - len(prefix[:split_start].lstrip())
    entity_right = len(prefix[:split_start].rstrip())
    value_left = split_end + len(prefix[split_end:]) - len(prefix[split_end:].lstrip())
    value_right = len(prefix[:len(prefix.rstrip())])
    entity, value = prefix[entity_left:entity_right], prefix[value_left:value_right]
    if not entity or not value or "の" in entity or "の" in value or _BLOCKED.search(body):
        return False
    # Licensor's own noun-phrase test on the value (independent of the reader's helper): no case particle token, no
    # adjective/verb as the last content word, no formal noun hanging off a verb/auxiliary.
    value_tokens = _license_tokens(value)
    if not value_tokens:
        return False
    if any(w.feature.pos1 == "助詞" and w.surface in ("が", "を", "に", "で", "へ", "から", "より", "まで")
           for w, _, _ in value_tokens):
        return False
    heads = [w for w, _, _ in value_tokens if w.feature.pos1 not in ("助詞", "助動詞", "補助記号", "記号")]
    if not heads or heads[-1].feature.pos1 in ("動詞", "形容詞"):
        return False
    if (len(value_tokens) > 1 and value_tokens[-1][0].surface in ("わけ", "こと", "もの", "はず", "ところ", "ため", "つもり")
            and value_tokens[-2][0].feature.pos1 in ("動詞", "助動詞", "形容詞")):
        return False
    parsed = (entity, value, negative,
              (entity_left, entity_right), (value_left, value_right),
              (len(prefix), len(prefix) + len(negative)))
    if not parsed:
        return False
    entity, value, negative, entity_span, value_span, cue = parsed
    entity_role = next((role for role in clause.roles if role.name == "entity"), None)
    value_role = next((role for role in clause.roles if role.name == "value"), None)
    if (len(clause.roles) != 2 or not entity_role or not value_role
            or (entity_role.term, entity_role.span.text,
                entity_role.span.start - clause.body_span.start,
                entity_role.span.end - clause.body_span.start) != (entity, entity, *entity_span)
            or (value_role.term, value_role.span.text,
                value_role.span.start - clause.body_span.start,
                value_role.span.end - clause.body_span.start) != (value, value, *value_span)
            or clause.predicate != "identity" or clause.predicate_span != value_role.span
            or (clause.polarity, clause.modality, clause.time) != (
                "-", "assert", "past" if negative in (
                    "ではありませんでした", "じゃありませんでした", "ではなかった", "でなかった", "じゃなかった") else "nonpast")
            or clause.conditions or clause.exceptions):
        return False
    tagged = _license_tokens(body)
    return bool(tagged) and all(
        word.feature.pos1 not in _CONTENT_POS
        or any(role.span.start - clause.body_span.start <= start
               and end <= role.span.end - clause.body_span.start for role in clause.roles)
        for word, start, end in tagged
    ) and cue[0] < cue[1]


def licenses(clause: Clause, source: str) -> bool:
    """Reparse the original source and verify cue, role, scope, tense and coverage."""
    if clause.rule != "negation" or clause.unsupported:
        return False
    if clause.predicate == "identity":
        return _licenses_copula(clause, source)
    return _licenses_event(clause, source)


register(Construction("negation", 40, reads, licenses))
