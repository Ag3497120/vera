"""Source-bounded voice and aspect readings over native case frames."""
from __future__ import annotations

import hashlib
from dataclasses import replace

from ..semantic_ir import Clause, Role, Span, Variable
from . import Construction, ConstructionContext, Reading, TypedNote, register


_A_ROW = {
    "う": "わ", "く": "か", "ぐ": "が", "す": "さ", "つ": "た",
    "ぬ": "な", "ぶ": "ば", "む": "ま", "る": "ら",
}
_E_ROW = {
    "う": "え", "く": "け", "ぐ": "げ", "す": "せ", "つ": "て",
    "ぬ": "ね", "ぶ": "べ", "む": "め", "る": "れ",
}
_A_TO_U = {value: key for key, value in _A_ROW.items()}
_TE_ROW = {
    "う": "って", "つ": "って", "る": "って", "く": "いて", "ぐ": "いで",
    "す": "して", "ぬ": "んで", "ぶ": "んで", "む": "んで",
}
_I_E = frozenset("いきぎしじちぢにひびぴみりえけげせぜてでねへべぺめれ")
_SAFE_UNSUPPORTED = frozenset((
    "multiple predicates need explicit clause scope", "ambiguous frame role",
    "unlocated patient", "unlocated agent", "unrepresented source content",
    "unlicensed role borrowing", "ambiguous case role: に", "ambiguous case role: で",
    "ambiguous case role: と", "ambiguous case role: から",
    # The native frame hands a causative's に-phrase to `recipient`; this construction (and gold_caus_pass) is the only
    # reader that may re-assign it, so the reader's reason is named here and nowhere else.
    "causative frame: causer/causee unresolved",
))
_MARKERS = ("によって", "により", "において", "における", "に対して", "について",
            "による", "として", "と共に", "ともに", "には", "では",
            "が", "は", "を", "に", "で", "と")
_EVENT_ENDINGS = ("る", "た", "ている", "ていた", "ており")


def _verb_class(lemma: str) -> tuple[str, str] | None:
    if lemma.endswith("する"):
        return "suru", lemma[:-2]
    if lemma in ("来る", "くる"):
        return "kuru", "来" if lemma == "来る" else "こ"
    if len(lemma) >= 2 and lemma.endswith("る") and lemma[-2] in _I_E:
        return "ichidan", lemma[:-1]
    row = _A_ROW.get(lemma[-1:] if lemma else "")
    return ("godan", lemma[:-1] + row) if row else None


def _forms_for_reader(lemma: str) -> tuple[tuple[str, str], ...]:
    """Return complete predicate forms licensed by productive conjugation."""
    parsed = _verb_class(lemma)
    if not parsed:
        return ()
    kind, stem = parsed
    if kind == "suru":
        passive, causative, te = stem + "され", stem + "させ", stem + "し"
    elif kind == "kuru":
        passive, causative, te = stem + "られ", stem + "させ", stem + "き"
    elif kind == "ichidan":
        passive, causative, te = stem + "られ", stem + "させ", stem + "て"
    else:
        last = lemma[-1]
        passive, causative = stem + "れ", stem + "せ"
        te = lemma[:-1] + _TE_ROW[last]
        if lemma == "行く":
            te = "行って"
    if kind == "suru":
        potential = stem + "でき"
    elif kind == "kuru":
        potential = stem + "られ"
    elif kind == "ichidan":
        potential = stem + "られ"
    else:
        potential = lemma[:-1] + _E_ROW[lemma[-1]]
    forms: list[tuple[str, str]] = []
    for ending in _EVENT_ENDINGS:
        forms.append(("passive", passive + ending))
        forms.append(("causative", causative + ending))
    for ending in ("いる", "いた", "おり"):
        forms.append(("aspect", te + ending))
    if potential:
        for ending in _EVENT_ENDINGS:
            forms.append(("potential", potential + ending))
    return tuple(forms)


def _case_after(text: str, end: int) -> tuple[str, int] | None:
    tail = text[end:]
    for marker in _MARKERS:
        if tail.startswith(marker):
            return marker, end + len(marker)
    return None


def _time_like(term: str) -> bool:
    return any(char.isdigit() for char in term) and any(
        marker in term for marker in ("年", "月", "日", "時", "分")
    )


