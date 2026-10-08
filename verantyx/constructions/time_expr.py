"""Source-bounded absolute and relative time adjuncts for finite event clauses."""
from __future__ import annotations

import hashlib
import re

from ..semantic_ir import Clause, Role, Span, Variable
from . import Construction, ConstructionContext, Reading, TypedNote, register


NAME = "time_expr"


class TimeValue(str):
    """A literal surface value carrying its time type without normalization."""

    def __new__(cls, value: str, granularity: str, kind: str, extent: str):
        instance = str.__new__(cls, value)
        instance.granularity = granularity
        instance.kind = kind
        instance.extent = extent
        return instance


_NUM = r"[0-9０-９]"
_YEAR = rf"(?:(?:令和|平成|昭和|大正|明治){_NUM}{{1,2}}|{_NUM}{{3,4}})年"
_ATOM = rf"(?:{_YEAR}(?:{_NUM}{{1,2}}月(?:{_NUM}{{1,2}}日)?)?|{_NUM}{{1,2}}月{_NUM}{{1,2}}日|{_NUM}{{1,2}}世紀(?:前半|中頃|後半)?|{_NUM}{{3,4}}年代(?:前半|後半)?)"
_ABSOLUTE = re.compile(
    rf"(?P<range>(?P<left>{_ATOM})から(?P<right>{_ATOM})まで)(?P<range_case>に|で)?"
    rf"|(?P<point>(?P<atom>{_ATOM}))(?P<point_case>に|で)"
)

_RELATIVE_TYPES = {
    "前年": "year", "翌年": "year", "同年": "year", "当年": "year",
    "昨年": "year", "今年": "year", "来年": "year",
    "前月": "month", "翌月": "month", "同月": "month", "当月": "month",
    "先月": "month", "今月": "month", "来月": "month",
    "前日": "day", "翌日": "day", "同日": "day", "当日": "day",
    "昨日": "day", "今日": "day", "明日": "day",
    "当時": "relative", "その時": "relative", "この時": "relative",
    "その後": "relative", "以後": "relative", "以前": "relative",
    "現在": "relative",
}
_RELATIVE = re.compile(
    rf"(?P<core>{'|'.join(sorted(map(re.escape, _RELATIVE_TYPES), key=len, reverse=True))})"
    rf"(?P<case>に|で|、)"
)

_FINITE_ENDINGS = (
    "されていた", "していた", "されている", "している",
    "された", "した", "される", "する",
)
_PAST_ENDINGS = frozenset(("されていた", "していた", "された", "した"))
_ICHIDAN_ENDINGS = (
    ("ていた", "past"), ("ている", "nonpast"),
    ("た", "past"), ("る", "nonpast"),
)
_BOUNDARIES = frozenset(("。", "、"))
_GRAMMATICAL_GAP = re.compile(
    r"(?:(?:において|における|によって|により|による|として|について|に対して|"
    r"と共に|ともに|から|まで|より|は|が|を|に|へ|で|と|の|も|や|て|"
    r"[、。？！・…（）()「」『』\s])*)\Z"
)
_CASE_MARKERS = (
    ("によって", "agent"), ("において", "context"), ("により", "agent"),
    ("による", "agent"), ("として", "capacity"), ("にて", "context"),
    ("から", "source"), ("より", "source"), ("は", "topic"),
    ("を", "patient"), ("で", "context"),
    ("へ", "goal"), ("と", "companion"),
)
_ROLE_MARKERS = {
    "topic": ("は",), "agent": ("によって", "により", "による"),
    "patient": ("を",), "source": ("から", "より"),
    "context": ("において", "にて", "で"), "capacity": ("として",),
    "goal": ("へ",), "companion": ("と",),
}


def _granularity(atom: str) -> str | None:
    if "世紀" in atom:
        return "century"
    if "年代" in atom:
        return "decade"
    if "年" in atom:
        if "日" in atom:
            return "day"
        if "月" in atom:
            return "month"
        return "year"
    if "月" in atom and "日" in atom:
        return "month_day"
    return None


