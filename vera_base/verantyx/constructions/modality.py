"""Source-bound modality and evidentiality readings."""
from __future__ import annotations

import re

from ..semantic_ir import Clause, Role, Span, Variable
from . import Construction, ConstructionContext, Reading, register


# These are grammatical endings, not a vocabulary list.  Longer endings come
# first so that 可能性 is never mistaken for the predicate 可能.
_ENDINGS = (
    ("可能性がある", "possibility"),
    ("不可能であった", "impossibility"),
    ("不可能である", "impossibility"),
    ("不可能だった", "impossibility"),
    ("不可能だ", "impossibility"),
    ("不可能", "impossibility"),
    ("可能であった", "possibility"),
    ("可能である", "possibility"),
    ("可能だった", "possibility"),
    ("可能だ", "possibility"),
    ("可能", "possibility"),
    ("と思われる", "hearsay"),
    ("と言われる", "hearsay"),
    ("とされる", "hearsay"),
    ("だろう", "possibility"),
    ("はずだ", "possibility"),
    ("ようだ", "possibility"),
    ("らしい", "hearsay"),
    ("べき", "obligation"),
)
_END_RE = re.compile("|".join(re.escape(word) for word, _ in _ENDINGS))
_MODALITY = dict(_ENDINGS)
_PARTICLES = {
    "agent": ("が", "は", "に", "によって", "により"),
    "patient": ("を", "が", "は"),
    "recipient": ("に", "へ", "と"),
    "source": ("から", "より"),
    "by": ("によって", "により", "による", "に", "から"),
    "place": ("で", "に", "へ"),
    "setting": ("で", "に", "において", "における"),
    "topic": ("は", "では"),
    "time": ("に", "で"),
    "direction": ("へ", "に", "から"),
    "capacity": ("として", "で"),
    "companion": ("と", "に"),
    "instrument": ("で", "によって"),
    "owner": ("の",),
}
_STRUCTURAL_POS = frozenset(("助詞", "助動詞", "補助記号"))
_ALLOWED_GAP = frozenset(("た", "て", "で", "いる", "いた", "ある", "あった",
                          "ない", "なかった", "ます", "ました", "と", "に", "へ",
                          "が", "は", "も", "を", "れる", "られる", "ず", "ぬ",
                          "べき", "よう", "だ", "で", "な", "こと"))
_QUOTE_PAIRS = (("「", "」"), ("『", "』"), ("“", "”"), ('"', '"'))


def _feature(token):
    return getattr(token, "feature", None)


def _pos1(token):
    feature = _feature(token)
    value = getattr(feature, "pos1", "") if feature is not None else ""
    if value:
        return value
    return str(getattr(token, "pos", "")).split(",", 1)[0]


def _surface(token):
    return str(getattr(token, "surface", token))


def _in_quote(text, position):
    return any(text.rfind(opening, 0, position) > text.rfind(closing, 0, position)
               for opening, closing in _QUOTE_PAIRS)


def _sentence_span(ctx):
    left = len(ctx.sentence_text) - len(ctx.sentence_text.lstrip())
    right = len(ctx.sentence_text.rstrip())
    start = ctx.sentence_span.start + left
    return Span(ctx.sentence_span.source, start, ctx.sentence_span.start + right,
                ctx.sentence_text[left:right])


def _body_boundary(ctx):
    trimmed = _sentence_span(ctx)
    return None if trimmed == ctx.sentence_span else trimmed


def _markers(ctx):
    found = []
    text = ctx.sentence_text
    for match in _END_RE.finditer(text):
        cue = match.group(0)
        modality = _MODALITY[cue]
        start, end = match.span()
        tail = text[end:]
        if _in_quote(text, start):
            continue
        if tail.startswith(("とされた場合", "とされる場合", "と考えられた場合",
                            "の場合", "ならば", "なら")):
            continue
        if cue in ("可能", "不可能"):
            if tail.startswith("性"):
                continue
            if tail and not tail.startswith(("で", "だ", "な", "と", "。", "、", "が", "に",
                                             "）", ")", "」", "』", "”", "\n", " ")):
                continue
            if tail.startswith(("になって", "になった")):
                pass
            if tail.startswith("と") and not tail.startswith(("とされ", "と言わ", "と思わ", "と考え")):
                continue
            if tail.startswith(("とされた場合", "とされる場合", "と考えられた場合")):
                continue
        if cue == "らしい" and start and text[start - 1] in "らし":
            continue
        found.append((start, end, cue, modality))
    return found


