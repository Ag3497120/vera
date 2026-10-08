"""Recover a locally licensed zero agent from one sentence-initial topic.

The rule is deliberately narrow: the topic has to be marked in the sentence,
the native frame has to leave its agent out, and every lexical token in the
frame scope has to belong to that topic, an existing case role, the predicate,
or a final nominal type phrase.
"""
from __future__ import annotations

from dataclasses import replace
import re
import unicodedata

from ..semantic_ir import Role, Span
from . import Construction, ConstructionContext, Reading, register


_REASONS = frozenset(("unlocated agent", "unrepresented source content"))
_TOPIC = "は"
_BLOCKING_PARTICLES = frozenset(("と", "に", "で", "へ", "から", "まで"))
_NOMINAL_POS = frozenset(("名詞", "代名詞", "接頭辞", "接尾辞", "形状詞"))
_TAIL_POS = frozenset(("名詞", "接頭辞", "接尾辞", "形状詞", "補助記号", "記号"))
_TAIL_PARTICLES = frozenset(("の",))
_BRACKETS = {"（": "）", "(": ")", "[": "]", "【": "】", "「": "」", "『": "』"}
_CLOSERS = {v: k for k, v in _BRACKETS.items()}
_STRUCTURAL_PARTICLES = (
    "において", "における", "によって", "に対して", "について", "として", "により",
    "ともに", "と共に", "から", "まで", "より", "には", "では", "は", "を",
    "に", "で", "と", "へ", "の", "も", "や", "か",
)
_PUNCT = frozenset(" \t\r\n。、，,・：:；;()（）[]【】「」『』〈〉《》<>!?！？〜～…—―‐-_/\\|#")


def _feature(token):
    return getattr(token, "feature", None)


def _field(token, name, default=""):
    return getattr(_feature(token), name, default)


def _surface(token):
    return getattr(token, "surface", str(token))


def _particle(tokens, index: int, lemma: str) -> bool:
    if not 0 <= index < len(tokens):
        return False
    token = tokens[index].token
    return (_field(token, "pos1") == "助詞" and _field(token, "lemma") == lemma)


def _balanced(text: str) -> bool:
    stack = []
    last_open = {}
    for i, char in enumerate(text):
        if char in _BRACKETS:
            stack.append(char)
            last_open[len(stack)] = i
        elif char in _CLOSERS:
            if not stack or stack.pop() != _CLOSERS[char]:
                return False
            if char == "】" and not text[last_open.pop(len(stack) + 1) + 1:i].strip():
                return False
            last_open.pop(len(stack) + 1, None)
    return not stack


def _topic(ctx: ConstructionContext) -> tuple[int, int] | None:
    """Return a sentence-local NP extent for a unique, direct topic marker."""
    tokens = ctx.tokens
    marks = [i for i, item in enumerate(tokens)
             if _field(item.token, "pos1") == "助詞"
             and _field(item.token, "pos2") == "係助詞"
             and _field(item.token, "lemma") == _TOPIC]
    if len(marks) != 1:
        return None
    mark_i = marks[0]
    mark = tokens[mark_i]
    if mark_i == 0 or _particle(tokens, mark_i - 1, "は"):
        return None
    if any(_particle(tokens, mark_i - 1, p) for p in _BLOCKING_PARTICLES):
        return None
    previous = tokens[mark_i - 1].token
    if (_field(previous, "pos1") not in _NOMINAL_POS
            and _surface(previous) not in _CLOSERS):
        return None

    nominal = [i for i in range(mark_i)
               if _field(tokens[i].token, "pos1") in _NOMINAL_POS]
    if not nominal:
        return None
    first_i = nominal[0]
    start = tokens[first_i].start
    raw_prefix = ctx.sentence_text[:start]
    if any(unicodedata.category(ch)[0] in ("L", "N") for ch in raw_prefix):
        return None
    topic_text = ctx.sentence_text[start:mark.start]
    if not topic_text.strip() or not _balanced(topic_text):
        return None

    depth = 0
    for item in tokens[first_i:mark_i]:
        token = item.token
        surface = _surface(token)
        if surface in _BRACKETS:
            depth += 1
            continue
        if surface in _CLOSERS:
            depth -= 1
            if depth < 0:
                return None
            continue
        pos1 = _field(token, "pos1")
        if depth:
            continue
        if pos1 == "助詞" and _field(token, "lemma") != "の":
            return None
        if pos1 in ("動詞", "助動詞", "形容詞"):
            return None
    if depth:
        return None

    if any(_particle(tokens, i, "が") for i in range(mark_i + 1, len(tokens))):
        return None
    return start, mark.start