def _aligned_roles(ctx: ConstructionContext, clause: Clause, mode: str,
                   predicate_start: int, predicate_end: int,
                   potential_as_subject: bool = False, source_base: str = "") -> tuple[Role, ...] | None:
    text, base = ctx.sentence_text, ctx.sentence_span.start
    roles: list[Role] = []
    seen_cases: list[tuple[Role, str, int]] = []
    for old in clause.roles:
        span = old.span
        if (span.source != ctx.sentence_span.source or span.start < base
                or span.end > ctx.sentence_span.end or span.text != text[span.start-base:span.end-base]
                or not isinstance(old.term, str) or old.term != span.text):
            return None
        found = _case_after(text, span.end-base)
        if found is None:
            if mode != "passive" or span.start != base+predicate_end:
                return None
            marker, marker_end = "", span.end-base
        else:
            marker, marker_end = found
        seen_cases.append((old, marker, marker_end))

    has_patient_case = any(marker in ("が", "は", "を") for _, marker, _ in seen_cases)
    has_passive_agent = any(marker in ("に", "によって", "により")
                            for _, marker, _ in seen_cases)
    # A causee is the person the causer acts on, which the native frame types as `recipient`. A に-phrase the frame
    # typed as goal/result/direction/location is an adjunct (X が Y を Z に V-させる, V intransitive): never the causee.
    has_causee_case = any(
        marker == "に" and old.name == "recipient" and not _time_like(old.term)
        for old, marker, _ in seen_cases
    ) if mode == "causative" else any(
        marker == "に" and old.name not in ("time", "place", "setting", "direction")
        and not _time_like(old.term) for old, marker, _ in seen_cases
    )

    if mode == "causative" and has_causee_case and any(marker == "を" for _, marker, _ in seen_cases):
        # X が Y に Z を V-させる (V transitive: Y is the causee, Z the patient) differs from X が Y を Z に V-させる (V
        # intransitive: Y is the causee, Z a destination). The source verb's transitivity (corpus-derived, frames.py) decides;
        # when it does not say transitive, abstain rather than guess.
        from ..frames import transitivity
        if not source_base or transitivity(source_base) != "trans":
            return None
    for old, marker, marker_end in seen_cases:
        if mode == "passive":
            if not marker and old.span.start == base+predicate_end:
                name = "patient"
            elif marker in ("によって", "により"):
                name = "agent"
            elif marker in ("が", "は"):
                name = "patient"
            elif marker == "を" and has_passive_agent:
                name = "patient"
            elif marker == "に" and has_patient_case and old.name not in (
                    "time", "place", "setting", "direction", "source") and not _time_like(old.term):
                name = "agent"
            elif marker == "と" and marker_end == predicate_start:
                name = "complement"
            elif marker == "に":
                return None
            else:
                continue
        elif mode == "causative":
            if old.name in ("goal", "direction", "result", "location", "source", "means", "companion", "ambiguous"):
                return None          # an adjunct this construction cannot represent: abstain, do not drop it
            if marker == "が" and old.name not in ("time", "place", "setting"):
                name = "causer"
            elif marker == "に" and old.name == "recipient" and not _time_like(old.term):
                name = "causee"
            elif marker == "を" and has_causee_case:
                name = "patient"
            elif marker == "を":
                return None
            else:
                continue
        elif mode == "potential":
            if marker == "を":
                name = "patient"
            elif marker == "が" and (old.name in ("patient", "ambiguous")
                                      or (potential_as_subject and old.name == "agent")):
                name = "patient"
            elif marker == "が" and old.name == "agent":
                name = "agent"
            elif marker in ("は", "では"):
                name = "topic"
            else:
                continue
        else:
            if marker == "が" and old.name != "patient":
                name = "subject"
            elif marker in ("は", "では"):
                name = "topic"
            elif marker == "を" and old.name in ("patient", "ambiguous"):
                name = "patient"
            else:
                continue
        roles.append(Role(name, old.term, old.span, old.rule))

    if mode == "passive" and not any(r.name == "patient" for r in roles):
        # A relative passive can place its head immediately after the verb.
        # Only promote a native source-bounded argument, never guessed text.
        for old in clause.roles:
            if old.span.start == ctx.sentence_span.start + predicate_end:
                roles.append(Role("patient", old.term, old.span, old.rule))
                break
    names = [r.name for r in roles]
    if len(names) != len(set(names)):
        return None
    if mode == "passive" and names.count("patient") != 1:
        return None
    if mode == "causative" and (not roles or not any(r.name == "causee" for r in roles)):
        return None
    if mode == "potential" and not any(name in ("patient", "agent") for name in names):
        return None
    if mode == "potential" and any(r.name == "topic" for r in roles) and not any(
            r.name == "patient" for r in roles):
        return None
    if mode == "aspect" and not roles:
        return None
    if mode == "passive":
        # The ichidan and 来る forms overlap. A structurally paired agent
        # settles the passive reading; otherwise leave the role ambiguous.
        form_start = min((r.span.start-base for r in roles), default=clause.predicate_span.start-base)
        form = text[form_start:predicate_end]
        ambiguous = ("られる" in form or "られて" in form) and not any(
            role.name == "agent" for role in roles
        )
        if ambiguous:
            return None
    return tuple(sorted(roles, key=lambda r: (r.span.start, r.name)))