def _inside_brackets(text: str, start: int, end: int) -> bool:
    for opening, closing in (("（", "）"), ("(", ")"), ("［", "］"), ("[", "]")):
        left = text.rfind(opening, 0, start)
        prior_close = text.rfind(closing, 0, start)
        if left > prior_close and text.find(closing, end) >= 0:
            return True
    return False


def _candidates(text: str):
    found: list[tuple[int, int, int, str, str, str]] = []
    for match in _ABSOLUTE.finditer(text):
        if match.group("range") is not None:
            core = match.group("range")
            left, right = match.group("left"), match.group("right")
            granularity = _granularity(left)
            if granularity is None or granularity != _granularity(right):
                continue
            extent = "range"
            case = match.group("range_case") or ""
        else:
            core = match.group("point")
            granularity = _granularity(core)
            if granularity is None:
                continue
            extent = "point"
            case = match.group("point_case")
        start, core_end, consume_end = match.start(), match.start() + len(core), match.end()
        if _inside_brackets(text, start, consume_end):
            continue
        found.append((start, core_end, consume_end, core, granularity, "absolute:" + extent))

    for match in _RELATIVE.finditer(text):
        core, case = match.group("core"), match.group("case")
        if _inside_brackets(text, match.start(), match.end()):
            continue
        found.append((match.start(), match.end() - len(case), match.end(), core,
                      _RELATIVE_TYPES[core], "relative:" + ("comma" if case == "、" else "point")))

    found.sort(key=lambda item: (item[0], -(item[2] - item[0])))
    selected = []
    occupied_until = -1
    for item in found:
        if item[0] < occupied_until:
            continue
        selected.append(item)
        occupied_until = item[2]
    return selected


def _event_end(text: str, start: int, stem: str, clause: Clause, sentence_offset: int):
    if not clause.predicate.endswith("する") or not stem:
        return None
    if text[start:start + len(stem)] != stem:
        return None
    for ending in _FINITE_ENDINGS:
        surface = stem + ending
        end = start + len(surface)
        if text.startswith(surface, start) and (end == len(text) or text[end] in _BOUNDARIES):
            marked = clause.predicate_span.start - sentence_offset
            if start <= marked < end and clause.predicate_span.text == text[marked:marked + len(clause.predicate_span.text)]:
                tense = "past" if ending in _PAST_ENDINGS else "nonpast"
                if clause.time == tense and clause.polarity == "+" and clause.modality == "assert":
                    return end
    return None


def _event_span(ctx: ConstructionContext, clause: Clause, sentence_offset: int):
    """Find a finite event surface from the parsed predicate and token morphology."""
    text = ctx.sentence_text
    pred_start = clause.predicate_span.start - sentence_offset
    pred_end = clause.predicate_span.end - sentence_offset
    stem = clause.predicate[:-2] if clause.predicate.endswith("する") else ""
    if stem:
        event_start = pred_start - len(stem)
        token = next((item for item in ctx.tokens if item.start == event_start), None)
        if (event_start < 0 or token is None or getattr(token.token, "surface", "") != stem):
            return None
        event_end = _event_end(text, event_start, stem, clause, sentence_offset)
        return (event_start, event_end) if event_end is not None else None

    if not clause.predicate.endswith("る"):
        return None
    token = next((item for item in ctx.tokens if item.start == pred_start), None)
    if token is None or getattr(token.token, "surface", "") != clause.predicate_span.text:
        return None
    feature = getattr(token.token, "feature", None)
    if getattr(feature, "pos1", "") != "動詞" or not any(
            form in getattr(feature, "cType", "") for form in ("上一段", "下一段")):
        return None
    stem = clause.predicate[:-1]
    for ending, tense in _ICHIDAN_ENDINGS:
        event_end = pred_start + len(stem + ending)
        if (text.startswith(stem + ending, pred_start)
                and pred_start <= pred_start < pred_end <= event_end
                and clause.time == tense
                and text[pred_start:pred_end] == clause.predicate_span.text):
            return pred_start, event_end
    return None


