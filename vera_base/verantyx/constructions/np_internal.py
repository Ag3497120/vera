"""Source-bounded noun-phrase structure for the semantic reader."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import re

from ..semantic_ir import Clause, Nominal, Role, Span, Variable
from . import Construction, ConstructionContext, Reading, TypedNote, register


_NAME = "np_internal"
_FUNCTION_POS = frozenset(("助詞", "助動詞", "補助記号", "記号"))
_NOUN_POS = frozenset(("名詞", "接頭辞", "接尾辞", "連体詞", "形容詞"))
_REASON_UNREPRESENTED = "unrepresented source content"


def _fields(item):
    value = getattr(item, "token", None)
    if isinstance(value, tuple) and len(value) >= 4:
        return str(value[0]), str(value[1]), str(value[2]), str(value[3])
    if isinstance(value, str):
        return value, "", "", ""
    feature = getattr(value, "feature", None)
    return (str(getattr(value, "surface", "")), str(getattr(feature, "pos1", "")),
            str(getattr(feature, "pos2", "")), str(getattr(feature, "cForm", "")))


def _relative(ctx, span):
    if span.source != ctx.sentence_span.source:
        return None
    start, end = span.start - ctx.sentence_span.start, span.end - ctx.sentence_span.start
    if not (0 <= start < end <= len(ctx.sentence_text)) or ctx.sentence_text[start:end] != span.text:
        return None
    return start, end


def _tokens_in(ctx, start, end):
    out = []
    for item in ctx.tokens:
        if item.start >= start and item.end <= end:
            out.append(_fields(item))
        elif item.start < end and item.end > start:
            return None
    return out or None


def _appositions(tokens):
    found = []
    for i, (surface, _, _, _) in enumerate(tokens):
        if surface == "という":
            found.append((i, i + 1))
        elif surface == "と" and i + 1 < len(tokens) and tokens[i + 1][0] == "いう":
            found.append((i, i + 2))
        elif surface == "で" and i + 1 < len(tokens) and tokens[i + 1][0] == "ある":
            found.append((i, i + 2))
    return found


def _coordinators(tokens):
    found = []
    for i, (surface, pos, _, _) in enumerate(tokens):
        if surface in ("と", "や") and pos == "助詞":
            # と is ambiguous with a case marker; the full parse below accepts
            # it only when it separates two complete nominal constituents.
            found.append((i, i + 1, surface))
        elif surface in ("、", "・") and pos == "補助記号":
            found.append((i, i + 1, surface))
    return found


def _head(term):
    return term.head if isinstance(term, Nominal) else term if isinstance(term, str) else ""


def _parse(tokens, depth=0):
    if depth > 8 or not tokens:
        return None
    pairs = {"（": "）", "(": ")"}
    if tokens[0][0] in pairs and tokens[-1][0] == pairs[tokens[0][0]]:
        inside = _parse(tokens[1:-1], depth + 1)
        if inside is not None:
            return Nominal(head=_head(inside), term=inside)
    for i, (surface, _, _, _) in enumerate(tokens):
        if surface in pairs and i > 0 and tokens[-1][0] == pairs[surface]:
            left, inside = _parse(tokens[:i], depth + 1), _parse(tokens[i+1:-1], depth + 1)
            if left is not None and inside is not None:
                return Nominal(head=_head(left), term=inside)
    apps = _appositions(tokens)
    if apps:
        if len(apps) != 1:
            return None
        a, b = apps[0]
        left, right = _parse(tokens[:a], depth + 1), _parse(tokens[b:], depth + 1)
        if left is None or right is None:
            return None
        return Nominal(head=_head(right), term=left)

    coords = _coordinators(tokens)
    if coords:
        parts, markers, begin = [], [], 0
        for a, b, marker in coords:
            part = _parse(tokens[begin:a], depth + 1)
            if part is None:
                return None
            parts.append(part); markers.append(marker); begin = b
        part = _parse(tokens[begin:], depth + 1)
        if part is None:
            return None
        parts.append(part)
        return Nominal(head=_head(parts[-1]), term=("coord", tuple(markers), tuple(parts)))

    links = [i for i, (surface, pos, pos2, _) in enumerate(tokens)
             if surface == "の" and pos == "助詞" and pos2 == "格助詞"]
    if links:
        parts, begin = [], 0
        for i in links:
            part = _parse(tokens[begin:i], depth + 1)
            if part is None:
                return None
            parts.append(part); begin = i + 1
        part = _parse(tokens[begin:], depth + 1)
        if part is None:
            return None
        term = parts[0]
        for right in (*parts[1:], part):
            head = _head(right)
            if not head:
                return None
            term = Nominal(head=head, term=term)
        return term

    if any(pos not in _NOUN_POS and not (pos == "補助記号" and s in ("・", "-", "–", "—"))
           for s, pos, _, _ in tokens):
        return None
    if not any(pos in ("名詞", "接尾辞") for _, pos, _, _ in tokens) and not all(
            pos in ("連体詞", "形容詞") for _, pos, _, _ in tokens):
        return None
    prefix = 0
    while prefix < len(tokens) and tokens[prefix][1] in ("連体詞", "形容詞"):
        prefix += 1
    if prefix and prefix < len(tokens):
        right = _parse(tokens[prefix:], depth + 1)
        if right is None or not _head(right):
            return None
        return Nominal(head=_head(right), term="".join(s for s, _, _, _ in tokens[:prefix]))
    return "".join(s for s, _, _, _ in tokens)


def _has_np_marker(tokens):
    return (any(s == "の" and p == "助詞" and p2 == "格助詞" for s, p, p2, _ in tokens)
            or bool(_appositions(tokens)) or bool(_coordinators(tokens))
            or (len(tokens) > 2 and tokens[0][0] in ("（", "(")
                and tokens[-1][0] in ("）", ")"))
            or any(s in ("（", "(") and i > 0 and tokens[-1][0] in ("）", ")")
                   for i, (s, _, _, _) in enumerate(tokens))
            or (len(tokens) > 1 and tokens[0][1] in ("連体詞", "形容詞")
                and any(pos in ("名詞", "接尾辞") for _, pos, _, _ in tokens[1:])))


def _nominal_phrase_start(tokens, case_index):
    j = case_index - 1
    if j < 0:
        return None
    begin = j
    if tokens[j][0] in ("）", ")", "」", "』", "】"):
        close_to_open = {"）": "（", ")": "(", "」": "「", "』": "『", "】": "【"}
        opening = close_to_open[tokens[j][0]]
        depth = 0
        while j >= 0:
            if tokens[j][0] == tokens[case_index-1][0]:
                depth += 1
            elif tokens[j][0] == opening:
                depth -= 1
                if depth == 0:
                    j -= 1
                    break
            j -= 1
        if depth:
            return None
        begin = j + 1
    while j >= 0:
        surface, pos, pos2, _ = tokens[j]
        if pos in _NOUN_POS or (pos == "補助記号" and surface in ("・", "-", "–", "—")):
            begin = j; j -= 1; continue
        if (surface == "の" and pos == "助詞" and pos2 == "格助詞") or (
                surface in ("と", "や") and pos == "助詞") or (
                surface == "、" and pos == "補助記号"):
            begin = j; j -= 1; continue
        break
    return begin


def _frame_arguments(ctx, clause, roles):
    """Recover only unambiguous が/を/は arguments that the frame left out."""
    tokens = [_fields(item) for item in ctx.tokens]
    starts = [item.start for item in ctx.tokens]
    pred = clause.predicate_span.start - ctx.sentence_span.start
    passive = any(x in ctx.sentence_text[pred:] for x in ("られる", "られ", "れる", "され"))
    cases = []
    for i, (surface, pos, pos2, _) in enumerate(tokens):
        if starts[i] >= pred:
            break
        if pos != "助詞":
            continue
        if surface in ("が", "を", "は"):
            if (surface == "は" and i and tokens[i-1][1] == "助詞"
                    and tokens[i-1][0] in ("に", "で", "へ", "と", "も", "から", "まで")):
                continue
            cases.append((i, surface, 1))
        elif surface == "で" and i + 1 < len(tokens) and tokens[i+1][0] == "は":
            cases.append((i, "では", 2))
    expanded = list(roles)
    used = []
    for i, marker, width in cases:
        begin = _nominal_phrase_start(tokens, i)
        if begin is None:
            return None
        start, end = ctx.tokens[begin].start, ctx.tokens[i-1].end
        if end <= start or start < 0:
            return None
        name = "patient" if marker == "を" or (marker == "が" and passive) else (
            "agent" if marker == "が" else "topic")
        if marker == "は":
            begin_abs = ctx.sentence_span.start + start
            end_abs = ctx.sentence_span.start + end
            if any(r.name == "topic" and begin_abs <= r.span.start < r.span.end <= end_abs for r in expanded):
                name = "topic"
            elif any(r.name == "agent" and begin_abs <= r.span.start < r.span.end <= end_abs for r in expanded):
                name = "agent"
        text = ctx.sentence_text[start:end]
        source_start = ctx.sentence_span.start + start
        source_end = ctx.sentence_span.start + end
        span = Span(ctx.sentence_span.source, source_start, source_end, text)
        same = [j for j, role in enumerate(expanded)
                if role.name == name and span.start <= role.span.start and role.span.end <= span.end]
        overlaps = [role for role in expanded if role.span.start < span.end and span.start < role.span.end]
        if overlaps and not same:
            continue
        if same:
            # A case-bounded phrase can restore omitted conjuncts or nominal heads.
            j = same[0]
            if any(k != j and expanded[k].name == name for k in same):
                return None
            if span.start != expanded[j].span.start or span.end != expanded[j].span.end:
                phrase_tokens = _tokens_in(ctx, start, end)
                nominal = _parse(phrase_tokens) if phrase_tokens and _has_np_marker(phrase_tokens) else None
                if _has_np_marker(phrase_tokens or ()) and not isinstance(nominal, Nominal):
                    return None
                expanded[j] = replace(expanded[j], term=text, span=span,
                                       rule="nominal" if isinstance(nominal, Nominal) else expanded[j].rule)
                used.append((span, nominal))
            continue
        existing = [role for role in expanded if role.name == name]
        if existing:
            # Several separate arguments in one slot are not silently pooled.
            continue
        phrase_tokens = _tokens_in(ctx, start, end)
        nominal = _parse(phrase_tokens) if phrase_tokens and _has_np_marker(phrase_tokens) else None
        if _has_np_marker(phrase_tokens or ()) and not isinstance(nominal, Nominal):
            return None
        expanded.append(Role(name, text, span, "nominal" if isinstance(nominal, Nominal) else "frame"))
        used.append((span, nominal))
    if len({role.name for role in expanded}) != len(expanded):
        return None
    return tuple(sorted(expanded, key=lambda role: (role.span.start, role.name))), tuple(used)


def _covered(ctx, span, roles, predicate, clause):
    a, b = span.start - ctx.sentence_span.start, span.end - ctx.sentence_span.start
    if not (0 <= a < b <= len(ctx.sentence_text)):
        return False
    coverage = [(r.span.start - ctx.sentence_span.start, r.span.end - ctx.sentence_span.start) for r in roles]
    ps = (predicate.start - ctx.sentence_span.start, predicate.end - ctx.sentence_span.start)
    coverage.append(ps)
    if clause.predicate.endswith("する"):
        stem = clause.predicate[:-2]
        if stem and ps[0] >= len(stem) and ctx.sentence_text[ps[0]-len(stem):ps[0]] == stem:
            coverage.append((ps[0]-len(stem), ps[0]))
    for item in ctx.tokens:
        if item.end <= a or item.start >= b:
            continue
        if any(x <= item.start and item.end <= y for x, y in coverage):
            continue
        surface, pos, _, _ = _fields(item)
        tail = ctx.sentence_text[predicate.end-ctx.sentence_span.start:item.start+1]
        discourse = pos == "接続詞" and item.start == a
        auxiliary = (surface in ("いる", "ある") and item.start > predicate.end-ctx.sentence_span.start
                     and "て" in tail)
        if pos not in _FUNCTION_POS and not discourse and not auxiliary:
            return False
    return True


def _with_nominals(ctx, clause):
    if clause.rule != "frame" or _REASON_UNREPRESENTED not in clause.unsupported:
        return None, None
    if len(clause.roles) > ctx.budget.max_clauses or len(ctx.tokens) > ctx.budget.max_tokens:
        return None, None
    if len({r.name for r in clause.roles}) != len(clause.roles):
        return None, None
    framed = _frame_arguments(ctx, clause, clause.roles)
    if framed is None:
        return None, None
    expanded_roles, recovered = framed
    roles, changed, saw_to = [], 0, False
    for role in expanded_roles:
        if role.name not in ("agent", "patient", "topic") or not isinstance(role.term, str):
            roles.append(role); continue
        rel = _relative(ctx, role.span)
        if rel is None:
            return None, None
        tokens = _tokens_in(ctx, *rel)
        if not tokens or not _has_np_marker(tokens):
            roles.append(role); continue
        term = _parse(tokens)
        if term is None or not isinstance(term, Nominal):
            return None, TypedNote("ambiguous_np_internal", role.span,
                                   "modifier or coordinator has no unique noun-phrase parse")
        if isinstance(term.term, tuple) and term.term[:1] == ("coord",):
            saw_to = saw_to or "と" in term.term[1]
        # Fact roles remain exact source literals for semantic_verify. The typed
        # nominal parse is the construction's structural proof; role.rule records
        # that the full noun phrase, including its modifiers, is the argument.
        roles.append(replace(role, term=role.span.text, rule="nominal")); changed += 1
    if not changed or not any(role.rule == "nominal" for role in roles):
        return None, None

    allowed = {_REASON_UNREPRESENTED}
    if saw_to:
        allowed.add("ambiguous case role: と")
    if any(reason not in allowed for reason in clause.unsupported):
        return None, None
    if "ambiguous case role: と" in clause.unsupported and any(r.name == "ambiguous" for r in clause.roles):
        return None, None

    if not _covered(ctx, clause.span, roles, clause.predicate_span, clause):
        return None, None
    updated = replace(clause, id=hashlib.sha256((clause.id + "|np_internal").encode()).hexdigest()[:24],
                      roles=tuple(roles), rule=_NAME, unsupported=())
    return updated, None


def reads(ctx: ConstructionContext) -> Reading | None:
    if len(ctx.tokens) > ctx.budget.max_tokens or len(ctx.clauses) > ctx.budget.max_steps:
        return None
    sentence_clauses = tuple(clause for clause in ctx.clauses
                             if clause.span.source == ctx.sentence_span.source
                             and ctx.sentence_span.start <= clause.span.start
                             and clause.span.end <= ctx.sentence_span.end)
    if (len(sentence_clauses) > ctx.budget.max_clauses
            or ctx.budget.max_steps < len(ctx.tokens) + len(sentence_clauses)):
        return None
    clauses, consumed, notes = [], [], []
    for clause in sentence_clauses:
        updated, note = _with_nominals(ctx, clause)
        if note is not None:
            notes.append(note)
        if updated is not None:
            clauses.append(updated); consumed.append(updated.span)
    if not clauses and not notes:
        return None
    return Reading(tuple(clauses), tuple(consumed), tuple(notes))


def _source_tree(text, depth=0):
    """Independent character-level reconstruction for the licensor."""
    if depth > 8 or not text:
        return None
    apps = [(text.find(m), m) for m in ("という", "である") if m in text]
    if apps:
        if len(apps) != 1:
            return None
        i, marker = apps[0]
        left, right = text[:i], text[i+len(marker):]
        if not left or not right or any(m in left+right for m in ("という", "である")):
            return None
        return Nominal(head=right, term=left)

    for opening, closing in (("（", "）"), ("(", ")")):
        if opening in text and text.endswith(closing):
            i = text.find(opening)
            left, inner = text[:i], text[i+len(opening):-len(closing)]
            if left and inner:
                return Nominal(head=left, term=_source_tree(inner, depth+1))

    # The reader requires a morphological token boundary for と. The licensor
    # uses stricter character boundaries, independently of that token decision.
    cuts = []
    for i, char in enumerate(text):
        if char in "や、・":
            cuts.append((i, char))
        elif char == "と" and 0 < i < len(text)-1:
            left, right = text[i-1], text[i+1]
            kana = lambda c: "ぁ" <= c <= "ゖ" or "ァ" <= c <= "ヺ"
            if not kana(left) and not kana(right):
                cuts.append((i, char))
    if cuts:
        parts, markers, begin = [], [], 0
        for i, marker in cuts:
            part = _source_tree(text[begin:i], depth+1)
            if part is None:
                return None
            parts.append(part); markers.append(marker); begin = i+1
        part = _source_tree(text[begin:], depth+1)
        if part is None:
            return None
        parts.append(part)
        return Nominal(head=parts[-1].head if isinstance(parts[-1], Nominal) else parts[-1],
                       term=("coord", tuple(markers), tuple(parts)))

    if "の" in text:
        parts = text.split("の")
        if len(parts) < 2 or any(not p for p in parts):
            return None
        term = parts[0]
        for right in parts[1:]:
            term = Nominal(head=right, term=term)
        return term
    try:
        from fugashi import Tagger
        words = list(Tagger()(text))
        prefix = 0
        while prefix < len(words) and str(words[prefix].feature.pos1) in ("連体詞", "形容詞"):
            prefix += 1
        if prefix and prefix < len(words):
            modifier = "".join(word.surface for word in words[:prefix])
            head = "".join(word.surface for word in words[prefix:])
            if modifier and head:
                return Nominal(head=head, term=modifier)
    except Exception:
        return None
    return text


def _source_covered(clause, source):
    try:
        from fugashi import Tagger
    except Exception:
        return False
    if source[clause.span.start:clause.span.end] != clause.span.text:
        return False
    covered = [(r.span.start-clause.span.start, r.span.end-clause.span.start) for r in clause.roles]
    covered.append((clause.predicate_span.start-clause.span.start, clause.predicate_span.end-clause.span.start))
    if clause.predicate.endswith("する"):
        stem = clause.predicate[:-2]
        ps = covered[-1][0]
        if stem and ps >= len(stem) and clause.span.text[ps-len(stem):ps] == stem:
            covered.append((ps-len(stem), ps))
    at = 0
    for word in Tagger()(clause.span.text):
        end = at + len(word.surface)
        if not any(a <= at and end <= b for a, b in covered):
            surface, pos = word.surface, str(word.feature.pos1)
            discourse = pos == "接続詞" and at == 0
            pred_end = clause.predicate_span.end - clause.span.start
            auxiliary = (surface in ("いる", "ある") and at > pred_end
                         and "て" in clause.span.text[pred_end:end])
            if pos not in _FUNCTION_POS and not discourse and not auxiliary:
                return False
        at = end
    return True


def licenses(clause: Clause, source: str) -> bool:
    if (clause.rule != _NAME or not isinstance(clause.event, Variable) or clause.event.sort != "event"
            or clause.polarity != "+" or clause.modality != "assert" or clause.time not in ("", "past", "nonpast")
            or clause.conditions or clause.exceptions or clause.exception_of
            or not source[clause.span.start:clause.span.end] == clause.span.text
            or len({r.name for r in clause.roles}) != len(clause.roles)):
        return False
    modified = []
    for role in clause.roles:
        if (role.span.source != clause.span.source or not (clause.span.start <= role.span.start < role.span.end <= clause.span.end)
                or source[role.span.start:role.span.end] != role.span.text):
            return False
        if role.rule == "nominal":
            if role.name not in ("agent", "patient", "topic") or not isinstance(role.term, str):
                return False
            if role.term != role.span.text or not isinstance(_source_tree(role.span.text), Nominal):
                return False
            marker = source[role.span.end:role.span.end+3]
            if role.name == "agent" and not marker.startswith(("が", "は")):
                return False
            if role.name == "topic" and not (marker.startswith("は") or marker.startswith("では")):
                return False
            if role.name == "patient":
                passive = any(x in clause.span.text for x in ("られる", "られ", "れる", "され"))
                if not marker.startswith("を") and not (marker.startswith("が") and passive):
                    return False
            modified.append(role)
        elif not isinstance(role.term, str) or role.term != role.span.text:
            return False
    if not modified or not _source_covered(clause, source):
        return False
    tail = source[clause.predicate_span.end:clause.span.end]
    if re.search(r"(?:なかっ|ない|ません|ぬ)(?:た|でした)?", tail):
        return False
    if clause.time == "past" and not re.search(r"(?:た|だ)(?:[。\s]|$)", tail):
        return False
    if clause.time == "nonpast" and re.search(r"(?:なかっ|ました)(?:[。\s]|$)", tail):
        return False
    return True


register(Construction(name=_NAME, priority=45, reads=reads, licenses=licenses, refines=("frame",)))
