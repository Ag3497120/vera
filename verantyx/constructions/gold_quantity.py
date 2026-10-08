"""Recover one source-bounded count phrase from an otherwise refused clause."""
from __future__ import annotations

import re
from dataclasses import replace
from hashlib import sha256

from verantyx.constructions import Construction, ConstructionContext, Reading, register
from verantyx.semantic_ir import Clause, Role, Span, Variable


_NAME = "gold_quantity"
_NUMERAL = re.compile(r"[0-9０-９〇零一二三四五六七八九十百千万億兆]+\Z")
_COUNTERS = frozenset((
    "人", "個", "つ", "本", "枚", "冊", "匹", "頭", "台", "件", "回", "階",
    "歳", "才", "円", "軒", "足", "着", "杯", "組", "名", "点", "校", "社",
    "隻", "羽", "株", "玉", "束", "箱", "袋", "粒", "房", "列", "基", "棟",
    "通", "首", "切", "脚", "面", "柱", "条", "口", "票", "局", "曲", "種",
))
_CASE_GAPS = frozenset(("を", "が", "は", "に", "で", "と", "へ", "から", "も"))
_GAP_CHARS = frozenset(" \t\r\n　、。！？「」『』（）［］【】・がはをにでとへものからまでよりてもたるうだですますっ")
_ROLE_PARTICLES = {
    "agent": frozenset(("が", "は", "も", "から", "に")),
    "patient": frozenset(("を", "が", "は", "も")),
    "recipient": frozenset(("に", "へ", "と")),
    "source": frozenset(("から", "より")),
    "place": frozenset(("で", "に", "へ")),
    "instrument": frozenset(("で", "に")),
    "time": frozenset(("に", "で")),
    "experiencer": frozenset(("が", "は", "に", "を")),
    "theme": frozenset(("が", "は", "を", "に")),
    "goal": frozenset(("に", "へ", "まで")),
    "beneficiary": frozenset(("に", "へ", "のために")),
    "location": frozenset(("で", "に", "へ")),
    "path": frozenset(("を", "から", "へ", "まで")),
}


def _token_surface(token) -> str:
    return str(getattr(token, "surface", ""))


def _counter_spans(ctx: ConstructionContext) -> tuple[tuple[int, int, str], ...] | None:
    """Read exact numeral + classifier pairs from the supplied tagged tokens."""
    tokens = ctx.tokens
    if len(tokens) > min(ctx.budget.max_tokens, 256):
        return None
    found: list[tuple[int, int, str]] = []
    for i in range(len(tokens) - 1):
        number, counter = tokens[i], tokens[i + 1]
        number_feature = getattr(number.token, "feature", None)
        counter_feature = getattr(counter.token, "feature", None)
        number_text = _token_surface(number.token)
        counter_text = _token_surface(counter.token)
        if (getattr(number_feature, "pos2", "") != "数詞"
                or getattr(counter_feature, "pos3", "") != "助数詞"
                or counter_text not in _COUNTERS
                or number.end != counter.start
                or not _NUMERAL.fullmatch(number_text)):
            continue
        start = ctx.sentence_span.start + number.start
        end = ctx.sentence_span.start + counter.end
        text = ctx.sentence_text[number.start:counter.end]
        if text != number_text + counter_text:
            continue
        found.append((start, end, text))
    return tuple(found)


def _source_slice(sentence: str, sentence_start: int, start: int, end: int) -> str:
    return sentence[start - sentence_start:end - sentence_start]


def _valid_offsets(span: Span, source_id: str, sentence_start: int, sentence_end: int,
                   sentence: str) -> bool:
    return (span.source == source_id and sentence_start <= span.start <= span.end <= sentence_end
            and _source_slice(sentence, sentence_start, span.start, span.end) == span.text)


def _covered_gaps_ok(sentence: str, sentence_start: int, clause: Clause,
                     roles: tuple[Role, ...]) -> bool:
    spans = [(clause.predicate_span.start, clause.predicate_span.end)]
    spans.extend((role.span.start, role.span.end) for role in roles)
    spans.sort()
    cursor = clause.span.start
    for start, end in spans:
        if start < cursor or start < clause.span.start or end > clause.span.end:
            return False
        gap = _source_slice(sentence, sentence_start, cursor, start)
        if any(char not in _GAP_CHARS for char in gap):
            return False
        cursor = end
    tail = _source_slice(sentence, sentence_start, cursor, clause.span.end)
    return all(char in _GAP_CHARS for char in tail)