def _role_chain(ctx: ConstructionContext, start: int, end: int) -> tuple[Role, ...] | None:
    """Read literal constituents only when each closes with an explicit case marker."""
    if start == end:
        return ()
    text = ctx.sentence_text
    cursor = start
    roles = []
    while cursor < end:
        hit = None
        for pos in range(cursor + 1, end):
            for marker, name in _CASE_MARKERS:
                if text.startswith(marker, pos) and pos + len(marker) <= end:
                    hit = (pos, marker, name)
                    break
            if hit is not None:
                break
        if hit is None:
            if _GRAMMATICAL_GAP.fullmatch(text[cursor:end]):
                return tuple(roles)
            return None
        pos, marker, name = hit
        term_start, term_end = cursor, pos
        while term_start < term_end and text[term_start] in "、 ， \t　":
            term_start += 1
        while term_end > term_start and text[term_end - 1] in "、 ， \t　":
            term_end -= 1
        if term_start == term_end:
            return None
        term = text[term_start:term_end]
        if any(mark in term for mark in "。？！"):
            return None
        # A constituent that swallows a が/は-marked phrase (<noun>が<noun>) is two constituents; this char scan cannot split them.
        if any(item.start >= term_start and item.end <= term_end and item.token.feature.pos1 == "助詞"
               and item.token.surface in ("が", "は") for item in ctx.tokens):
            return None
        span = Span(ctx.sentence_span.source, ctx.sentence_span.start + term_start,
                    ctx.sentence_span.start + term_end, term)
        roles.append(Role(name, term, span, "literal"))
        cursor = pos + len(marker)
        while cursor < end and text[cursor] in "、 ， \t　":
            cursor += 1
    return tuple(roles)