def _nominal_tail(ctx: ConstructionContext, clause, pred_end: int) -> tuple[int, int] | None:
    """Read one comma-introduced nominal predicate complement, if present."""
    tokens = ctx.tokens
    comma = next((t for t in tokens if t.start >= pred_end and _surface(t.token) in ("、", ",")), None)
    if comma is None:
        return None
    last = len(ctx.sentence_text)
    while last > comma.end and ctx.sentence_text[last - 1].isspace():
        last -= 1
    if last > comma.end and ctx.sentence_text[last - 1] in "。.!！？?":
        last -= 1
    start = comma.end
    while start < last and ctx.sentence_text[start].isspace():
        start += 1
    if start >= last:
        return None
    tail_tokens = [t for t in tokens if t.start >= start and t.end <= last]
    if not tail_tokens:
        return None
    has_nominal = False
    for item in tail_tokens:
        pos1 = _field(item.token, "pos1")
        if pos1 in _TAIL_POS:
            if pos1 in _NOMINAL_POS:
                has_nominal = True
            continue
        if pos1 == "助詞" and _field(item.token, "lemma") in _TAIL_PARTICLES:
            continue
        return None
    if not has_nominal:
        return None
    return start, last


def _covered(start: int, end: int, ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(a <= start and end <= b for a, b in ranges)


def _lexical_coverage(ctx: ConstructionContext, clause, topic: tuple[int, int],
                      tail: tuple[int, int] | None) -> bool:
    base = ctx.sentence_span.start
    ranges = [(topic[0], topic[1]),
              (clause.predicate_span.start - base, clause.predicate_span.end - base)]
    ranges.extend((r.span.start - base, r.span.end - base) for r in clause.roles)
    if tail:
        ranges.append(tail)
    for item in ctx.tokens:
        pos1 = _field(item.token, "pos1")
        if _covered(item.start, item.end, tuple(ranges)):
            continue
        if pos1 in ("助詞", "補助記号", "記号"):
            continue
        if pos1 == "助動詞" and _field(item.token, "lemma") in ("た", "だ"):
            continue
        if (pos1 == "動詞" and _field(item.token, "pos2") == "非自立可能"
                and item.start >= clause.predicate_span.end - base):
            continue
        return False
    return True


def reads(ctx: ConstructionContext) -> Reading | None:
    if (len(ctx.tokens) > ctx.budget.max_tokens or len(ctx.clauses) > ctx.budget.max_steps
            or ctx.sentence_span.source != ctx.document_id
            or ctx.sentence_span.text != ctx.sentence_text
            or ctx.sentence_span.end - ctx.sentence_span.start != len(ctx.sentence_text)):
        return None
    spent = len(ctx.clauses) + len(ctx.tokens)
    if spent > ctx.budget.max_steps:
        return None

    same_source = [c for c in ctx.clauses if c.span.source == ctx.document_id]
    if len(same_source) > ctx.budget.max_clauses:
        return None
    in_sentence = [c for c in same_source
                   if c.span.start == ctx.sentence_span.start
                   and c.span.end == ctx.sentence_span.end]
    if len(in_sentence) != 1:
        return None
    clause = in_sentence[0]
    if (clause.rule != "frame" or not clause.unsupported
            or set(clause.unsupported) - _REASONS
            or not set(clause.unsupported) & _REASONS
            or any(r.name == "agent" for r in clause.roles)
            or any(r.name == "topic" for r in clause.roles)):
        return None
    if any(c is not clause for c in in_sentence):
        return None
    if (clause.polarity != "+" or clause.modality != "assert"
            or clause.span.text != ctx.sentence_text
            or not ctx.sentence_text.endswith(("。", "!", "！", "?", "？"))):
        return None

    subject = _topic(ctx)
    if subject is None:
        return None
    subject_start, subject_end = subject
    pred_start = clause.predicate_span.start - ctx.sentence_span.start
    pred_end = clause.predicate_span.end - ctx.sentence_span.start
    if not (0 <= subject_start < subject_end <= pred_start <= pred_end <= len(ctx.sentence_text)):
        return None

    for role in clause.roles:
        if (role.span.source != ctx.document_id or role.span.start < clause.span.start
                or role.span.end > clause.span.end
                or role.span.text != ctx.sentence_text[role.span.start - ctx.sentence_span.start:
                                                       role.span.end - ctx.sentence_span.start]):
            return None
    if any(r.span.end > clause.predicate_span.start for r in clause.roles):
        return None

    tail = _nominal_tail(ctx, clause, pred_end)
    if tail and any(r.name == "attribute" for r in clause.roles):
        return None
    if not _lexical_coverage(ctx, clause, subject, tail):
        return None

    subject_span = Span(ctx.document_id, ctx.sentence_span.start + subject_start,
                        ctx.sentence_span.start + subject_end,
                        ctx.sentence_text[subject_start:subject_end])
    roles = list(clause.roles)
    roles.append(Role("agent", subject_span.text, subject_span, "literal"))
    if tail:
        a, b = tail
        attr_span = Span(ctx.document_id, ctx.sentence_span.start + a,
                         ctx.sentence_span.start + b, ctx.sentence_text[a:b])
        roles.append(Role("attribute", attr_span.text, attr_span, "literal"))
    roles.sort(key=lambda r: (r.span.start, r.span.end, r.name))
    resolved = replace(clause, id=clause.id + ":zero_subject", roles=tuple(roles),
                       rule="zero_subject", unsupported=())
    return Reading((resolved,), (ctx.sentence_span,), ())


def _structural_gap(text: str) -> bool:
    i = 0
    while i < len(text):
        char = text[i]
        if char in _PUNCT or unicodedata.category(char)[0] in ("P", "S", "Z"):
            i += 1
            continue
        particle = next((p for p in _STRUCTURAL_PARTICLES if text.startswith(p, i)), None)
        if particle is None or particle in ("が", "は"):
            return False
        i += len(particle)
    return True


def _source_clause(clause, source: str) -> bool:
    span = clause.span
    if (not isinstance(source, str) or type(span.start) is not int or type(span.end) is not int
            or not 0 <= span.start < span.end <= len(source)
            or source[span.start:span.end] != span.text):
        return False
    raw = span.text
    if not raw.endswith(("。", "!", "！", "?", "？")):
        return False
    if clause.polarity != "+" or clause.modality != "assert" or not clause.predicate:
        return False
    ps = clause.predicate_span
    if (ps.source != span.source or ps.start < span.start or ps.end > span.end
            or ps.start >= ps.end or source[ps.start:ps.end] != ps.text):
        return False

    agents = [r for r in clause.roles if r.name == "agent"]
    if len(agents) != 1 or agents[0].rule != "literal":
        return False
    agent = agents[0]
    if (agent.span.source != span.source or agent.span.start < span.start
            or agent.span.end > ps.start or agent.span.start >= agent.span.end
            or source[agent.span.start:agent.span.end] != agent.span.text
            or agent.term != agent.span.text):
        return False
    marker = agent.span.end
    if marker >= ps.start or source[marker:marker + 1] != _TOPIC:
        return False
    if not _balanced(source[agent.span.start:marker]):
        return False
    prefix = source[span.start:agent.span.start]
    if any(unicodedata.category(ch)[0] in ("L", "N") for ch in prefix):
        return False

    # The source must have exactly this one top-level topic marker.
    depth = 0
    topics = []
    for i, char in enumerate(raw):
        if char in _BRACKETS:
            depth += 1
        elif char in _CLOSERS:
            depth -= 1
            if depth < 0:
                return False
        elif char == _TOPIC and depth == 0:
            topics.append(i + span.start)
    if depth or topics != [marker]:
        return False

    ranges = [(agent.span.start, marker + 1), (ps.start, ps.end)]
    if any(r.name == "topic" for r in clause.roles):
        return False
    attributes = [r for r in clause.roles if r.name == "attribute"]
    if len(attributes) > 1:
        return False
    for role in clause.roles:
        if (role.span.source != span.source or role.span.start < span.start
                or role.span.end > span.end or role.span.start >= role.span.end
                or source[role.span.start:role.span.end] != role.span.text):
            return False
        if role.rule == "literal" and role.term != role.span.text:
            return False
        if role.name != "agent":
            ranges.append((role.span.start, role.span.end))
    ranges.sort()
    cursor = span.start
    for start, end in ranges:
        if start < cursor:
            if end <= cursor:
                continue
            return False
        if not _structural_gap(source[cursor:start]):
            return False
        cursor = end
    if not _structural_gap(source[cursor:span.end]):
        return False

    if attributes:
        attribute = attributes[0]
        if attribute.rule != "literal" or attribute.span.start < ps.end:
            return False
        after_predicate = source[ps.end:attribute.span.start]
        if (not after_predicate.startswith(("、", ","))
                or any(ch in after_predicate[1:] for ch in ("。", "!", "！", "?", "？"))):
            return False
        tail = attribute.span.text
        if (not tail or not any(unicodedata.category(ch)[0] in ("L", "N") for ch in tail)
                or tail[-1] in "ぁぃぅぇぉゃゅょっァィゥェォャュョッー"):
            return False
        if any(p in tail for p in ("て", "た", "ない", "れる", "られる", "が", "を", "に", "で")):
            return False
    if re.match(r"(?:さ|ら)?れ", source[ps.end:span.end]):
        return False
    return True


def licenses(clause, source: str) -> bool:
    """Independently check the local topic and the clause's complete source scope."""
    return clause.rule == "zero_subject" and not clause.unsupported and _source_clause(clause, source)


register(Construction(name="zero_subject", priority=20, reads=reads, licenses=licenses,
                      refines=("frame",)))


__all__ = ("licenses", "reads")