def reads(ctx: ConstructionContext) -> Reading | None:
    if (len(ctx.sentence_text) > 4096 or len(ctx.clauses) != 1
            or len(ctx.clauses) > min(ctx.budget.max_clauses, 128)):
        return None
    clause = ctx.clauses[0]
    if len(ctx.tokens) + len(clause.roles) > min(ctx.budget.max_steps, 4096):
        return None
    if (clause.unsupported != ("unrepresented source content",)
            or clause.conditions or clause.exceptions
            or not _valid_offsets(clause.span, ctx.sentence_span.source,
                                  ctx.sentence_span.start, ctx.sentence_span.end,
                                  ctx.sentence_text)
            or not _valid_offsets(clause.predicate_span, ctx.sentence_span.source,
                                  ctx.sentence_span.start, ctx.sentence_span.end,
                                  ctx.sentence_text)):
        return None
    quantities = _counter_spans(ctx)
    if quantities is None or len(quantities) != 1:
        return None
    q_start, q_end, q_text = quantities[0]
    if not (clause.span.start <= q_start < q_end <= clause.predicate_span.start):
        return None

    roles = list(clause.roles)
    for i, role in enumerate(roles):
        if (role.name not in _ROLE_PARTICLES or not isinstance(role.term, str)
                or not _valid_offsets(role.span, ctx.sentence_span.source,
                                      ctx.sentence_span.start, ctx.sentence_span.end,
                                      ctx.sentence_text)):
            return None
        after = _source_slice(ctx.sentence_text, ctx.sentence_span.start,
                              role.span.end, min(clause.span.end, role.span.end + 8))
        if not any(after.startswith(particle) for particle in _ROLE_PARTICLES[role.name]):
            return None
        roles[i] = replace(role, term=role.span.text, rule=_NAME)
    q_inside = [i for i, role in enumerate(roles)
                if role.span.source == clause.span.source
                and role.span.start <= q_start and q_end <= role.span.end]
    if len(q_inside) == 1:
        index = q_inside[0]
        role = roles[index]
        roles[index] = replace(role, term=role.span.text, rule=_NAME)
    elif q_inside:
        return None
    else:
        expanded: list[tuple[int, int, int, int, str]] = []
        for i, role in enumerate(roles):
            if role.span.source != clause.span.source:
                continue
            if q_end <= role.span.start and _source_slice(
                    ctx.sentence_text, ctx.sentence_span.start, q_end, role.span.start) == "の":
                expanded.append((i, q_start, role.span.end, role.span.start, "prefix"))
            elif role.span.end <= q_start and role.span.end == q_start:
                expanded.append((i, role.span.start, q_end, role.span.end, "suffix"))
        if len(expanded) == 1:
            index, start, end, _, _ = expanded[0]
            role = roles[index]
            text = _source_slice(ctx.sentence_text, ctx.sentence_span.start, start, end)
            roles[index] = replace(role, term=text,
                                   span=Span(role.span.source, start, end, text), rule=_NAME)
        elif expanded:
            return None
        else:
            tail = _source_slice(ctx.sentence_text, ctx.sentence_span.start,
                                 q_end, clause.predicate_span.start)
            # A comma can detach a postposed count from the role it appears to follow.
            if (any(role.name == "recipient" for role in roles)
                    and any(char in "、。！？" for char in tail)):
                return None
            preceding = [role for role in roles if role.span.source == clause.span.source
                         and role.span.end <= q_start
                         and _source_slice(ctx.sentence_text, ctx.sentence_span.start,
                                           role.span.end, q_start) in _CASE_GAPS]
            if len(preceding) != 1:
                return None
            roles.append(Role("quantity", q_text,
                              Span(clause.span.source, q_start, q_end, q_text), _NAME))

    final_roles = tuple(roles)
    if not _covered_gaps_ok(ctx.sentence_text, ctx.sentence_span.start, clause, final_roles):
        return None
    if len(final_roles) > min(ctx.budget.max_steps, 4096):
        return None
    ident = sha256((clause.id + "\0" + _NAME + f"\0{q_start}:{q_end}").encode("utf-8")).hexdigest()[:24]
    recovered = replace(clause, id=ident,
                         event=Variable("event_" + ident, "event"),
                         roles=final_roles, rule=_NAME, unsupported=())
    return Reading((recovered,), (clause.span,))