def reads(ctx: ConstructionContext) -> Reading | None:
    if len(ctx.tokens) > ctx.budget.max_tokens or len(ctx.sentence_text) > 4096:
        return None
    candidates = _candidates(ctx.sentence_text)
    if not candidates:
        return None
    source = ctx.sentence_span.source
    offset = ctx.sentence_span.start
    sentence_end = offset + len(ctx.sentence_text)
    local_clauses = tuple(
        clause for clause in ctx.clauses
        if clause.predicate_span.source == source
        and offset <= clause.predicate_span.start < sentence_end
        and clause.predicate_span.end <= sentence_end
    )
    if len(local_clauses) > ctx.budget.max_clauses:
        return None
    clauses: list[Clause] = []
    consumed: list[Span] = []
    notes: list[TypedNote] = []
    claimed: set[str] = set()
    steps = 0
    for start, core_end, consume_end, core, granularity, kind_extent in candidates:
        kind, extent = kind_extent.split(":", 1)
        value = TimeValue(core, granularity, kind, "range" if extent == "range" else "point")
        for base in local_clauses:
            steps += 1
            if steps > ctx.budget.max_steps:
                return None
            if (base.id in claimed or base.rule != "frame" or not base.unsupported
                    or base.conditions or base.exceptions or base.exception_of
                    or base.predicate_span.source != source):
                continue
            event = _event_span(ctx, base, offset)
            if event is None:
                continue
            event_start, event_end = event
            if event_start < consume_end:
                continue
            middle_roles = _role_chain(ctx, consume_end, event_start)
            if middle_roles is None:
                continue
            scope_start = base.span.start - offset
            scope_end = base.span.end - offset
            if not (0 <= scope_start <= start < consume_end <= event_start < event_end <= scope_end):
                continue
            # A date can modify one event only when this native clause contains
            # exactly one time expression and one predicate. Multiple dates or
            # events need a relation that this construction does not infer.
            in_scope = [other for other in local_clauses
                        if base.span.start <= other.predicate_span.start < base.span.end]
            in_time = [candidate for candidate in candidates
                       if scope_start <= candidate[0] < candidate[2] <= scope_end]
            if len(in_scope) != 1 or in_scope[0].predicate_span != base.predicate_span or len(in_time) != 1:
                continue
            if extent == "range" and ctx.sentence_text[consume_end:consume_end + 1] == "の":
                # A range followed by a genitive particle is modifying a noun,
                # as in “期間を指す”, rather than locating the event in time.
                continue
            prefix_roles = _role_chain(ctx, scope_start, start)
            if prefix_roles is None:
                continue
            suffix_roles = _role_chain(ctx, event_end, scope_end)
            if suffix_roles is None:
                continue
            all_roles = (*prefix_roles, *middle_roles, *suffix_roles)
            role_names = [role.name for role in all_roles]
            if len(role_names) != len(set(role_names)):
                continue
            abs_start, abs_end = offset + scope_start, offset + scope_end
            role_span = Span(source, offset + start, offset + core_end, core)
            roles = (*all_roles, Role("time", value, role_span, "literal"))
            span = Span(source, abs_start, abs_end, ctx.sentence_text[scope_start:scope_end])
            digest = hashlib.sha256(
                f"{source}\0{abs_start}\0{abs_end}\0{base.predicate}\0{core}".encode("utf-8")
            ).hexdigest()[:24]
            clauses.append(Clause(
                id=digest, event=Variable(name="event_" + digest, sort="event"), predicate=base.predicate,
                predicate_span=base.predicate_span, roles=roles, span=span, body_span=span,
                polarity=base.polarity, modality=base.modality, time=base.time,
                rule=NAME, sovereign=base.sovereign, family=base.family,
            ))
            consumed.append(span)
            claimed.add(base.id)
            if kind == "relative":
                notes.append(TypedNote("relative_time", role_span,
                                       "kept relative; no absolute date inferred"))
            break
    if not clauses:
        return None
    return Reading(tuple(clauses), tuple(consumed), tuple(notes))


def _license_granularity(atom: str) -> str | None:
    if "世紀" in atom:
        return "century"
    if atom.endswith("年代") or atom.endswith("年代前半") or atom.endswith("年代後半"):
        return "decade"
    if "年" in atom:
        return "day" if "日" in atom else "month" if "月" in atom else "year"
    if atom.endswith("日") and "月" in atom:
        return "month_day"
    return None


def _licensed_time(core: str):
    if core in _RELATIVE_TYPES:
        return "relative", _RELATIVE_TYPES[core], "point"
    if "から" in core and core.endswith("まで"):
        left, right = core[:-2].split("から", 1)
        left_type, right_type = _license_granularity(left), _license_granularity(right)
        if left_type is not None and left_type == right_type:
            return "absolute", left_type, "range"
        return None
    value_type = _license_granularity(core)
    if value_type is not None:
        return "absolute", value_type, "point"
    return None