def _root_start(ctx, clause):
    """Extend a サ変 predicate over its verbal-noun stem when tagged that way."""
    pred = clause.predicate_span
    local = pred.start - ctx.sentence_span.start
    for item in ctx.tokens:
        if item.end != local:
            continue
        stem = _surface(item.token)
        feature = _feature(item.token)
        pos3 = getattr(feature, "pos3", "") if feature is not None else ""
        if ("サ変可能" in pos3 and clause.predicate == stem + "する"):
            return item.start + ctx.sentence_span.start
    return pred.start


def _role_particle(ctx, role):
    if role.name == "ambiguous" or role.name not in _PARTICLES or role.rule not in ("literal", "frame"):
        return False
    if not isinstance(role.term, str) or role.term != role.span.text:
        return False
    # Numeric spans marked as recipients are commonly time adjuncts.  Leave
    # them out of this clause unless the reader already typed them as time.
    if role.name == "recipient" and re.search(r"(?:\d|[０-９]).*(?:年|月|日|頃|ごろ)", role.span.text):
        return False
    local_end = role.span.end - ctx.sentence_span.start
    if local_end < 0:
        return False
    remainder = ctx.sentence_text[local_end:]
    return any(remainder.startswith(particle) for particle in _PARTICLES[role.name])


def _covered_body(ctx, clause, marker, roles, root_start):
    cue_start = ctx.sentence_span.start + marker[0]
    cue_end = ctx.sentence_span.start + marker[1]
    pred = clause.predicate_span
    start = min([root_start, pred.start] + [r.span.start for r in roles])
    if not (ctx.sentence_span.start <= start < cue_end <= ctx.sentence_span.end):
        return None
    pred_tokens = [(root_start, pred.end)]
    role_ranges = [(r.span.start, r.span.end) for r in roles]
    cue_range = (cue_start, cue_end)
    for item in ctx.tokens:
        lo = ctx.sentence_span.start + item.start
        hi = ctx.sentence_span.start + item.end
        if hi <= start or lo >= cue_end:
            continue
        if any(a <= lo and hi <= b for a, b in role_ranges + pred_tokens + [cue_range]):
            continue
        surface = _surface(item.token)
        if _pos1(item.token) in _STRUCTURAL_POS and surface in _ALLOWED_GAP:
            continue
        if surface == "こと" and _pos1(item.token) == "名詞" and cue_start > hi:
            continue
        return None
    return Span(ctx.sentence_span.source, start, cue_end,
                ctx.sentence_text[start - ctx.sentence_span.start:marker[1]])


def _candidate(ctx, marker, clauses):
    cue_start = ctx.sentence_span.start + marker[0]
    cue_end = ctx.sentence_span.start + marker[1]
    candidates = []
    for clause in clauses:
        if clause.span.source != ctx.sentence_span.source:
            continue
        pred = clause.predicate_span
        if not (ctx.sentence_span.start <= pred.start < pred.end <= cue_end):
            continue
        if pred.start < cue_end and pred.end > cue_start:
            continue
        if pred.end > cue_start or cue_start - pred.end > 12:
            continue
        intervening = [t for t in ctx.tokens
                       if pred.end - ctx.sentence_span.start <= t.start
                       and t.end <= marker[0]]
        if any((_pos1(t.token) not in _STRUCTURAL_POS or _surface(t.token) not in _ALLOWED_GAP)
               and not (marker[3] in ("possibility", "impossibility")
                        and _surface(t.token) == "こと" and _pos1(t.token) == "名詞")
               for t in intervening):
            continue
        candidates.append(clause)
    if not candidates:
        return None
    candidates.sort(key=lambda c: (marker[0] - (c.predicate_span.end - ctx.sentence_span.start), c.id))
    if len(candidates) > 1:
        first_gap = marker[0] - (candidates[0].predicate_span.end - ctx.sentence_span.start)
        second_gap = marker[0] - (candidates[1].predicate_span.end - ctx.sentence_span.start)
        if first_gap == second_gap:
            return None
    return candidates[0]


def _verbal_noun(ctx, marker):
    """Read an open-class verbal noun as an event when 可能 scopes over it."""
    if marker[3] not in ("possibility", "impossibility"):
        return None
    marker_start = marker[0]
    preceding = [item for item in ctx.tokens if item.end <= marker_start]
    if not preceding:
        return None
    item = preceding[-1]
    # A case/topic particle may intervene between the event noun and 可能.
    if _pos1(item.token) == "助詞" and _surface(item.token) in ("も", "は", "が"):
        preceding = preceding[:-1]
        if not preceding:
            return None
        item = preceding[-1]
    feature = _feature(item.token)
    pos3 = getattr(feature, "pos3", "") if feature is not None else ""
    lemma = getattr(feature, "lemma", None) if feature is not None else None
    verbal_noun = _pos1(item.token) == "名詞" and "サ変可能" in pos3
    event_nominal = (_pos1(item.token) == "名詞" and _surface(item.token).endswith("し")
                     and marker[2].startswith("可能"))
    if not (verbal_noun or event_nominal) or not isinstance(lemma, str) or not lemma:
        return None
    local_start = item.start
    start_abs = ctx.sentence_span.start + local_start
    predicate_span = Span(ctx.sentence_span.source, start_abs, start_abs + len(_surface(item.token)),
                          _surface(item.token))
    event = Variable("modality-event:" + str(start_abs), "event")
    clause = Clause(
        id="modality:" + str(start_abs), event=event,
        predicate=lemma + "する" if verbal_noun else lemma,
        predicate_span=predicate_span, roles=(),
        span=ctx.sentence_span,
        body_span=_body_boundary(ctx),
        polarity="+", modality=marker[3], time="nonpast", rule="modality",
    )
    return clause