def _form_at(text: str, local_start: int, local_end: int, lemma: str):
    matches = []
    for mode, form in _forms_for_reader(lemma):
        earliest = max(0, local_start - len(form))
        latest = min(local_start, len(text) - len(form))
        for start in range(earliest, latest + 1):
            if (text.startswith(form, start) and start <= local_start < start + len(form)
                    and start + len(form) >= local_end
                    and form[local_start-start:local_end-start] == text[local_start:local_end]):
                matches.append((mode, start, start + len(form), form))
    return matches


def _causative_bases(lemma: str) -> tuple[str, ...]:
    """Invert regular causative morphology, retaining every structural tie."""
    candidates: set[str] = set()
    if lemma.endswith("させる"):
        root = lemma[:-3]
        candidates.add(root + "する")
        if root and root[-1] in _I_E:
            candidates.add(root + "る")
    if lemma.endswith("こさせる"):
        candidates.add("くる")
    if lemma.endswith("来させる"):
        candidates.add("来る")
    if lemma.endswith("せる") and len(lemma) > 2:
        a_stem = lemma[:-2]
        final = a_stem[-1:]
        if final in _A_TO_U:
            candidates.add(a_stem[:-1] + _A_TO_U[final])
    return tuple(sorted(base for base in candidates if _verb_class(base)))


def _unrepresented_lead(tokens, lead_end: int) -> bool:
    """A case/topic-marked phrase (<pronoun>は, <place>で) stands in this clause before its typed frame. The segment starts after the
    previous predicate (earlier clauses of a long sentence are other clauses' business). Connective particles (が、て)
    do not count; case, topic and focus particles do."""
    segment = []
    for item in tokens:
        if item.end > lead_end:
            break
        feature = item.token.feature
        if feature.pos1 in ("動詞", "形容詞") or (feature.pos1 == "助動詞" and str(feature.cForm).startswith("終止")):
            segment = []
            continue
        segment.append(item)
    return any(getattr(i.token.feature, "pos1", "") == "助詞" and getattr(i.token.feature, "pos2", "") in ("格助詞", "係助詞", "副助詞")
               and i.token.surface != "の" for i in segment)


def _resolve_causative_bases(ctx: ConstructionContext, p0: int, p1: int, bases: tuple[str, ...]) -> tuple[str, ...]:
    """Settle the base verb of a causative from the source's own morphology.

    食べさせる inverts to 食べる (ichidan), 食べする (suru) and 食べす (godan) when only the form is looked at. The tagger
    already knows which verb stands in front of させ/せ: a candidate that is not that verb's lemma is dropped (so 着させた
    does not become 着する). When the tagger gives no verb there, nothing is changed (the ambiguity stays an abstention)."""
    if not bases:
        return bases
    for index, item in enumerate(ctx.tokens):
        if item.start < p0 or item.end > ctx.sentence_span.end - ctx.sentence_span.start:
            continue
        if getattr(item.token, "surface", "") in ("せ", "さ せ") or (
                getattr(item.token, "surface", "") in ("させ",) and item.start >= p0):
            if index == 0:
                return bases
            before = ctx.tokens[index - 1].token
            feature = getattr(before, "feature", None)
            if feature is None or getattr(feature, "pos1", "") != "動詞":
                return bases
            lemma = getattr(feature, "orthBase", None) or getattr(feature, "lemma", None)
            if not lemma:
                return bases
            lemma = str(lemma).split("-")[0]
            if lemma == "する":                      # <サ変 noun>させる: the noun + する
                return tuple(b for b in bases if b.endswith("する"))
            return tuple(b for b in bases if b == lemma)
    return bases


