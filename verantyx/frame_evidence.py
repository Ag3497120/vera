"""Source-grounded evidence sidecar for the existing Japanese Frame reader.

The sidecar leaves :mod:`frames` and ``Frame.key`` unchanged.  It records
source token offsets and where Frame values came from, while keeping topic,
relative-head, cleft, cross-clause and omitted roles distinct.

Offsets are Python Unicode code-point offsets into the unchanged source text,
using half-open ``[start, end)`` ranges.  A text span alone does not license a
semantic role or make a quoted/conditional event an assertion.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, replace
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import frames
from .typed_edges import _NEG_LEMMA, _base, _tagger


@dataclass(frozen=True)
class SourceSpan:
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class GapEvidence:
    """A non-token source interval; whitespace is explicit, other gaps held."""

    span: Optional[SourceSpan]
    classification: str
    left_token_index: Optional[int]
    right_token_index: Optional[int]


@dataclass(frozen=True)
class TokenEvidence:
    index: int
    surface: str
    base: str
    pos1: str
    pos2: str
    span: Optional[SourceSpan]


@dataclass(frozen=True)
class FrameSnapshot:
    """Immutable copy of the existing Frame fields."""

    predicate: str
    agent: str
    patient: str
    recipient: str
    negated: bool
    past: bool
    ambiguous: bool
    inferred: bool

    def key(self) -> Tuple[str, str, str, str, bool]:
        return (self.predicate, self.agent, self.patient, self.recipient,
                self.negated)


@dataclass(frozen=True)
class ArgumentEvidence:
    """One observed case phrase or one explicit Frame-role gap.

    ``span`` is the exact noun-phrase surface and excludes its case marker.
    ``value`` is the normalized phrase used by the old Frame reader.
    ``owner_frame_id`` names the Frame this record is attached to;
    ``source_frame_id`` may be an ordinal-only hypothesis for a carried topic.
    ``permitted`` licenses only this role-to-source binding; it never upgrades
    the clause's assertion status or states that an event is true.
    """

    role: str
    value: str
    span: Optional[SourceSpan]
    case_particle: Optional[str]
    particle_span: Optional[SourceSpan]
    owner_frame_id: str
    source_frame_id: Optional[str]
    origin: str
    permitted: bool
    evidence: str
    binding_status: str = "UNKNOWN"
    source_owner_status: str = "UNKNOWN"
    argument_quote_status: str = "UNKNOWN"
    case_quote_status: str = "NOT_APPLICABLE"
    binding_quote_status: str = "UNKNOWN"


@dataclass(frozen=True)
class ClauseEvidence:
    """Per-predicate record; proposition scope is separate from local morphology."""

    clause_id: str
    frame_id: str
    ordinal: int
    predicate: str
    predicate_span: Optional[SourceSpan]
    scope_span: Optional[SourceSpan]
    negation_spans: Tuple[SourceSpan, ...]
    polarity: str
    scope_status: str
    quote_status: str
    assertion_status: str
    quote_span: Optional[SourceSpan]
    frame: Optional[FrameSnapshot]
    arguments: Tuple[ArgumentEvidence, ...]
    alignment_status: str
    local_polarity: str
    local_scope_status: str
    local_scope_span: Optional[SourceSpan]
    scope_reason: str
    source_coverage_status: str


@dataclass(frozen=True)
class FrameEvidenceDocument:
    """Per-source evidence, with token positions distinct from source coverage."""

    source_id: str
    source_sha256: str
    source_text: str
    tokens: Tuple[TokenEvidence, ...]
    clauses: Tuple[ClauseEvidence, ...]
    unmatched_frames: Tuple[FrameSnapshot, ...]
    alignment_status: str
    reader_order_alignment_status: str
    token_positions_complete: bool
    source_gaps: Tuple[GapEvidence, ...]
    source_coverage_status: str

    @property
    def token_offsets_complete(self) -> bool:
        """Deprecated r1 alias: every emitted token has a located source span.

        This says nothing about whitespace or other source intervals; use
        ``source_coverage_status`` and ``source_gaps`` for source coverage.
        """
        return self.token_positions_complete

    def as_dict(self) -> Dict[str, Any]:
        """Return a JSON-friendly representation with stable field order."""
        return asdict(self)


@dataclass(frozen=True)
class _CaseMention:
    token_index: int
    start_token_index: int
    value: str
    particle: str
    span: Optional[SourceSpan]
    particle_span: Optional[SourceSpan]


_CASES = frozenset(("が", "を", "に", "へ", "から", "で", "は"))
_ROLE_NAMES = ("agent", "patient", "recipient")
_OPEN_QUOTES = {"「": "」", "『": "』", "“": "”"}
_CLOSE_QUOTES = {close: open_ for open_, close in _OPEN_QUOTES.items()}
_COMPLEMENT_MARKERS = frozenset(("と", "って", "こと", "の", "か", "もの", "よう"))
_CLEAR_COORDINATION = frozenset(("て", "で", "ず", "たり", "り", "ながら", "つつ", "、"))


def _span(text: str, start: int, end: int) -> Optional[SourceSpan]:
    if start < 0 or end < start or end > len(text):
        return None
    return SourceSpan(start, end, text[start:end])


def _position_tokens(text: str):
    """Return Fugashi tokens with monotonic source offsets when locatable."""
    positioned = []
    cursor = 0
    complete = True
    for word in _tagger()(text):
        at = text.find(word.surface, cursor)
        if at < 0:
            complete = False
            token_span = None
        else:
            token_span = _span(text, at, at + len(word.surface))
            cursor = at + len(word.surface)
            if token_span is None:
                complete = False
        positioned.append((word, token_span))
    return positioned, complete


def _source_coverage(text: str, positioned):
    """Describe every interval outside token spans, including source suffixes."""
    gaps = []
    missing = {index for index, (_word, token_span) in enumerate(positioned)
               if token_span is None}
    cursor = 0
    left_token_index = None
    located = [(index, token_span) for index, (_word, token_span)
               in enumerate(positioned) if token_span is not None]
    for index, token_span in located:
        if token_span.text != text[token_span.start:token_span.end]:
            gaps.append(GapEvidence(token_span, "UNKNOWN_TOKEN_POSITION",
                                    left_token_index, index))
            missing.add(index)
            continue
        if token_span.start < cursor:
            gaps.append(GapEvidence(token_span, "UNKNOWN_TOKEN_POSITION",
                                    left_token_index, index))
            missing.add(index)
            continue
        if token_span.start > cursor:
            gap_span = _span(text, cursor, token_span.start)
            has_missing_token = any(
                missing_index in missing
                for missing_index in range((left_token_index + 1)
                                           if left_token_index is not None else 0,
                                           index)
            )
            kind = ("UNKNOWN_TOKEN_POSITION" if has_missing_token else
                    "WHITESPACE" if gap_span is not None and gap_span.text.isspace()
                    else "UNKNOWN_NONWHITESPACE")
            gaps.append(GapEvidence(gap_span, kind, left_token_index, index))
        cursor = token_span.end
        left_token_index = index

    if cursor < len(text):
        gap_span = _span(text, cursor, len(text))
        has_missing_token = any(index > (left_token_index if left_token_index is not None else -1)
                                for index in missing)
        kind = ("UNKNOWN_TOKEN_POSITION" if has_missing_token else
                "WHITESPACE" if gap_span is not None and gap_span.text.isspace()
                else "UNKNOWN_NONWHITESPACE")
        gaps.append(GapEvidence(gap_span, kind, left_token_index, None))

    if missing:
        represented_missing = {index for gap in gaps
                               if gap.classification == "UNKNOWN_TOKEN_POSITION"
                               for index in range((gap.left_token_index + 1)
                                                  if gap.left_token_index is not None else 0,
                                                  gap.right_token_index
                                                  if gap.right_token_index is not None
                                                  else len(positioned))}
        if not missing.issubset(represented_missing):
            gaps.append(GapEvidence(None, "UNKNOWN_TOKEN_POSITION",
                                    min(missing), max(missing) + 1
                                    if max(missing) + 1 < len(positioned) else None))
        return tuple(gaps), "UNKNOWN_TOKEN_POSITIONS"
    if any(gap.classification == "UNKNOWN_NONWHITESPACE" for gap in gaps):
        return tuple(gaps), "UNKNOWN_NONWHITESPACE"
    if gaps:
        return tuple(gaps), "WHITESPACE_ONLY"
    return tuple(gaps), "EXACT"


def _as_token_evidence(positioned) -> Tuple[TokenEvidence, ...]:
    records = []
    for index, (word, token_span) in enumerate(positioned):
        feature = word.feature
        records.append(TokenEvidence(
            index=index,
            surface=word.surface,
            base=_base(word),
            pos1=str(feature.pos1),
            pos2=str(feature.pos2),
            span=token_span,
        ))
    return tuple(records)


def _noun_start(toks: Sequence[Any], end_index: int) -> Optional[int]:
    """Start token for the NP shape used by ``frames._noun_run_back``."""
    if end_index < 0 or end_index >= len(toks):
        return None
    parts, before = frames._run_back(toks, end_index)
    if not parts:
        return None
    start = end_index - len(parts) + 1
    if before >= 0 and toks[before].feature.pos1 == "形容詞" \
            and str(toks[before].feature.cForm).startswith("連体形"):
        start = before
        before -= 1
    elif before >= 1 and toks[before].surface == "な" \
            and toks[before - 1].feature.pos1 == "形状詞":
        start = before - 1
        before -= 2

    current_value = frames._noun_run_back(toks, end_index)
    while before >= 1 and toks[before].surface == "の" \
            and toks[before - 1].feature.pos1 in ("名詞", "接尾辞"):
        left, left_before = frames._run_back(toks, before - 1)
        if not left:
            break
        left_value = "".join(token.surface for token in left)
        # Match the reader's apposition convention: 医師の小林 -> 小林.
        if frames.is_role(left_value) and not frames.is_role(current_value):
            break
        start = before - len(left)
        current_value = left_value + "の" + current_value
        before = left_before
    return start


def _case_mentions(toks: Sequence[Any], positioned, source: str) -> Tuple[_CaseMention, ...]:
    records = []
    for index, token in enumerate(toks):
        if token.feature.pos1 != "助詞" or token.surface not in _CASES or index == 0:
            continue
        value = frames._noun_run_back(toks, index - 1)
        if not value:
            continue
        start_index = _noun_start(toks, index - 1)
        phrase_span = None
        if start_index is not None:
            first = positioned[start_index][1]
            last = positioned[index - 1][1]
            if first is not None and last is not None:
                phrase_span = _span(source, first.start, last.end)
        records.append(_CaseMention(
            index, start_index if start_index is not None else index - 1,
            value, token.surface, phrase_span, positioned[index][1]))
    return tuple(records)


def _negative_indices(toks: Sequence[Any], index: int) -> Tuple[int, ...]:
    """Find negative morphemes in the exact auxiliary chain Frame checks."""
    found = []
    j = index + 1
    while j < len(toks):
        token = toks[j]
        pos = token.feature.pos1
        if (pos == "助動詞"
                or (pos == "形容詞" and token.feature.pos2 == "非自立可能")
                or (pos == "動詞" and token.feature.pos2 == "非自立可能")
                or (pos == "助詞" and token.surface in ("て", "は", "も"))):
            lemma = getattr(token.feature, "lemma", "") or ""
            if (_base(token) in _NEG_LEMMA or lemma in _NEG_LEMMA
                    or token.surface == "ん"):
                found.append(j)
            j += 1
            continue
        break
    return tuple(found)


def _is_negative_token(token) -> bool:
    if token.feature.pos1 not in ("助動詞", "形容詞"):
        return False
    lemma = getattr(token.feature, "lemma", "") or ""
    return (_base(token) in _NEG_LEMMA or lemma in _NEG_LEMMA
            or token.surface == "ん")


def _quote_state(text: str, at: Optional[int]):
    """Conservatively classify Japanese quote scope at one source offset."""
    if at is None:
        return "UNKNOWN", None
    stack: List[Tuple[str, int]] = []
    regions = []
    unmatched_close_before = False
    for index, char in enumerate(text):
        if char in _OPEN_QUOTES:
            stack.append((char, index))
        elif char in _CLOSE_QUOTES:
            if stack and stack[-1][0] == _CLOSE_QUOTES[char]:
                opening, start = stack.pop()
                regions.append((start, index + 1, opening))
            elif index <= at:
                unmatched_close_before = True
    for start, end, _opening in regions:
        if start <= at < end:
            return "QUOTED", _span(text, start, end)
    if unmatched_close_before or any(start <= at for _opening, start in stack):
        return "UNKNOWN", None
    return "UNQUOTED", None


def _quote_state_for_span(text: str, span: Optional[SourceSpan]):
    """Classify the whole span, not only its first code point."""
    if span is None:
        return "UNKNOWN", None
    status, quote_span = _quote_state(text, span.start)
    if status == "QUOTED":
        if quote_span is None or span.start < quote_span.start or span.end > quote_span.end:
            return "CROSSES_QUOTE_SCOPE", None
        return status, quote_span
    if status == "UNQUOTED":
        if any(char in _OPEN_QUOTES or char in _CLOSE_QUOTES
               for char in span.text):
            return "CROSSES_QUOTE_SCOPE", None
        return status, None
    return "UNKNOWN", None


def _binding_quote_status(predicate_status: str, predicate_quote_span,
                          argument_status: str, argument_quote_span,
                          case_status: str, case_quote_span) -> str:
    statuses = [predicate_status, argument_status]
    quote_spans = [predicate_quote_span, argument_quote_span]
    if case_status != "NOT_APPLICABLE":
        statuses.append(case_status)
        quote_spans.append(case_quote_span)
    if "CROSSES_QUOTE_SCOPE" in statuses:
        return "CROSSES_QUOTE_SCOPE"
    if "UNKNOWN" in statuses:
        return "UNKNOWN"
    if all(status == "UNQUOTED" for status in statuses):
        return "UNQUOTED"
    if all(status == "QUOTED" for status in statuses):
        signatures = {(span.start, span.end) if span is not None else None
                      for span in quote_spans}
        return "QUOTED" if len(signatures) == 1 else "CROSSES_QUOTE_SCOPE"
    return "CROSSES_QUOTE_SCOPE"


def _scope_context_reason(toks, predicate_index: int,
                          next_predicate_index: int, quote_status: str,
                          next_predicate_surface: Optional[str] = None,
                          following_argument_index: Optional[int] = None) -> str:
    if quote_status == "QUOTED":
        return "QUOTED_PROPOSITION_SCOPE_UNVERIFIED"
    if quote_status == "UNKNOWN":
        return "QUOTE_SCOPE_UNKNOWN"
    next_start = next_predicate_index
    if (next_predicate_surface and next_predicate_index > 0
            and _base(toks[next_predicate_index]) == "する"
            and toks[next_predicate_index - 1].feature.pos1 == "名詞"
            and _base(toks[next_predicate_index - 1]) + "する"
                == next_predicate_surface):
        next_start -= 1
    context_end = (min(next_start, following_argument_index)
                   if following_argument_index is not None else next_start)
    between = toks[predicate_index + 1:context_end]
    if any(token.surface in _COMPLEMENT_MARKERS for token in between):
        return "COMPLEMENT_OR_EMBEDDING_SCOPE_UNRESOLVED"
    if any(token.surface in ("。", "！", "？", "!", "?") for token in between):
        return "UNEMBEDDED_LOCAL_SCOPE"
    if next_predicate_index < len(toks):
        if between and all(token.surface in _CLEAR_COORDINATION for token in between):
            return "COORDINATED_LOCAL_SCOPE"
        return "NONFINAL_CLAUSE_SCOPE_UNRESOLVED"
    return "UNEMBEDDED_LOCAL_SCOPE"


def _annotate_argument_scopes(source: str, arguments, predicate_span,
                              predicate_quote_status: str, predicate_quote_span,
                              source_coverage_status: str):
    predicate_status, predicate_region = _quote_state_for_span(source, predicate_span)
    if predicate_status == "UNKNOWN" and predicate_quote_status != "UNKNOWN":
        predicate_status = predicate_quote_status
        predicate_region = predicate_quote_span
    safe_coverage = source_coverage_status in ("EXACT", "WHITESPACE_ONLY")
    annotated = []
    for argument in arguments:
        argument_status, argument_region = _quote_state_for_span(source, argument.span)
        if argument.particle_span is None:
            case_status, case_region = "NOT_APPLICABLE", None
        else:
            case_status, case_region = _quote_state_for_span(source, argument.particle_span)
        binding_status = _binding_quote_status(
            predicate_status, predicate_region,
            argument_status, argument_region,
            case_status, case_region,
        )
        permission = (argument.permitted and binding_status == "UNQUOTED"
                      and safe_coverage and argument.binding_status == "UNIQUE")
        evidence = argument.evidence
        if binding_status != "UNQUOTED" and argument.binding_status == "UNIQUE":
            evidence += "; predicate/argument/case quote scopes do not all match as unquoted"
        if not safe_coverage and argument.value:
            evidence += "; unknown non-whitespace source gap holds binding"
            if argument.binding_status != "AMBIGUOUS":
                argument_status_kind = "UNKNOWN"
            else:
                argument_status_kind = "AMBIGUOUS"
        else:
            argument_status_kind = argument.binding_status
        source_owner_status = {
            "EXPLICIT_CASE": "LOCAL_TOKEN_WINDOW",
            "TOPIC_INFERENCE": "INFERRED_LOCAL",
            "RELATIVE_HEAD_INFERENCE": "INFERRED_LOCAL",
            "CLEFT_FOCUS_INFERENCE": "INFERRED_LOCAL",
            "INTERCLAUSE_BORROW": "ORDER_HYPOTHESIS",
            "OMITTED": "NONE",
            "UNKNOWN": "UNKNOWN",
        }.get(argument.origin, "UNKNOWN")
        annotated.append(replace(
            argument,
            permitted=permission,
            evidence=evidence,
            binding_status=argument_status_kind,
            source_owner_status=source_owner_status,
            argument_quote_status=argument_status,
            case_quote_status=case_status,
            binding_quote_status=binding_status,
        ))
    return tuple(annotated)


def _frame_snapshot(frame) -> FrameSnapshot:
    return FrameSnapshot(
        predicate=frame.predicate,
        agent=frame.agent,
        patient=frame.patient,
        recipient=frame.recipient,
        negated=bool(frame.negated),
        past=bool(frame.past),
        ambiguous=bool(frame.ambiguous),
        inferred=bool(frame.inferred),
    )


def _source_key(source_id: str, source_sha256: str) -> str:
    return hashlib.sha256((source_id + "\0" + source_sha256).encode("utf-8")).hexdigest()[:16]


def _voice(toks: Sequence[Any], predicate_index: int) -> str:
    if predicate_index + 1 < len(toks):
        following = _base(toks[predicate_index + 1])
        if following in ("れる", "られる"):
            return "passive"
    return "active_or_transformed"


def _candidate_role(case: _CaseMention, frame, predicate_surface: str,
                    voice: str) -> Optional[str]:
    """Role from closed case/voice rules, only when Frame agrees exactly."""
    if case.particle == "は":
        return None
    if case.particle == "を":
        role = "patient"
    elif case.particle == "が":
        if voice == "passive":
            role = "patient"
        elif predicate_surface in frames.CONVERSE \
                and frame.predicate == frames.CONVERSE[predicate_surface]:
            role = "recipient"
        else:
            role = "agent"
    elif case.particle in ("に", "から"):
        if voice == "passive":
            role = ("recipient" if case.particle == "に"
                    and frame.recipient == case.value else "agent")
        elif predicate_surface in frames.CONVERSE \
                and frame.predicate == frames.CONVERSE[predicate_surface]:
            role = "agent"
        else:
            role = "recipient" if case.particle == "に" else None
    elif case.particle == "へ":
        role = "recipient"
    else:
        return None
    return role if role and getattr(frame, role, "") == case.value else None


def _cleft_mention(toks, positioned, source, predicate_index, value):
    """Locate a cleft focus only when its normalized text matches the Frame."""
    for j in range(predicate_index + 1, len(toks) - 1):
        if toks[j].surface != "の" or toks[j + 1].surface != "は":
            continue
        end = j + 2
        while end < len(toks) and (toks[end].feature.pos1 in ("名詞", "接尾辞")
                                   or toks[end].surface in ("の", "・")
                                   or frames._is_verb_in_noun(toks, end)):
            end += 1
        if end <= j + 2 or frames._noun_run_back(toks, end - 1) != value:
            return None
        start_index = _noun_start(toks, end - 1)
        if start_index is None:
            return None
        first = positioned[start_index][1]
        last = positioned[end - 1][1]
        if first is None or last is None:
            return None
        return (_span(source, first.start, last.end),
                _span(source, positioned[j][1].start,
                      positioned[j + 1][1].end)
                if positioned[j][1] is not None
                and positioned[j + 1][1] is not None else None)
    return None


def _relative_span(source, positioned, predicate_index, next_predicate_index, value):
    """Locate a unique exact relative-head surface after the predicate."""
    predicate_span = positioned[predicate_index][1]
    if predicate_span is None:
        return None
    next_span = (positioned[next_predicate_index][1]
                 if next_predicate_index < len(positioned) else None)
    left = predicate_span.end
    right = next_span.start if next_span is not None else len(source)
    hits = []
    at = source.find(value, left, right)
    while at >= 0:
        hits.append(at)
        at = source.find(value, at + max(1, len(value)), right)
    return _span(source, hits[0], hits[0] + len(value)) if len(hits) == 1 else None


def _predicate_surface_span(source, toks, positioned, predicate_index, frame):
    """Include the nominal stem of a サ変 predicate when the reader did."""
    start_index = predicate_index
    if predicate_index > 0 and _base(toks[predicate_index]) == "する":
        previous = toks[predicate_index - 1]
        if (previous.feature.pos1 == "名詞"
                and _base(previous) + "する" == frame.predicate):
            start_index = predicate_index - 1
    first = positioned[start_index][1]
    last = positioned[predicate_index][1]
    if first is None or last is None:
        return None
    return _span(source, first.start, last.end)


def _build_arguments(source: str, toks, positioned, mentions,
                     predicate_index: int, previous_predicate_index: int,
                     next_predicate_index: int, frame, frame_id: str,
                     frame_ids: Sequence[str], predicate_indices: Sequence[int],
                     predicate_surface: str, scope_known: bool,
                     quote_status: str) -> Tuple[ArgumentEvidence, ...]:
    start = previous_predicate_index + 1
    local = [m for m in mentions if start <= m.token_index < predicate_index]
    voice = _voice(toks, predicate_index)
    args: List[ArgumentEvidence] = []
    mapped_roles = set()
    candidate_roles = {}
    for mention in local:
        if mention.particle == "は":
            matching = [name for name in _ROLE_NAMES
                        if getattr(frame, name) == mention.value]
            candidate_roles[mention.token_index] = (
                matching[0] if len(matching) == 1 else None)
        else:
            candidate_roles[mention.token_index] = _candidate_role(
                mention, frame, predicate_surface, voice)
    candidate_counts = {}
    for role in candidate_roles.values():
        if role is not None:
            candidate_counts[role] = candidate_counts.get(role, 0) + 1

    for mention in local:
        if mention.particle == "は":
            role = candidate_roles[mention.token_index] or "UNKNOWN"
            origin = "TOPIC_INFERENCE" if role != "UNKNOWN" else "EXPLICIT_CASE"
            permitted = False
            binding_status = ("AMBIGUOUS" if role != "UNKNOWN"
                              and candidate_counts[role] > 1 else
                              "INFERRED" if role != "UNKNOWN" else "UNKNOWN")
            evidence = ("multiple same-clause mentions map to this owner Frame role; "
                        "topic/explicit role selection is ambiguous and all candidates are held"
                        if binding_status == "AMBIGUOUS" else
                        "legacy Frame filled role from は-topic; inference is held"
                        if role != "UNKNOWN" else
                        "explicit は-topic has no unique Frame-role match")
            if role != "UNKNOWN":
                mapped_roles.add(role)
        else:
            candidate_role = candidate_roles[mention.token_index]
            if candidate_role is not None:
                role = candidate_role
                origin = "EXPLICIT_CASE"
                binding_status = ("AMBIGUOUS" if candidate_counts[role] > 1
                                  else "UNIQUE")
                permitted = (binding_status == "UNIQUE"
                             and scope_known and quote_status == "UNQUOTED"
                             and not frame.ambiguous
                             and mention.span is not None
                             and mention.particle_span is not None)
                if binding_status == "AMBIGUOUS":
                    evidence = ("multiple same-clause mentions map to this owner Frame role; "
                                "identity/selection is ambiguous and all candidates are held")
                elif permitted:
                    evidence = "unique same-clause case marker and exact Frame filler match"
                elif frame.ambiguous:
                    evidence = "explicit case matches Frame role; another Frame role is ambiguous, so held"
                else:
                    evidence = "explicit case matched; scope/quote/offset gate is held"
                mapped_roles.add(role)
            else:
                role = "UNKNOWN"
                origin = "EXPLICIT_CASE"
                permitted = False
                binding_status = "UNKNOWN"
                evidence = "case phrase retained; case-to-role mapping is unsupported or conflicts with Frame"
        args.append(ArgumentEvidence(
            role=role,
            value=mention.value,
            span=mention.span,
            case_particle=mention.particle,
            particle_span=mention.particle_span,
            owner_frame_id=frame_id,
            source_frame_id=frame_id,
            origin=origin,
            permitted=permitted,
            evidence=evidence,
            binding_status=binding_status,
        ))

    for role in _ROLE_NAMES:
        value = getattr(frame, role)
        if not value or role in mapped_roles:
            continue
        topic_hits = [m for m in mentions if m.particle == "は"
                      and m.value == value and m.token_index < predicate_index]
        if topic_hits:
            topic = topic_hits[-1]
            local_topic = topic.token_index >= start
            source_owner = frame_id
            if not local_topic:
                # The topic belongs to the first Frame whose predicate follows
                # its source mention; a later consumer Frame stays held.
                first_following = next((i for i, p in enumerate(predicate_indices)
                                        if topic.token_index < p), 0)
                source_owner = frame_ids[first_following] if frame_ids else None
            args.append(ArgumentEvidence(
                role=role,
                value=value,
                span=topic.span,
                case_particle=topic.particle,
                particle_span=topic.particle_span,
                owner_frame_id=frame_id,
                source_frame_id=source_owner,
                origin="TOPIC_INFERENCE" if local_topic else "INTERCLAUSE_BORROW",
                permitted=False,
                evidence=("same-clause は-topic inference; held" if local_topic
                          else "topic mention lies before this Frame's local window; source owner is order-based hypothesis only; cross-clause borrowing held"),
                binding_status="INFERRED",
            ))
            mapped_roles.add(role)
            continue

        if frame.inferred:
            relative = _relative_span(source, positioned, predicate_index,
                                      next_predicate_index, value)
            if relative is not None:
                args.append(ArgumentEvidence(
                    role=role,
                    value=value,
                    span=relative,
                    case_particle=None,
                    particle_span=None,
                    owner_frame_id=frame_id,
                    source_frame_id=frame_id,
                    origin="RELATIVE_HEAD_INFERENCE",
                    permitted=False,
                    evidence="relative-head role is inferred; no case marker licenses it",
                    binding_status="INFERRED",
                ))
                mapped_roles.add(role)
                continue

        focus = _cleft_mention(toks, positioned, source,
                               predicate_index, value)
        if focus is not None:
            focus_span, cue_span = focus
            args.append(ArgumentEvidence(
                role=role,
                value=value,
                span=focus_span,
                case_particle="のは",
                particle_span=cue_span,
                owner_frame_id=frame_id,
                source_frame_id=frame_id,
                origin="CLEFT_FOCUS_INFERENCE",
                permitted=False,
                evidence="cleft focus is role-assigned by the legacy reader; no direct case license",
                binding_status="INFERRED",
            ))
            mapped_roles.add(role)
            continue

        args.append(ArgumentEvidence(
            role="UNKNOWN",
            value=value,
            span=None,
            case_particle=None,
            particle_span=None,
            owner_frame_id=frame_id,
            source_frame_id=None,
            origin="UNKNOWN",
            permitted=False,
            evidence=("legacy Frame inference/ambiguity has no role-specific source span"
                      if frame.inferred or frame.ambiguous else
                      "nonempty Frame value has no unique matching source argument span"),
            binding_status="UNKNOWN",
        ))
        mapped_roles.add(role)

    for role in _ROLE_NAMES:
        if not getattr(frame, role):
            args.append(ArgumentEvidence(
                role=role,
                value="",
                span=None,
                case_particle=None,
                particle_span=None,
                owner_frame_id=frame_id,
                source_frame_id=None,
                origin="OMITTED",
                permitted=False,
                evidence="Frame role is empty in its owner clause; no cross-clause fill is licensed",
                binding_status="OMITTED",
            ))
    return tuple(args)


def read_frame_evidence(source_id: str, text: str) -> FrameEvidenceDocument:
    """Build a per-source, per-clause sidecar for the existing Frame reader.

    Only a same-clause explicit case with an exact Frame-filler and closed
    case/voice match can be ``permitted``.  Topic, relative, cleft, borrowed
    and omitted roles retain provenance but remain held.
    """
    if not isinstance(source_id, str) or not isinstance(text, str):
        raise TypeError("source_id and text must be str")
    try:
        source_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        source_key = _source_key(source_id, source_sha)
    except UnicodeEncodeError as exc:
        raise ValueError("source_id and text must be valid UTF-8 strings") from exc

    positioned, token_positions_complete = _position_tokens(text)
    source_gaps, source_coverage_status = _source_coverage(text, positioned)
    toks = [word for word, _token_span in positioned]
    token_records = _as_token_evidence(positioned)
    predicate_hits = frames._predicates(toks)
    parsed_frames = frames.read_all(text)
    mentions = _case_mentions(toks, positioned, text)
    predicate_indices = [item[0] for item in predicate_hits]
    reader_alignment = ("ALIGNED_BY_READER_ORDER"
                        if len(predicate_hits) == len(parsed_frames) else "UNKNOWN")
    source_coverage_known = source_coverage_status in ("EXACT", "WHITESPACE_ONLY")
    alignment = (reader_alignment if source_coverage_known
                 else "UNKNOWN_SOURCE_COVERAGE")
    clause_ids = [f"{source_key}:c{i:04d}" for i in range(len(predicate_hits))]
    frame_ids = [f"{source_key}:f{i:04d}" for i in range(len(predicate_hits))]
    snapshots = [_frame_snapshot(frame) for frame in parsed_frames]
    clauses: List[ClauseEvidence] = []
    unmatched: Tuple[FrameSnapshot, ...] = ()

    if reader_alignment == "ALIGNED_BY_READER_ORDER":
        paired = parsed_frames
    else:
        # Do not positionally guess across a count mismatch. Preserve the
        # unmatched parsed values and leave each predicate unaligned/held.
        unmatched = tuple(snapshots)
        paired = [None] * len(predicate_hits)

    for index, (predicate_index, predicate_surface) in enumerate(predicate_hits):
        frame = paired[index]
        predicate_span = (_predicate_surface_span(text, toks, positioned,
                                                  predicate_index, frame)
                          if frame is not None else positioned[predicate_index][1])
        frame_id = frame_ids[index]
        next_predicate_index = (predicate_indices[index + 1]
                                if index + 1 < len(predicate_indices) else len(toks))
        previous_predicate_index = (predicate_indices[index - 1]
                                    if index else -1)

        negative_indices = _negative_indices(toks, predicate_index)
        frame_negated = bool(frame.negated) if frame is not None else False
        # Catch negators beyond the auxiliary chain, such as 送らないわけではない.
        all_local_negatives = [j for j in range(predicate_index + 1,
                                                 next_predicate_index)
                               if _is_negative_token(toks[j])]
        unscoped_negatives = [j for j in all_local_negatives
                              if j not in negative_indices]
        source_coverage_known = source_coverage_status in ("EXACT", "WHITESPACE_ONLY")
        local_scope_known = (frame is not None and source_coverage_known
                             and len(negative_indices) <= 1
                             and not unscoped_negatives
                             and frame_negated == bool(negative_indices)
                             and predicate_span is not None)
        local_polarity = ("NEGATIVE" if negative_indices else "POSITIVE") \
            if local_scope_known else "UNKNOWN"
        local_scope_span = (_span(text, predicate_span.start,
                                  positioned[negative_indices[0]][1].end)
                            if local_scope_known and negative_indices
                            and positioned[negative_indices[0]][1] is not None
                            else None)
        negation_spans = tuple(positioned[j][1] for j in all_local_negatives
                               if positioned[j][1] is not None)

        predicate_quote_status, quote_span = _quote_state_for_span(
            text, predicate_span)
        quote_status = (predicate_quote_status
                        if predicate_quote_status in ("QUOTED", "UNQUOTED")
                        else "UNKNOWN")
        next_predicate_surface = (predicate_hits[index + 1][1]
                                  if index + 1 < len(predicate_hits) else None)
        following_argument_index = next((mention.start_token_index for mention in mentions
                                         if predicate_index < mention.token_index
                                         < next_predicate_index), None)
        context_reason = _scope_context_reason(
            toks, predicate_index, next_predicate_index, quote_status,
            next_predicate_surface, following_argument_index,
        )
        scope_known = (local_scope_known and context_reason in (
            "UNEMBEDDED_LOCAL_SCOPE", "COORDINATED_LOCAL_SCOPE"))
        polarity = local_polarity if scope_known else "UNKNOWN"
        scope_status = "KNOWN" if scope_known else "UNKNOWN"
        scope_span = local_scope_span if scope_known else None
        if not source_coverage_known:
            context_reason = "UNKNOWN_SOURCE_COVERAGE"
        elif not local_scope_known:
            context_reason = "LOCAL_NEGATION_SCOPE_UNKNOWN"
        assertion_status = ("UNKNOWN" if not source_coverage_known else
                            "QUOTED" if quote_status == "QUOTED"
                            else "UNCLASSIFIED" if quote_status == "UNQUOTED"
                            else "UNKNOWN")

        if frame is None:
            arguments = ()
            snapshot = None
            clause_alignment = "UNKNOWN_PREDICATE_FRAME_ALIGNMENT"
        else:
            arguments = _build_arguments(
                text, toks, positioned, mentions, predicate_index,
                previous_predicate_index, next_predicate_index, frame, frame_id,
                frame_ids, predicate_indices, predicate_surface, scope_known,
                quote_status,
            )
            arguments = _annotate_argument_scopes(
                text, arguments, predicate_span, quote_status, quote_span,
                source_coverage_status,
            )
            snapshot = snapshots[index]
            clause_alignment = ("ALIGNED_BY_READER_ORDER"
                                if source_coverage_known
                                else "UNKNOWN_SOURCE_COVERAGE")
        clauses.append(ClauseEvidence(
            clause_id=clause_ids[index],
            frame_id=frame_id,
            ordinal=index,
            predicate=(frame.predicate if frame is not None else predicate_surface),
            predicate_span=predicate_span,
            scope_span=scope_span,
            negation_spans=negation_spans,
            polarity=polarity,
            scope_status=scope_status,
            quote_status=quote_status,
            assertion_status=assertion_status,
            quote_span=quote_span,
            frame=snapshot,
            arguments=arguments,
            alignment_status=clause_alignment,
            local_polarity=local_polarity,
            local_scope_status="KNOWN" if local_scope_known else "UNKNOWN",
            local_scope_span=local_scope_span,
            scope_reason=context_reason,
            source_coverage_status=source_coverage_status,
        ))

    return FrameEvidenceDocument(
        source_id=source_id,
        source_sha256=source_sha,
        source_text=text,
        tokens=token_records,
        clauses=tuple(clauses),
        unmatched_frames=unmatched,
        alignment_status=alignment,
        reader_order_alignment_status=reader_alignment,
        token_positions_complete=token_positions_complete,
        source_gaps=source_gaps,
        source_coverage_status=source_coverage_status,
    )


__all__ = [
    "ArgumentEvidence", "ClauseEvidence", "FrameEvidenceDocument",
    "FrameSnapshot", "GapEvidence", "SourceSpan", "TokenEvidence",
    "read_frame_evidence",
]