def reads(ctx: ConstructionContext) -> Reading | None:
    if len(ctx.tokens) > ctx.budget.max_tokens:
        return None
    markers = _markers(ctx)
    if not markers or len(markers) > ctx.budget.max_steps:
        return None
    if len(ctx.tokens) + min(len(ctx.clauses), ctx.budget.max_clauses) > ctx.budget.max_steps:
        return None
    # document_view may pass clauses accumulated for earlier source documents;
    # scan only the bounded tail, where the current sentence's native clauses
    # are appended, then enforce the clause budget on this sentence's subset.
    recent = ctx.clauses[-ctx.budget.max_clauses:]
    clauses = tuple(c for c in recent if c.span.source == ctx.sentence_span.source
                    and c.span.start < ctx.sentence_span.end
                    and c.span.end > ctx.sentence_span.start)
    if len(clauses) > ctx.budget.max_clauses:
        return None
    made = []
    bodies = []
    for marker in markers:
        clause = _candidate(ctx, marker, clauses)
        if clause is None and (marker[2].startswith("可能") or marker[2].startswith("不可能")):
            clause = _verbal_noun(ctx, marker)
            if clause is not None:
                made.append(clause)
                local_start = clause.predicate_span.start - ctx.sentence_span.start
                end_abs = ctx.sentence_span.start + marker[1]
                bodies.append(Span(ctx.sentence_span.source, clause.predicate_span.start,
                                   end_abs, ctx.sentence_text[local_start:marker[1]]))
                continue
        if clause is None or clause.conditions or clause.exceptions:
            continue
        if clause.polarity not in ("+", "-"):
            continue
        root_start = _root_start(ctx, clause)
        # Drop roles that are ambiguous or cannot be independently tied to a
        # case particle. Then keep only a body whose lexical tokens are typed.
        retained = [r for r in clause.roles if _role_particle(ctx, r)]
        body = None
        while True:
            body = _covered_body(ctx, clause, marker, retained, root_start)
            if body is not None:
                break
            if not retained:
                break
            retained.pop(0)
        if body is None:
            continue
        safe_time = clause.time if clause.time in ("past", "nonpast") else ""
        made.append(Clause(
            id=clause.id + ":modality", event=clause.event, predicate=clause.predicate,
            predicate_span=clause.predicate_span, roles=tuple(retained), span=ctx.sentence_span,
            body_span=_body_boundary(ctx), polarity=clause.polarity, modality=marker[3], time=safe_time,
            rule="modality", sovereign=clause.sovereign, family=clause.family,
        ))
        bodies.append(body)
    if not made:
        return None
    ordered = sorted(zip(made, bodies), key=lambda pair: pair[1].start)
    for index, (_, left) in enumerate(ordered):
        if any(right.start < left.end for _, right in ordered[index + 1:]):
            return None
    return Reading(tuple(clause for clause, _ in ordered),
                   tuple(body for _, body in ordered), ())