def _body_span(ctx: ConstructionContext, roles: tuple[Role, ...],
               pred_start: int, pred_end: int) -> Span | None:
    sentence, text = ctx.sentence_span, ctx.sentence_text
    base = sentence.start
    bounds = [(pred_start, pred_end)]
    for role in roles:
        left, right = role.span.start-base, role.span.end-base
        bounds.append((left, right))
        case = _case_after(text, right)
        if case is not None:
            bounds.append((right, case[1]))
        elif not (role.name == "patient" and left == pred_end):
            return None
    start = min(left for left, _ in bounds)
    end = max(right for _, right in bounds)
    covered = [False] * (end-start)
    for left, right in bounds:
        for position in range(left-start, right-start):
            if position < 0 or position >= len(covered) or covered[position]:
                return None
            covered[position] = True
    if any(not covered[i] and not text[start+i].isspace() for i in range(len(covered))):
        return None
    return Span(sentence.source, base+start, base+end, text[start:end])


def reads(ctx: ConstructionContext) -> Reading | None:
    if (len(ctx.tokens) > ctx.budget.max_tokens or len(ctx.clauses) > ctx.budget.max_steps
            or len(ctx.sentence_text) > 4096):
        return None
    sentence = ctx.sentence_span
    if sentence.text != ctx.sentence_text or sentence.start < 0 or sentence.end <= sentence.start:
        return None
    local_clauses = tuple(c for c in ctx.clauses
                          if c.span.source == sentence.source
                          and c.span.start < sentence.end and c.span.end > sentence.start
                          and c.predicate_span.source == sentence.source
                          and sentence.start <= c.predicate_span.start < c.predicate_span.end <= sentence.end)
    if len(local_clauses) > ctx.budget.max_clauses:
        return None
    text, base = ctx.sentence_text, sentence.start
    output: list[Clause] = []
    consumed: list[Span] = []
    notes: list[TypedNote] = []
    for clause in local_clauses:
        if ((clause.rule != "frame" and not (clause.rule == "simile" and clause.predicate.endswith("できる")))
                or clause.conditions or clause.exceptions
                or clause.polarity != "+" or clause.modality not in ("assert", "possible", "permission", "simile")
                or any(reason not in _SAFE_UNSUPPORTED for reason in clause.unsupported)):
            continue
        p0, p1 = clause.predicate_span.start-base, clause.predicate_span.end-base
        if clause.predicate_span.text != text[p0:p1]:
            continue
        lemma = clause.predicate
        potential_base = lemma[:-3] + "する" if lemma.endswith("できる") and len(lemma) > 3 else ""
        matches = [(mode, start, end, form, lemma)
                   for mode, start, end, form in _form_at(text, p0, p1, lemma)]
        if potential_base:
            matches.extend((mode, start, end, form, potential_base)
                           for mode, start, end, form in _form_at(text, p0, p1, potential_base)
                           if mode == "potential")
        causative_bases = _resolve_causative_bases(ctx, p0, p1, _causative_bases(lemma))
        for candidate in causative_bases:
            matches.extend((mode, start, end, form, candidate)
                           for mode, start, end, form in _form_at(text, p0, p1, candidate)
                           if mode == "causative")
        unique_matches = sorted(set(matches))
        if len(unique_matches) > 1:
            modes = {match[0] for match in unique_matches}
            bounds = {(match[1], match[2], match[3]) for match in unique_matches}
            if modes == {"passive", "potential"} and len(bounds) == 1:
                explicit_agent = any(
                    (case := _case_after(text, role.span.end-base)) is not None
                    and case[0] in ("によって", "により") for role in clause.roles
                )
                potential_roles = _aligned_roles(
                    ctx, clause, "potential", p0, p1,
                    potential_as_subject=(clause.predicate == "する" and "できる" in text[p0:p1]),
                )
                passive_roles = _aligned_roles(ctx, clause, "passive", p0, p1)
                distinct_potential_frame = (potential_roles is not None
                                           and any(r.name == "patient" for r in potential_roles)
                                           and (any(r.name == "topic" for r in potential_roles)
                                                or any(_case_after(text, r.span.end-base) is not None
                                                       and _case_after(text, r.span.end-base)[0] == "を"
                                                       for r in clause.roles)))
                if explicit_agent or (passive_roles is not None
                                      and any(r.name == "agent" for r in passive_roles)):
                    unique_matches = [match for match in unique_matches if match[0] == "passive"]
                elif distinct_potential_frame:
                    unique_matches = [match for match in unique_matches if match[0] == "potential"]
                else:
                    notes.append(TypedNote("ambiguous frame role", clause.predicate_span,
                                           "the inflected form can express either passive voice or potential ability"))
                    continue
        if len(unique_matches) != 1:
            if causative_bases and any(m[0] == "causative" for m in unique_matches):
                notes.append(TypedNote("ambiguous frame role", clause.predicate_span,
                                       "more than one base predicate licenses this causative form"))
            continue
        mode, form_start, form_end, form, source_base = unique_matches[0]
        if mode != "potential" and clause.modality not in ("assert", "possible"):
            continue
        remainder = text[form_end:].lstrip()
        boundary = (remainder[0] in "。！？」』）》)]}、，," or remainder.startswith("が、")) if remainder else True
        purpose_potential = mode == "potential" and remainder.startswith("ように")
        if remainder and not boundary and not purpose_potential:
            continue
        new_predicate = (source_base if mode == "causative" else
                         potential_base if mode == "potential" and potential_base else lemma)
        modality = "possible" if mode == "potential" else "assert"
        roles = _aligned_roles(
            ctx, clause, mode, form_start, form_end,
            potential_as_subject=(mode == "potential" and new_predicate == "する" and form == "できる"),
            source_base=(source_base if mode == "causative" else ""),
        )
        if roles is None:
            notes.append(TypedNote("ambiguous frame role", clause.predicate_span,
                                   "voice or aspect morphology is present, but the source case frame does not settle every role"))
            continue
        body = _body_span(ctx, roles, form_start, form_end)
        if body is None:
            notes.append(TypedNote("unrepresented source content", clause.predicate_span,
                                   "the local source span contains material outside the typed case frame and predicate"))
            continue
        lead_rel = body.start - base
        if _unrepresented_lead(ctx.tokens, lead_rel):
            # A case/topic phrase stands before the typed frame and no role holds it (an affected 私は, a で-phrase):
            # the clause would silently drop it, so abstain.
            notes.append(TypedNote("unrepresented source content", clause.predicate_span,
                                   "a case-marked phrase before the typed frame is not represented by any role"))
            continue
        time = "past" if form.endswith(("た", "ていた", "できた", "できていた")) else "nonpast"
        digest = hashlib.sha256(
            (sentence.source + ":" + str(sentence.start) + ":" + str(form_start) + ":" +
             new_predicate + ":" + mode + ":" + ",".join(r.name+"="+r.span.text for r in roles)).encode("utf-8")
        ).hexdigest()[:24]
        predicate_span = Span(sentence.source, base+form_start, base+form_end, form)
        event = replace(clause.event, name="event_"+digest, sort="event")
        built = replace(clause, id=digest, event=event, predicate=new_predicate,
                        predicate_span=predicate_span, roles=roles, span=sentence,
                        body_span=clause.body_span, polarity="+", modality=modality, time=time,
                        conditions=(), condition_spans=(), exceptions=(),
                        exception_spans=(), exception_of="", rule="diathesis", unsupported=())
        output.append(built)
        if sentence not in consumed:
            consumed.append(sentence)
    if output:
        return Reading(tuple(output[:ctx.budget.max_clauses]),
                       tuple(consumed[:ctx.budget.max_clauses]), ())
    return Reading((), (), tuple(notes)) if notes else None