_LICENSED_QUANTITY = re.compile(
    r"[0-9０-９〇零一二三四五六七八九十百千万億兆]+"
    r"(?:人|個|つ|本|枚|冊|匹|頭|台|件|回|階|歳|才|円|軒|足|着|杯|組|名|点|校|社|隻|羽|株|玉|束|箱|袋|粒|房|列|基|棟|通|首|切|脚|面|柱|条|口|票|局|曲|種)"
)


def licenses(clause, source: str) -> bool:
    """Independently verify the count phrase, argument span, and clause scope."""
    if (clause.rule != _NAME or clause.unsupported or clause.polarity != "+"
            or clause.modality != "assert" or clause.time != "past"
            or clause.conditions or clause.condition_spans
            or clause.exceptions or clause.exception_spans or clause.exception_of
            or not isinstance(source, str) or len(source) > 1_000_000):
        return False
    lo, hi = clause.span.start, clause.span.end
    if (lo < 0 or hi <= lo or hi > len(source) or source[lo:hi] != clause.span.text
            or clause.predicate_span.source != clause.span.source
            or not (lo <= clause.predicate_span.start < clause.predicate_span.end <= hi)
            or source[clause.predicate_span.start:clause.predicate_span.end]
            != clause.predicate_span.text):
        return False
    raw = source[lo:hi]
    predicate_tail = raw[clause.predicate_span.end - lo:]
    if not re.search(r"た[。！？」』）]*\Z", predicate_tail):
        return False
    licensed = list(_LICENSED_QUANTITY.finditer(raw))
    if len(licensed) != 1:
        return False
    q_start = lo + licensed[0].start()
    q_end = lo + licensed[0].end()
    q_text = source[q_start:q_end]
    if q_end > clause.predicate_span.start:
        return False

    all_roles = clause.roles
    if not all_roles:
        return False
    for role in all_roles:
        if (role.span.source != clause.span.source or role.span.start < lo
                or role.span.end > hi or role.span.end <= role.span.start
                or source[role.span.start:role.span.end] != role.span.text
                or not isinstance(role.term, str)):
            return False
        if role.rule == _NAME:
            if role.term != role.span.text:
                return False
        elif role.name != "quantity" and role.rule not in ("frame", "case", "quantifier", "measure"):
            return False
        if role.name != "quantity":
            if role.name not in _ROLE_PARTICLES:
                return False
            after = source[role.span.end:min(hi, role.span.end + 8)]
            if not any(after.startswith(particle) for particle in _ROLE_PARTICLES[role.name]):
                return False

    quantity_roles = [role for role in all_roles if role.name == "quantity"]
    if quantity_roles:
        if (len(quantity_roles) != 1 or quantity_roles[0].rule != _NAME
                or quantity_roles[0].span.start != q_start or quantity_roles[0].span.end != q_end
                or quantity_roles[0].term != q_text):
            return False
        tail = source[q_end:clause.predicate_span.start]
        if (any(role.name == "recipient" for role in all_roles)
                and any(char in "、。！？" for char in tail)):
            return False
        antecedents = [role for role in all_roles if role.name != "quantity"
                       and role.span.end <= q_start
                       and source[role.span.end:q_start] in _CASE_GAPS]
        if len(antecedents) != 1:
            return False
    else:
        carried = [role for role in all_roles if role.rule == _NAME
                   and role.span.start <= q_start and q_end <= role.span.end
                   and role.term == role.span.text]
        if len(carried) != 1:
            return False

    spans = [(clause.predicate_span.start, clause.predicate_span.end)]
    spans.extend((role.span.start, role.span.end) for role in all_roles)
    spans.sort()
    cursor = lo
    for start, end in spans:
        if start < cursor or end > hi:
            return False
        if any(char not in _GAP_CHARS for char in source[cursor:start]):
            return False
        cursor = end
    return all(char in _GAP_CHARS for char in source[cursor:hi])


register(Construction(_NAME, 75, reads, licenses, refines=("frame",)))
