"""Source-bounded links between two independently read clauses."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from fugashi import Tagger

from ..semantic_ir import Clause, Role, Span, Variable
from . import Construction, ConstructionContext, Reading, TypedNote, register


_RELATION_ROLES = {
    "cause": ("cause", "effect"),
    "condition_relation": ("antecedent", "consequent"),
    "contrast": ("left", "right"),
    "addition": ("prior", "added"),
}
_AUX_NEGATIVE = frozenset(("ない", "ぬ", "ん", "まい"))
_AUX_NONASSERTIVE = frozenset(("う", "よう", "だろう", "でしょう", "らしい"))


@dataclass(frozen=True)
class _Link:
    kind: str
    start: int
    end: int
    left: tuple[int, int]
    right: tuple[int, int]
    prefix: bool = False


def _text(token) -> str:
    return token.token.surface


def _feature(token):
    return token.token.feature


def _at(tokens, start: int, end: int):
    return tuple(t for t in tokens if t.start < end and start < t.end)


def _is_connective_token(form: str, tokens, start: int, end: int) -> bool:
    ts = _at(tokens, start, end)
    if not ts or ts[0].start != start or ts[-1].end != end:
        return False
    if "".join(_text(t) for t in ts) != form:
        return False
    if form in ("しかし", "また", "さらに"):
        return len(ts) == 1 and _feature(ts[0]).pos1 in ("副詞", "接続詞")
    if form in ("が", "から", "ば", "けれども"):
        return any(_feature(t).pos2 == "接続助詞" for t in ts)
    if form == "ので":
        return len(ts) >= 2 and _feature(ts[0]).pos1 == "助詞" and any(
            _feature(t).pos1 == "助動詞" for t in ts[1:])
    if form == "ため":
        return any(_feature(t).pos1 == "名詞" for t in ts)
    if form == "ために":
        return (len(ts) >= 2 and _feature(ts[0]).pos1 == "名詞"
                and _text(ts[0]) == "ため" and _text(ts[-1]) == "に"
                and _feature(ts[-1]).pos1 == "助詞")
    if form == "場合":
        return any(_feature(t).pos1 == "名詞" for t in ts)
    if form in ("なら", "たら"):
        return any(_feature(t).pos1 in ("助詞", "助動詞") for t in ts)
    if form == "ても":
        return len(ts) >= 2 and _feature(ts[-1]).pos1 == "助詞"
    return False


def _after_comma(text: str, position: int) -> int:
    while position < len(text) and text[position] in "、 \t\r\n":
        position += 1
    return position


def _trim_boundary(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start] in "、 \t\r\n":
        start += 1
    while end > start and text[end - 1] in "、 \t\r\n":
        end -= 1
    return start, end


def _reader_inside_parenthesis(text: str, position: int) -> bool:
    depth = 0
    for char in text[:position]:
        if char in "（(":
            depth += 1
        elif char in "）)":
            depth = max(0, depth - 1)
    return depth > 0


def _reader_operand_has_clause(ctx: ConstructionContext, bounds: tuple[int, int],
                               allow_te: bool = False) -> bool:
    start, end = bounds
    selected = [t for t in ctx.tokens if t.start < end and start < t.end]
    if not selected or selected[0].start < start or selected[-1].end > end:
        return False
    if any(ch in ctx.sentence_text[start:end]
           for ch in "、「」『』【】[]\"'“”:："):
        return False
    heads = []
    for index, token in enumerate(selected):
        feature = _feature(token)
        lemma = feature.lemma or feature.orthBase or _text(token)
        if lemma in _AUX_NONASSERTIVE:
            return False
        if lemma in _AUX_NEGATIVE:
            return False
        previous = selected[index - 1] if index else None
        following = selected[index + 1] if index + 1 < len(selected) else None
        if feature.pos1 not in ("動詞", "形容詞"):
            continue
        if (allow_te and lemma in ("付く", "つく") and previous
                and _text(previous) == "に"):
            continue
        if (feature.cForm.startswith("連体形") and following
                and _feature(following).pos1 == "名詞"):
            continue
        if (lemma in ("因る", "依る") and previous and _text(previous) == "に"):
            continue
        if (lemma in ("居る", "いる") and previous
                and _text(previous) in ("て", "で") and feature.pos2 == "非自立可能"):
            continue
        independent = feature.pos2 != "非自立可能"
        lexical_suru = (lemma in ("為る", "する") and previous is not None
                        and _feature(previous).pos1 == "名詞")
        lexical_copula = lemma in ("有る", "成る")
        te_chain = following is not None and _text(following) in ("て", "で")
        if independent or lexical_suru or lexical_copula or te_chain:
            heads.append(token)
    if len(heads) != 1:
        return False
    tail = list(selected)
    while tail and _feature(tail[-1]).pos1 == "補助記号":
        tail.pop()
    if not tail:
        return False
    terminal = _feature(tail[-1])
    closed = terminal.cForm.startswith(("終止形", "連体形"))
    te_form = (allow_te and terminal.cForm.startswith("連用形")
               and heads[-1] is tail[-1])
    return closed or te_form


def _reader_has_condition(ctx: ConstructionContext) -> bool:
    """Do not emit an unguarded relation over a source with a guard cue."""
    forms = ("場合", "たら", "なら", "ば")
    text = ctx.sentence_text
    for form in forms:
        at = text.find(form)
        while at >= 0:
            if _is_connective_token(form, ctx.tokens, at, at + len(form)):
                return True
            at = text.find(form, at + 1)
    base = ctx.sentence_span.start
    current = ctx.clauses[-ctx.budget.max_clauses:]
    return any(c.span.source == ctx.sentence_span.source
               and c.span.start == base and (c.conditions or c.condition_spans)
               for c in current)


def _reader_scope_start(ctx: ConstructionContext, marker_start: int) -> int:
    text = ctx.sentence_text
    forms = ("けれども", "しかし", "さらに", "また", "けれど", "が")
    starts = []
    for form in forms:
        at = text.find(form)
        while 0 <= at < marker_start:
            stop = at + len(form)
            if _is_connective_token(form, ctx.tokens, at, stop):
                comma = stop
                while comma < marker_start and text[comma] in " \t":
                    comma += 1
                if comma < marker_start and text[comma] == "、":
                    starts.append(_after_comma(text, comma + 1))
            at = text.find(form, at + 1)
    return max(starts, default=0)


def _reader_past_tail(ctx: ConstructionContext, bounds: tuple[int, int]) -> bool:
    selected = [t for t in ctx.tokens if bounds[0] <= t.start and t.end <= bounds[1]]
    tail = next((t for t in reversed(selected) if _feature(t).pos1 != "補助記号"), None)
    return bool(tail and (_feature(tail).lemma == "た"
                          or _feature(tail).cType == "助動詞-タ"))


def _reader_next_boundary(ctx: ConstructionContext, marker_end: int) -> int:
    text = ctx.sentence_text
    forms = ("けれども", "しかし", "さらに", "ので", "ために", "ため", "から", "たら",
             "なら", "場合", "ても", "けれど", "また", "ば", "が")
    boundaries = []
    for form in forms:
        at = text.find(form, marker_end)
        while at >= 0:
            stop = at + len(form)
            if (_reader_inside_parenthesis(text, at)
                    or not _is_connective_token(form, ctx.tokens, at, stop)):
                at = text.find(form, at + 1)
                continue
            if ((form == "ため" and text[stop:stop + 1] in ("に", "の"))
                    or (form == "ても" and text[max(0, at - 2):at] == "として")):
                at = text.find(form, at + 1)
                continue
            if form in ("しかし", "また", "さらに"):
                comma = at - 1
                while comma >= 0 and text[comma] in " \t":
                    comma -= 1
                if comma < 0 or text[comma] != "、":
                    at = text.find(form, at + 1)
                    continue
                left = _trim_boundary(text, _reader_scope_start(ctx, at), comma)
            else:
                left = _trim_boundary(text, _reader_scope_start(ctx, at), at)
            if form == "ために" and not _reader_past_tail(ctx, left):
                at = text.find(form, at + 1)
                continue
            if _reader_operand_has_clause(ctx, left, form == "ても"):
                boundaries.append(left[1])
            at = text.find(form, at + 1)
    return min(boundaries, default=len(text))


def _reader_links(ctx: ConstructionContext) -> tuple[_Link, ...]:
    text = ctx.sentence_text
    forms = (("けれども", "contrast"), ("しかし", "contrast"), ("さらに", "addition"),
             ("ので", "cause"), ("ために", "cause"), ("ため", "cause"), ("から", "cause"),
             ("たら", "condition"), ("なら", "condition"), ("場合", "condition"),
             ("ても", "contrast"), ("けれど", "contrast"), ("また", "addition"),
             ("ば", "condition"), ("が", "contrast"))
    found = []
    for form, kind in forms:
        pos = text.find(form)
        while pos >= 0:
            end = pos + len(form)
            if _is_connective_token(form, ctx.tokens, pos, end):
                if _reader_inside_parenthesis(text, pos):
                    pos = text.find(form, pos + 1)
                    continue
                prefix = form in ("しかし", "また", "さらに")
                if form == "ため" and text[end:end + 1] in ("に", "の"):
                    pos = text.find(form, pos + 1)
                    continue
                if form == "ても" and text[max(0, pos - 2):pos] == "として":
                    pos = text.find(form, pos + 1)
                    continue
                if prefix:
                    comma = pos - 1
                    while comma >= 0 and text[comma] in " \t":
                        comma -= 1
                    if comma >= 0 and text[comma] == "、":
                        le = _trim_boundary(text, 0, comma)[1]
                        rs = _after_comma(text, end)
                        left = (0, le)
                        right_end = _reader_next_boundary(ctx, end)
                        right = _trim_boundary(text, rs, right_end)
                        if (_reader_operand_has_clause(ctx, left)
                                and _reader_operand_has_clause(ctx, right)):
                            found.append(_Link(kind, pos, end, left, right, True))
                else:
                    left = _trim_boundary(text, _reader_scope_start(ctx, pos), pos)
                    rs = _after_comma(text, end)
                    if form == "ために" and not _reader_past_tail(ctx, left):
                        pos = text.find(form, pos + 1)
                        continue
                    right_end = _reader_next_boundary(ctx, end)
                    right = _trim_boundary(text, rs, right_end)
                    if (_reader_operand_has_clause(ctx, left, form == "ても")
                            and _reader_operand_has_clause(ctx, right)):
                        found.append(_Link(kind, pos, end, left, right, False))
            pos = text.find(form, pos + 1)
    # Competing marker readings are ambiguity; the separate particle checks
    # above rule out ordinary case-marking が/から and adverb homographs.
    found = [x for x in found if x.left[0] < x.left[1] and x.right[0] < x.right[1]]
    unique = {(x.kind, x.start, x.end, x.left, x.right, x.prefix): x for x in found}
    return tuple(sorted(unique.values(), key=lambda x: (x.start, x.end, x.kind)))


def reads(ctx: ConstructionContext) -> Reading | None:
    if (len(ctx.tokens) > ctx.budget.max_tokens or
            ctx.sentence_span.end - ctx.sentence_span.start != len(ctx.sentence_text)):
        return None
    if _reader_has_condition(ctx):
        return None
    base = ctx.sentence_span.start
    links = _reader_links(ctx)
    if not links:
        return None
    source = ctx.sentence_span.source
    trim_start = len(ctx.sentence_text) - len(ctx.sentence_text.lstrip())
    trim_end = len(ctx.sentence_text.rstrip())
    body = Span(source, base + trim_start, base + trim_end,
                ctx.sentence_text[trim_start:trim_end])
    relations = []
    notes = []
    for link in links:
        kind = "condition_relation" if link.kind == "condition" else link.kind
        marker = Span(source, base + link.start, base + link.end,
                      ctx.sentence_text[link.start:link.end])
        rel_roles = _RELATION_ROLES[kind]
        left_span = Span(source, base + link.left[0], base + link.left[1],
                         ctx.sentence_text[link.left[0]:link.left[1]])
        right_span = Span(source, base + link.right[0], base + link.right[1],
                          ctx.sentence_text[link.right[0]:link.right[1]])
        key = f"{source}\0{base}\0{ctx.sentence_text}\0{kind}\0{link.start}\0{link.end}"
        stem = sha256(key.encode("utf-8")).hexdigest()
        relations.append(Clause(
            id=stem[:24], event=Variable("relation_" + stem[24:42], "event"),
            predicate=kind, predicate_span=marker,
            roles=(Role(rel_roles[0], left_span.text, left_span, "literal"),
                   Role(rel_roles[1], right_span.text, right_span, "literal")),
            span=ctx.sentence_span, body_span=body,
            rule="connective_rel",
            sovereign=ctx.clauses[0].sovereign if ctx.clauses else "document",
            family=ctx.clauses[0].family if ctx.clauses else "document",
        ))
        notes.append(TypedNote("relation_" + link.kind, marker,
                               left_span.text + " -> " + right_span.text))
    if len(relations) > ctx.budget.max_clauses or len(ctx.tokens) + 2 * len(relations) > ctx.budget.max_steps:
        return None
    return Reading(tuple(relations), (ctx.sentence_span,), tuple(notes))


@dataclass(frozen=True)
class _SourceToken:
    surface: str
    start: int
    end: int
    lemma: str
    orth_base: str
    pos1: str
    pos2: str
    ctype: str
    cform: str


_LICENSE_TAGGER = Tagger()


def _license_tokens(sentence: str) -> tuple[_SourceToken, ...]:
    result = []
    offset = 0
    for node in _LICENSE_TAGGER(sentence):
        surface = node.surface
        feature = node.feature
        start = sentence.find(surface, offset)
        if start < 0:
            return ()
        end = start + len(surface)
        result.append(_SourceToken(surface, start, end, feature.lemma,
                                   feature.orthBase, feature.pos1, feature.pos2,
                                   feature.cType, feature.cForm))
        offset = end
    return tuple(result)


def _license_has_condition(sentence: str, tokens: tuple[_SourceToken, ...]) -> bool:
    for form in ("場合", "たら", "なら", "ば"):
        at = sentence.find(form)
        while at >= 0:
            stop = at + len(form)
            ts = [t for t in tokens if t.start < stop and at < t.end]
            if (ts and ts[0].start == at and ts[-1].end == stop
                    and "".join(t.surface for t in ts) == form):
                if form in ("たら", "なら") and any(t.pos1 in ("助詞", "助動詞") for t in ts):
                    return True
                if form == "ば" and any(t.pos2 == "接続助詞" for t in ts):
                    return True
                if form == "場合" and any(t.pos1 == "名詞" for t in ts):
                    return True
            at = sentence.find(form, at + 1)
    return False


def _license_past_tail(sentence: str, tokens: tuple[_SourceToken, ...],
                       bounds: tuple[int, int]) -> bool:
    selected = [t for t in tokens if bounds[0] <= t.start and t.end <= bounds[1]]
    tail = next((t for t in reversed(selected) if t.pos1 != "補助記号"), None)
    return bool(tail and (tail.lemma == "た" or tail.ctype == "助動詞-タ"))


def _license_scope_start(sentence: str, tokens: tuple[_SourceToken, ...],
                         marker_start: int) -> int:
    starts = []
    for form in ("けれども", "しかし", "さらに", "また", "けれど", "が"):
        at = sentence.find(form)
        while 0 <= at < marker_start:
            stop = at + len(form)
            ts = [t for t in tokens if t.start < stop and at < t.end]
            tagged = (not _license_inside_parenthesis(sentence, at)
                      and ts and ts[0].start == at and ts[-1].end == stop
                      and "".join(t.surface for t in ts) == form)
            if form in ("が", "けれど", "けれども"):
                tagged = tagged and any(t.pos2 == "接続助詞" for t in ts)
            elif form in ("しかし", "また", "さらに"):
                tagged = tagged and len(ts) == 1 and ts[0].pos1 in ("副詞", "接続詞")
            comma = stop
            while comma < marker_start and sentence[comma] in " \t":
                comma += 1
            if tagged and comma < marker_start and sentence[comma] == "、":
                starts.append(_after_comma(sentence, comma + 1))
            at = sentence.find(form, at + 1)
    return max(starts, default=0)


def _license_inside_parenthesis(sentence: str, position: int) -> bool:
    depth = 0
    for char in sentence[:position]:
        if char in "（(":
            depth += 1
        elif char in "）)":
            depth = max(0, depth - 1)
    return depth > 0


def _license_link(sentence: str, tokens: tuple[_SourceToken, ...], clause: Clause) -> _Link | None:
    """Re-scan grammar and offsets from the source; it does not call reads()."""
    candidates = []
    # Suffix forms are recognized from their token class and boundary, not by
    # accepting a matching substring alone.
    suffixes = (("ので", "cause"), ("ために", "cause"), ("ため", "cause"), ("から", "cause"),
                ("たら", "condition"), ("なら", "condition"), ("場合", "condition"),
                ("ても", "contrast"), ("けれども", "contrast"),
                ("けれど", "contrast"), ("ば", "condition"), ("が", "contrast"))
    for form, kind in suffixes:
        at = sentence.find(form)
        while at >= 0:
            stop = at + len(form)
            ts = [t for t in tokens if t.start < stop and at < t.end]
            if (not _license_inside_parenthesis(sentence, at) and ts
                    and ts[0].start == at and ts[-1].end == stop
                    and "".join(t.surface for t in ts) == form):
                if form in ("が", "から", "ば", "けれど", "けれども") and not any(
                        t.pos2 == "接続助詞" for t in ts):
                    at = sentence.find(form, at + 1)
                    continue
                if form == "ため" and sentence[stop:stop + 1] in ("に", "の"):
                    at = sentence.find(form, at + 1)
                    continue
                if form == "ために" and not (
                        len(ts) >= 2 and ts[0].surface == "ため" and ts[0].pos1 == "名詞"
                        and ts[-1].surface == "に" and ts[-1].pos1 == "助詞"):
                    at = sentence.find(form, at + 1)
                    continue
                if form == "ても" and sentence[max(0, at - 2):at] == "として":
                    at = sentence.find(form, at + 1)
                    continue
                if form in ("なら", "たら") and not any(t.pos1 in ("助詞", "助動詞") for t in ts):
                    at = sentence.find(form, at + 1)
                    continue
                if form == "場合" and not any(t.pos1 == "名詞" for t in ts):
                    at = sentence.find(form, at + 1)
                    continue
                if form == "ので" and not (len(ts) >= 2 and ts[0].pos1 == "助詞"
                                             and any(t.pos1 == "助動詞" for t in ts[1:])):
                    at = sentence.find(form, at + 1)
                    continue
                if form == "ても" and not (len(ts) >= 2 and ts[-1].pos1 == "助詞"):
                    at = sentence.find(form, at + 1)
                    continue
                if form == "ため" and not any(t.pos1 == "名詞" for t in ts):
                    at = sentence.find(form, at + 1)
                    continue
                if form == "から" and not any(t.pos2 == "接続助詞" for t in ts):
                    at = sentence.find(form, at + 1)
                    continue
                left = _trim_boundary(sentence, _license_scope_start(sentence, tokens, at), at)
                if form == "ために" and not _license_past_tail(sentence, tokens, left):
                    at = sentence.find(form, at + 1)
                    continue
                right = _trim_boundary(sentence, _after_comma(sentence, stop), len(sentence))
                if left[0] < left[1] and right[0] < right[1]:
                    candidates.append(_Link(kind, at, stop, left, right, False))
            at = sentence.find(form, at + 1)
    # Prefix adverbs require a comma boundary and independent adverb tags.
    for form, kind in (("しかし", "contrast"), ("また", "addition"), ("さらに", "addition")):
        at = sentence.find(form)
        while at >= 0:
            stop = at + len(form)
            ts = [t for t in tokens if t.start < stop and at < t.end]
            comma = at - 1
            while comma >= 0 and sentence[comma] in " \t":
                comma -= 1
            if (not _license_inside_parenthesis(sentence, at)
                    and len(ts) == 1 and ts[0].start == at and ts[0].end == stop
                    and ts[0].pos1 in ("副詞", "接続詞")
                    and comma >= 0 and sentence[comma] == "、"):
                left = _trim_boundary(sentence, _license_scope_start(sentence, tokens, at), comma)
                right = _trim_boundary(sentence, _after_comma(sentence, stop), len(sentence))
                if left[0] < left[1] and right[0] < right[1]:
                    candidates.append(_Link(kind, at, stop, left, right, True))
            at = sentence.find(form, at + 1)
    scoped = []
    for link in candidates:
        allow_te = sentence[link.start:link.end] == "ても"
        if not _operand_has_clause(sentence, tokens, link.left, allow_te):
            continue
        later = sorted((x for x in candidates if x.start > link.end),
                       key=lambda x: (x.start, x.end))
        right_end = len(sentence)
        for following in later:
            following_te = sentence[following.start:following.end] == "ても"
            if _operand_has_clause(sentence, tokens, following.left, following_te):
                right_end = min(right_end, following.left[1])
                break
        right = _trim_boundary(sentence, link.right[0], right_end)
        if right[0] < right[1] and _operand_has_clause(sentence, tokens, right,
                                                        allow_te=False):
            scoped.append(_Link(link.kind, link.start, link.end, link.left,
                                right, link.prefix))
    # Select only links that divide this source predicate from another clause.
    relation_kind = "condition" if clause.predicate == "condition_relation" else clause.predicate
    marker_start = clause.predicate_span.start - clause.span.start
    marker_end = clause.predicate_span.end - clause.span.start
    candidates = [x for x in scoped if x.kind == relation_kind
                  and x.start == marker_start and x.end == marker_end]
    unique = {(x.kind, x.start, x.end, x.left, x.right, x.prefix): x for x in candidates}
    return next(iter(unique.values())) if len(unique) == 1 else None


def _operand_has_clause(sentence: str, tokens: tuple[_SourceToken, ...],
                        bounds: tuple[int, int], allow_te: bool = False) -> bool:
    start, end = bounds
    selected = [t for t in tokens if t.start < end and start < t.end]
    if not selected or selected[0].start < start or selected[-1].end > end:
        return False
    if (any(ch in sentence[start:end] for ch in "、「」『』【】[]\"'“”:：")
            or sentence[start:end].rstrip().endswith(("?", "？"))):
        return False
    heads = []
    for index, token in enumerate(selected):
        if token.lemma in _AUX_NONASSERTIVE:
            return False
        if token.lemma in _AUX_NEGATIVE:
            return False
        if token.pos1 not in ("動詞", "形容詞"):
            continue
        previous = selected[index - 1] if index else None
        following = selected[index + 1] if index + 1 < len(selected) else None
        if (allow_te and token.lemma in ("付く", "つく") and previous
                and previous.surface == "に"):
            continue
        if token.cform.startswith("連体形") and following and following.pos1 == "名詞":
            continue
        # Exclude the attributive よる in による and the auxiliary いる in
        # a ている chain.  The exact text remains in the role's source span.
        if token.lemma in ("因る", "依る") and previous and previous.surface == "に":
            continue
        if (token.lemma in ("居る", "いる") and previous
                and previous.surface in ("て", "で") and token.pos2 == "非自立可能"):
            continue
        independent = token.pos2 != "非自立可能"
        lexical_suru = (token.lemma in ("為る", "する") and previous is not None
                        and previous.pos1 == "名詞")
        lexical_copula = token.lemma in ("有る", "成る")
        te_chain = following is not None and following.surface in ("て", "で")
        if independent or lexical_suru or lexical_copula or te_chain:
            heads.append(token)
    if len(heads) != 1:
        return False
    tail = list(selected)
    while tail and tail[-1].pos1 == "補助記号":
        tail.pop()
    if not tail:
        return False
    form = tail[-1].cform
    te_form = allow_te and form.startswith("連用形") and heads[-1] is tail[-1]
    return form.startswith(("終止形", "連体形")) or te_form


def _gaps_are_boundary(sentence: str, link: _Link) -> bool:
    before = sentence[link.left[1]:link.start]
    after = sentence[link.end:link.right[0]]
    if link.prefix:
        return (before.count("、") == 1 and all(c in "、 \t\r\n" for c in before)
                and all(c in "、 \t\r\n" for c in after))
    return (all(c in " \t\r\n" for c in before)
            and all(c in "、 \t\r\n" for c in after))


def licenses(clause: Clause, source: str) -> bool:
    """Independently license a typed relation edge from its source text."""
    if (clause.rule != "connective_rel" or clause.predicate not in _RELATION_ROLES
            or not clause.span.valid({clause.span.source: source})
            or clause.span.end - clause.span.start > 2048):
        return False
    sentence = source[clause.span.start:clause.span.end]
    tokens = _license_tokens(sentence)
    if not tokens or _license_has_condition(sentence, tokens):
        return False
    link = _license_link(sentence, tokens, clause)
    if link is None:
        return False
    marker = Span(clause.span.source, clause.span.start + link.start,
                  clause.span.start + link.end, sentence[link.start:link.end])
    names = _RELATION_ROLES[clause.predicate]
    expected_kind = "condition" if clause.predicate == "condition_relation" else clause.predicate
    left = Span(clause.span.source, clause.span.start + link.left[0],
                clause.span.start + link.left[1], sentence[link.left[0]:link.left[1]])
    right = Span(clause.span.source, clause.span.start + link.right[0],
                 clause.span.start + link.right[1], sentence[link.right[0]:link.right[1]])
    trim_start = len(sentence) - len(sentence.lstrip())
    trim_end = len(sentence.rstrip())
    expected_body = Span(clause.span.source, clause.span.start + trim_start,
                         clause.span.start + trim_end, sentence[trim_start:trim_end])
    return (expected_kind == link.kind and clause.predicate_span == marker
            and clause.body_span == expected_body and clause.span.text == sentence
            and clause.polarity == "+" and clause.modality == "assert" and not clause.time
            and clause.event.sort == "event" and _gaps_are_boundary(sentence, link)
            and _operand_has_clause(sentence, tokens, link.left,
                                    sentence[link.start:link.end] == "ても")
            and _operand_has_clause(sentence, tokens, link.right)
            and not clause.conditions and not clause.condition_spans
            and not clause.exceptions and not clause.exception_spans and not clause.exception_of
            and len(clause.roles) == 2
            and clause.roles[0] == Role(names[0], left.text, left, "literal")
            and clause.roles[1] == Role(names[1], right.text, right, "literal"))


register(Construction(name="connective_rel", priority=30, reads=reads,
                      licenses=licenses, refines=("frame",)))


__all__ = ("licenses", "reads")