def _license_class(lemma: str) -> tuple[str, str] | None:
    if lemma[-2:] == "する":
        return "suru", lemma[:-2]
    if lemma == "来る" or lemma == "くる":
        return "kuru", "来" if lemma == "来る" else "こ"
    if lemma.endswith("る") and len(lemma) > 1 and lemma[-2] in _I_E:
        return "ichidan", lemma[:-1]
    final = lemma[-1:] if lemma else ""
    if final in _A_ROW:
        return "godan", lemma[:-1] + _A_ROW[final]
    return None


def _license_forms(lemma: str) -> dict[str, frozenset[str]]:
    """Independent source morphology check; it does not inspect reader output."""
    parsed = _license_class(lemma)
    if parsed is None:
        return {}
    kind, root = parsed
    if kind == "suru":
        p, c, te = root+"され", root+"させ", root+"し"
    elif kind == "kuru":
        p, c, te = root+"られ", root+"させ", root+"き"
    elif kind == "ichidan":
        p, c, te = root+"られ", root+"させ", root+"て"
    else:
        a = _A_ROW[lemma[-1]]
        p, c = root+"れ", root+"せ"
        te = lemma[:-1] + _TE_ROW[lemma[-1]]
        if lemma == "行く":
            te = "行って"
    endings = ("る", "た", "ている", "ていた", "ており")
    result = {
        "passive": frozenset(p+x for x in endings),
        "causative": frozenset(c+x for x in endings),
        "aspect": frozenset(te+x for x in ("いる", "いた", "おり")),
    }
    if kind == "suru":
        potential = root + "でき"
    elif kind in ("kuru", "ichidan"):
        potential = root + "られ"
    else:
        potential = lemma[:-1] + _E_ROW[lemma[-1]]
    result["potential"] = frozenset(potential+x for x in endings)
    return result