def licenses(clause: Clause, source: str) -> bool:
    """Check the source morphology and argument positions without calling reads."""
    if clause.rule != "modality" or clause.unsupported:
        return False
    if not clause.span.valid({clause.span.source: source}):
        return False
    if clause.body_span is not None:
        if not clause.body_span.valid({clause.body_span.source: source}):
            return False
        left = len(clause.span.text) - len(clause.span.text.lstrip())
        right = len(clause.span.text.rstrip())
        if (clause.body_span.start != clause.span.start + left
                or clause.body_span.end != clause.span.start + right
                or clause.body_span.text != clause.span.text[left:right]):
            return False
    modality_cues = {
        "hearsay": ("と思われる", "と言われる", "とされる", "らしい"),
        "obligation": ("べき",),
        "possibility": ("可能性がある", "可能であった", "可能である", "可能だった",
                        "可能だ", "可能", "だろう", "はずだ", "ようだ"),
        "impossibility": ("不可能であった", "不可能である", "不可能だった", "不可能だ", "不可能"),
    }
    cues = modality_cues.get(clause.modality)
    if not cues:
        return False
    pred = clause.predicate_span
    if not (clause.span.start <= pred.start < pred.end <= clause.span.end):
        return False
    if source[pred.start:pred.end] != pred.text:
        return False
    if clause.modality == "impossibility" and clause.polarity != "+":
        return False
    if clause.modality != "impossibility" and clause.polarity == "-":
        # Negation is not silently recast as a modality distinction.
        return False
    if len({r.name for r in clause.roles}) != len(clause.roles):
        return False
    for role in clause.roles:
        if (role.name not in _PARTICLES or role.rule not in ("literal", "frame")
                or not isinstance(role.term, str) or role.term != role.span.text
                or not role.span.valid({role.span.source: source})
                or not (clause.span.start <= role.span.start < role.span.end <= clause.span.end)):
            return False
        suffix = source[role.span.end:role.span.end + 8]
        if not any(suffix.startswith(p) for p in _PARTICLES[role.name]):
            return False

    # Re-find the ending from the source and attach it to this predicate by a
    # bounded inflection/particle gap.  This check is independent of reads().
    sentence = source[clause.span.start:clause.span.end]
    matches = []
    for word in cues:
        cursor = 0
        while True:
            offset = sentence.find(word, cursor)
            if offset < 0:
                break
            at = clause.span.start + offset
            if at >= pred.end:
                gap = source[pred.end:at]
                if len(gap) <= 12 and all(
                        not ((0x4E00 <= ord(ch) <= 0x9FFF)
                             or (0x30A0 <= ord(ch) <= 0x30FF)
                             or ch.isascii() and ch.isalnum()) for ch in gap):
                    matches.append((at, word))
            cursor = offset + 1
    if not matches:
        return False
    longest_at = {}
    for at, word in matches:
        if at not in longest_at or len(word) > len(longest_at[at]):
            longest_at[at] = word
    matches = sorted(longest_at.items(), key=lambda pair: pair[0])
    cue_start, cue = matches[0]
    cue_end = cue_start + len(cue)
    before_cue = source[clause.span.start:cue_start]
    for opening, closing in _QUOTE_PAIRS:
        if before_cue.rfind(opening) > before_cue.rfind(closing):
            return False
    if source[cue_end:clause.span.end].startswith((
            "とされた場合", "とされる場合", "と考えられた場合", "の場合", "ならば", "なら")):
        return False

    # A nominal verbal predicate can have its derivational noun immediately
    # before the native inflected span (noun + し/する).
    predicate_start = pred.start
    if clause.predicate.endswith("する") and clause.predicate[:-2]:
        stem = clause.predicate[:-2]
        if source[max(clause.span.start, pred.start - len(stem)):pred.start] == stem:
            predicate_start = pred.start - len(stem)
    if clause.predicate == pred.text + "する":
        pass
    elif clause.predicate.endswith("る") and clause.predicate[:-1] == pred.text:
        pass
    elif clause.predicate == "する":
        if pred.text not in ("し", "さ", "す", "せ", "する"):
            return False
    elif clause.predicate.endswith("する") and predicate_start < pred.start:
        pass
    elif clause.predicate != pred.text:
        return False

    # Check that the local predicate and explicitly typed roles cover every
    # lexical stem before the modal ending. Other clauses remain outside this
    # construction's body even though the native sentence span is preserved.
    local_start = min([predicate_start] + [r.span.start for r in clause.roles])
    covered = [(predicate_start, pred.end), (cue_start, cue_end)]
    covered.extend((r.span.start, r.span.end) for r in clause.roles)
    gap = source[pred.end:cue_start]
    if gap.startswith("こと") and len(gap) > 2 and gap[2] in "がはもを":
        covered.append((pred.end, pred.end + 2))
    allowed_chars = set("たてでいるあったないなかっませとにへがはもをれるらずぬ、，,. \n")
    for pos in range(local_start, cue_end):
        if any(a <= pos < b for a, b in covered):
            continue
        char = source[pos]
        code = ord(char)
        if ((0x4E00 <= code <= 0x9FFF) or (0x30A0 <= code <= 0x30FF)
                or char.isascii() and char.isalnum() or char not in allowed_chars):
            return False
    return True


register(Construction(
    name="modality",
    priority=70,
    reads=reads,
    licenses=licenses,
    refines=("record", "frame", "copula", "identity", "measure", "adnominal",
             "diathesis", "np_internal", "light_verb", "time_expr", "quantifier",
             "zero_subject", "te_chain", "connective_rel", "paren_gloss", "negation",
             "comparison", "giving"),
))