def licenses(clause: Clause, source: str) -> bool:
    if (clause.rule != NAME or clause.unsupported or clause.event.sort != "event"
            or clause.polarity != "+" or clause.modality != "assert"
            or clause.time not in ("past", "nonpast") or clause.conditions or clause.exceptions
            or clause.exception_of):
        return False
    if (clause.span.source != clause.predicate_span.source
            or not clause.span.valid({clause.span.source: source})
            or not clause.predicate_span.valid({clause.span.source: source})):
        return False
    time_roles = [role for role in clause.roles if role.name == "time"]
    other_roles = [role for role in clause.roles if role.name != "time"]
    if len(time_roles) != 1 or any(role.name not in _ROLE_MARKERS for role in other_roles):
        return False
    role = time_roles[0]
    if (role.rule != "literal" or not isinstance(role.term, TimeValue)
            or not role.span.valid({role.span.source: source}) or role.span.source != clause.span.source
            or not (clause.span.start <= role.span.start < role.span.end <= clause.span.end)
            or str(role.term) != role.span.text):
        return False
    typed_time = _licensed_time(role.span.text)
    if typed_time is None or (role.term.kind, role.term.granularity, role.term.extent) != typed_time:
        return False

    text = clause.span.text
    time_end = role.span.end - clause.span.start
    marker = ""
    after_time = text[time_end:]
    if after_time.startswith(("に", "で")):
        marker = after_time[0]
    elif typed_time[0] == "relative" and after_time.startswith("、"):
        marker = "、"
    elif typed_time[2] == "point":
        return False
    if typed_time[0] == "relative" and marker not in ("に", "で", "、"):
        return False
    if typed_time[0] == "absolute" and marker == "、":
        return False
    if typed_time[2] == "range" and after_time.startswith("の"):
        return False

    pred_start = clause.predicate_span.start - clause.span.start
    pred_end = pred_start + len(clause.predicate_span.text)
    stem = clause.predicate[:-2] if clause.predicate.endswith("する") else ""
    ichidan_stem = clause.predicate[:-1] if not stem and clause.predicate.endswith("る") else ""
    event_start = pred_start - len(stem) if stem else pred_start
    event_end = None
    if stem:
        ending = None
        for candidate in _FINITE_ENDINGS:
            stop = event_start + len(stem) + len(candidate)
            if (event_start >= 0 and text[event_start:stop] == stem + candidate
                    and event_start >= time_end + len(marker)
                    and event_start + len(stem) <= pred_start < stop):
                event_end, ending = stop, candidate
                break
        expected_time = "past" if ending in _PAST_ENDINGS else "nonpast"
    elif ichidan_stem:
        # Independently verify the regular 一段 finite forms from the stored
        # predicate and source; the reader additionally checks the token class.
        forms = (("ていた", "past"), ("ている", "nonpast"),
                 ("た", "past"), ("る", "nonpast"))
        expected_time = ""
        for candidate, tense in forms:
            stop = event_start + len(ichidan_stem + candidate)
            if (text[event_start:stop] == ichidan_stem + candidate
                    and pred_start < pred_end <= stop
                    and event_start >= time_end + len(marker)):
                event_end, expected_time = stop, tense
                break
    else:
        return False
    if (event_end is None or not expected_time or clause.time != expected_time
            or text[pred_start:pred_end] != clause.predicate_span.text):
        return False
    if clause.body_span is not None and clause.body_span != clause.span:
        return False

    intervals = [(role.span.start - clause.span.start, role.span.end - clause.span.start)]
    for other in other_roles:
        if (other.rule != "literal" or not isinstance(other.term, str)
                or other.span.source != clause.span.source or not other.span.valid({other.span.source: source})
                or not (clause.span.start <= other.span.start < other.span.end <= clause.span.end)
                or str(other.term) != other.span.text):
            return False
        other_end = other.span.end - clause.span.start
        case = next((item for item in _ROLE_MARKERS[other.name]
                     if text.startswith(item, other_end)), None)
        if case is None:
            return False
        intervals.append((other.span.start - clause.span.start, other_end))
    intervals.append((event_start, event_end))
    intervals.sort()
    cursor = 0
    for left, right in intervals:
        if left < cursor or not _GRAMMATICAL_GAP.fullmatch(text[cursor:left]):
            return False
        cursor = right
    if not _GRAMMATICAL_GAP.fullmatch(text[cursor:]):
        return False
    prev = source[clause.span.start - 1:clause.span.start] if clause.span.start else ""
    return ((not prev or prev in _BOUNDARIES)
            and (text.endswith(("。", "、")) or clause.span.end == len(source)))


register(Construction(name=NAME, priority=20, reads=reads, licenses=licenses))