def _license_case(text: str, start: int, end: int) -> tuple[str, int] | None:
    # Kept separate from the reader's case scanner for independent checking.
    rest = text[end:]
    for mark in ("によって", "により", "において", "における", "に対して",
                 "について", "による", "として", "と共に", "ともに", "には", "では"):
        if rest.startswith(mark):
            return mark, end+len(mark)
    for mark in ("が", "は", "を", "に", "で", "と"):
        if rest.startswith(mark):
            return mark, end+len(mark)
    return None


def _license_time_like(value: str) -> bool:
    digit = False
    unit = False
    for char in value:
        digit = digit or char.isdigit()
        unit = unit or char in "年月日時分"
    return digit and unit or value.endswith(("年", "月", "日", "時", "分"))


def licenses(clause: Clause, source: str) -> bool:
    if (clause.rule != "diathesis" or not isinstance(source, str) or clause.unsupported
            or clause.polarity != "+" or clause.conditions or clause.exceptions
            or clause.exception_of or clause.modality not in ("assert", "possible")):
        return False
    whole = clause.span
    body = clause.body_span
    pred = clause.predicate_span
    if (whole.source != pred.source or whole.start < 0 or whole.end > len(source)
            or source[whole.start:whole.end] != whole.text or body is None
            or body.source != whole.source or body.start != whole.start or body.end != whole.end
            or source[body.start:body.end] != body.text or pred.start < whole.start
            or pred.end > whole.end or source[pred.start:pred.end] != pred.text):
        return False
    if whole.text != source[whole.start:whole.end] or not whole.text:
        return False
    form_table = _license_forms(clause.predicate)
    form = pred.text
    possible_modes = {mode for mode, forms in form_table.items() if form in forms}
    if clause.modality == "possible" and "potential" in possible_modes:
        mode = "potential"
    elif clause.modality == "assert" and "passive" in possible_modes:
        mode = "passive"
    elif len(possible_modes) == 1:
        mode = next(iter(possible_modes))
    else:
        return False
    if (mode == "potential") != (clause.modality == "possible"):
        return False
    expected_time = "past" if form.endswith(("た", "ていた", "できた", "できていた")) else "nonpast"
    if clause.time != expected_time:
        return False

    role_marks: list[tuple[int, int, str, str]] = []
    source_marks: dict[str, list[str]] = {}
    for role in clause.roles:
        found = _license_case(source, role.span.start, role.span.end)
        source_marks.setdefault(role.name, []).append(found[0] if found else "")
    passive_has_agent = any(mark in ("に", "によって", "により")
                            for mark in source_marks.get("agent", ()))
    passive_has_patient = any(mark in ("が", "は", "を")
                              for mark in source_marks.get("patient", ()))
    for role in clause.roles:
        span = role.span
        if (span.source != whole.source or span.start < whole.start or span.end > whole.end
                or span.start >= span.end or source[span.start:span.end] != span.text
                or not isinstance(role.term, str) or role.term != span.text):
            return False
        case = _license_case(source, span.start, span.end)
        marker = case[0] if case else ""
        if mode == "passive":
            allowed = ((role.name == "patient" and marker in ("が", "は"))
                       or (role.name == "patient" and marker == "を" and passive_has_agent)
                       or (role.name == "agent" and marker in ("によって", "により"))
                       or (role.name == "agent" and marker == "に" and passive_has_patient
                           and not _license_time_like(span.text))
                       or (role.name == "complement" and marker == "と"
                           and case is not None and case[1] == pred.start))
        elif mode == "causative":
            allowed = ((role.name == "causer" and marker == "が")
                       or (role.name == "causee" and marker == "に" and not _license_time_like(span.text))
                       or (role.name == "patient" and marker == "を"))
        elif mode == "potential":
            allowed = ((role.name == "patient" and marker == "を")
                       or (role.name == "patient" and marker == "が")
                       or (role.name == "agent" and marker == "が")
                       or (role.name == "topic" and marker in ("は", "では")))
        else:
            allowed = ((role.name == "subject" and marker == "が")
                       or (role.name == "topic" and marker in ("は", "では"))
                       or (role.name == "patient" and marker == "を"))
        if not allowed:
            # An unmarked patient is licensed only as the nominal head directly
            # following an attributive passive form and ending the sentence.
            if not (mode == "passive" and role.name == "patient" and not marker
                    and span.start == pred.end
                    and source[span.end:whole.end].strip("。！？ \t\n") == ""):
                return False
            mark_end = span.end
        else:
            assert case is not None
            mark_end = case[1]
        role_marks.append((span.start, mark_end, role.name, marker))
    names = [role.name for role in clause.roles]
    if len(names) != len(set(names)):
        return False
    if mode == "passive":
        if names.count("patient") != 1 or len(names) > 3:
            return False
        if form.endswith(("られる", "られている", "られていた", "られており")) and not any(
            name == "agent" and marker in ("に", "によって", "により")
            for _, _, name, marker in role_marks
        ):
            return False
    elif mode == "causative":
        if "causee" not in names or len(names) > 3:
            return False
        if "patient" in names:
            # causee に + patient を is the transitive causative; an intransitive verb's を-phrase is its causee and its に-phrase
            # a destination, so this role assignment would be the wrong one for 戻る/向かう-type bases.
            from ..frames import transitivity
            if transitivity(clause.predicate) != "trans":
                return False
        if "patient" in names and not any(name == "patient" and mark == "を"
                                           for _, _, name, mark in role_marks):
            return False
    elif mode == "potential":
        if not any(name in ("patient", "agent") for name in names) or len(names) > 2:
            return False
        if "passive" in possible_modes:
            patient_markers = {mark for _, _, name, mark in role_marks if name == "patient"}
            has_topic = any(name == "topic" and mark in ("は", "では")
                            for _, _, name, mark in role_marks)
            if not ("を" in patient_markers or (has_topic and patient_markers & {"が", "を"})):
                return False
    elif not names or len(names) > 2:
        return False

    remainder = source[pred.end:whole.end].lstrip()
    boundary = (remainder[0] in "。！？」』）》)]}、，," or remainder.startswith("が、")) if remainder else True
    purpose_potential = mode == "potential" and remainder.startswith("ように")
    if remainder and not boundary and not purpose_potential:
        return False

    # Reconstruct the local frame from source-anchored roles and the complete
    # inflected predicate. Sentence material outside that frame stays outside
    # this clause's body even though the evidence span is sentence-wide.
    frame_start = min([pred.start] + [a for a, _, _, _ in role_marks])
    frame_end = max([pred.end] + [b for _, b, _, _ in role_marks])
    from ..typed_edges import _tagger
    lead = []
    for word in _tagger()(source[whole.start:frame_start]):
        if word.feature.pos1 in ("動詞", "形容詞") or (word.feature.pos1 == "助動詞" and str(word.feature.cForm).startswith("終止")):
            lead = []
            continue
        lead.append(word)
    if any(word.feature.pos1 == "助詞" and word.feature.pos2 in ("格助詞", "係助詞", "副助詞") and word.surface != "の" for word in lead):
        return False     # a case/topic phrase before the frame that no role represents (私は…盗まれた)
    covered = [False] * (frame_end-frame_start)
    for lo, hi in ((pred.start, pred.end),) + tuple((a, b) for a, b, _, _ in role_marks):
        for pos in range(lo-frame_start, hi-frame_start):
            if pos < 0 or pos >= len(covered) or covered[pos]:
                return False
            covered[pos] = True
    for i, char in enumerate(source[frame_start:frame_end]):
        if covered[i] or char.isspace():
            continue
        return False
    return True


register(Construction(name="diathesis", priority=48, reads=reads, licenses=licenses,
                      refines=("frame", "simile")))


__all__ = ("licenses", "reads")
