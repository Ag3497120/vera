"""A deliberately finite Japanese brief reader, using the existing Frame reader.

Supported: explicit short fiction/explanation, case-marked event clauses,
open/owner/location states, Before/Cause, explicit local rules, literal quotes,
conditional worlds, tense, focal viewpoint, sentence/length and word limits.
Source event ordering uses adjacent shared participants; cross-source same-name
reuse in fiction needs an explicit identity-recast choice.
Unknown mandatory text is retained and blocks public success. This is not a
general Japanese instruction reader and does not equate span coverage with R.
"""
from __future__ import annotations

from dataclasses import replace
import re

from .content_ir import (CLAUSE_TERMINATORS, Atom, Budget, ContentError, Ledger, Obligation,
                         Rule, Source, Span, State, digest, strip_clause_terminator)
from .frames import read_all
from .realize import surfaces
from .typed_edges import _tagger


def segments(text: str):
    """Split only at top-level terminators; quoted instructions stay data."""
    start, stack = 0, []
    pairs = {"「": "」", "『": "』", "（": "）", "(": ")"}
    for i, char in enumerate(text):
        if char in pairs:
            stack.append(pairs[char])
        elif stack and char == stack[-1]:
            stack.pop()
        elif not stack and char in CLAUSE_TERMINATORS:
            if text[start:i].strip():
                yield start, i + 1, text[start:i].strip()
            start = i + 1
    if text[start:].strip():
        yield start, len(text), text[start:].strip()
    if stack:
        raise ContentError("UNKNOWN_CONTENT_UNREAD", "unclosed quotation or parenthesis")


def norm(text: str) -> str:
    return re.sub(r"[\s、,。.!！]+", "", text)


def outside_quotes(text: str) -> str:
    """Offset-preserving mask: quoted meta-instructions cannot control C."""
    stack, result = [], []
    pairs = {"「": "」", "『": "』"}
    for char in text:
        if char in pairs:
            stack.append(pairs[char])
            result.append(" ")
        elif stack:
            if char == stack[-1]:
                stack.pop()
            result.append(" ")
        else:
            result.append(char)
    return "".join(result)


def read_state(text: str, world: str = "fiction") -> State | None:
    text = strip_clause_terminator(text)
    opened = re.fullmatch(r"([^、。]{1,40}?)(?:が|は)(開いている|閉じている|開いていない|閉じていない)", text)
    if opened:
        name, shape = opened.groups()
        return State(name, "open", "open" if shape.startswith("開") else "closed",
                     world, "いない" not in shape)
    owner = re.fullmatch(r"([^、。]{1,40}?)(?:が|は)([^、。]{1,40}?)の(?:持ち物|もの)(?:だ|です|である)", text)
    if owner:
        return State(owner[1], "owner", owner[2], world)
    place = re.fullmatch(r"([^、。]{1,40}?)(?:が|は)([^、。]{1,40}?)に(?:いる|ある)", text)
    if place:
        return State(place[1], "location", place[2], world)
    return None


def read_atom(text: str, budget: Budget, world: str = "fiction", *, conditional: bool = True) -> Atom:
    budget.tick()
    body = strip_clause_terminator(text)
    quoted = re.fullmatch(r"(?:引用[：:]\s*)?[「『](.*)[」』](?:を引用(?:する|して))?", body, re.S)
    attributed = re.fullmatch(r"([^「『]{1,40}?)(?:が|は)[「『](.*)[」』]と(?:言う|言った|述べる|述べた)", body, re.S)
    if attributed:
        return Atom(kind="quote", agent=attributed[1], quote=attributed[2],
                    world=world, tense="past" if body.endswith(("言った", "述べた")) else "present")
    if quoted:
        return Atom(kind="quote", quote=quoted[1], world=world)
    if conditional:
        condition = re.fullmatch(r"(?:もし)?(.+?)(?:なら|場合は)[、,](.+)", body)
        if condition:
            child = "hyp:" + digest(body)[:12]
            left = read_atom(condition[1], budget, child, conditional=False)
            right = read_atom(condition[2], budget, child, conditional=False)
            if left.kind == "quote" or right.kind == "quote":
                raise ContentError("UNKNOWN_CONTENT_UNREAD", "nested quoted conditional is unsupported")
            return replace(right, condition=(left,))
    state = read_state(body, world)
    if state:
        if any(name in ("彼", "彼女", "それ", "これ", "あれ") for name in state.as_atom().names()):
            raise ContentError("UNKNOWN_CONTENT_REFERENT", "unresolved state participant")
        return state.as_atom()
    frames = read_all(body + "。")
    # UniDic writes voiced past 「読んだ」 with orthBase=だ but cType=助動詞-タ.
    # The existing Frame.past flag misses that form. C retains the explicit
    # tense without changing Frame or teaching a new conjugation system.
    tokens = list(_tagger()(body))
    budget.tick(amount=max(1, len(tokens)))
    if any(t.feature.pos1 == "代名詞" for t in tokens):
        raise ContentError("UNKNOWN_CONTENT_REFERENT", "unresolved pronoun", clause=body)
    voiced_past = any("助動詞-タ" in str(t.feature.cType) for t in tokens)
    if len(frames) == 1 and voiced_past:
        frames[0].past = True
    budget.tick("parse_candidates", len(frames))
    viable = []
    for frame in frames:
        budget.tick()
        if not frame.agent or frame.ambiguous:
            continue
        variants = surfaces(frame, past=frame.past)
        variants["topic"] = variants.get("active", "").replace(frame.agent + "が", frame.agent + "は", 1)
        for shape in variants.values():
            budget.tick()
            if norm(body) == norm(shape):
                viable.append(Atom(predicate=frame.predicate, agent=frame.agent,
                                   patient=frame.patient, recipient=frame.recipient,
                                   negated=frame.negated, tense="past" if frame.past else "present",
                                   world=world))
                break
    distinct = {a.key(): a for a in viable}
    if len(distinct) > 1:
        raise ContentError("UNKNOWN_CONTENT_AMBIGUOUS", "multiple event readings survive")
    if not distinct:
        raise ContentError("UNKNOWN_CONTENT_UNREAD", "not a fully covered supported clause", clause=body)
    atom = next(iter(distinct.values()))
    if any(name in ("彼", "彼女", "それ", "これ", "あれ") for name in atom.names()):
        raise ContentError("UNKNOWN_CONTENT_REFERENT", "unresolved pronoun", clause=body)
    return atom


def read_rule(body: str, source: Span, budget: Budget, world: str) -> Rule:
    """規則：箱が閉じているとき、ミナが箱を開けると、箱が開いている。

    This is an explicit work-local transition, not an imported commonsense law.
    A rule without とき has no preconditions; none are silently invented.
    """
    required = ()
    pre = re.fullmatch(r"(.+?)(?:とき|場合は)[、,](.+)", body)
    if pre:
        states = []
        for part in pre[1].split("かつ"):
            budget.tick()
            state = read_state(part, world)
            if state is None:
                raise ContentError("UNKNOWN_CONTENT_UNREAD", "unsupported rule precondition")
            states.append(state)
        required, body = tuple(states), pre[2]
    candidates = []
    for match in re.finditer("と[、,]?", body):
        budget.tick()
        left, right = body[:match.start()], body[match.end():]
        effects = []
        for part in right.split("かつ"):
            budget.tick()
            effect = read_state(part, world)
            if effect is None:
                break
            effects.append(effect)
        else:
            try:
                action = read_atom(left, budget, world, conditional=False)
            except ContentError as error:
                if error.verdict == "UNKNOWN_CONTENT_BUDGET":
                    raise
                continue
            if action.kind == "event" and not action.negated:
                candidates.append((action, tuple(effects)))
    if len(candidates) != 1:
        raise ContentError("UNKNOWN_CONTENT_UNREAD", "local rule must have one explicit action/effect reading")
    action, effects = candidates[0]
    return Rule("r:" + digest((action.key(), required, effects, source))[:16], action, required, effects, source)


def _source_events(source: Source, budget: Budget, world: str, *, required: bool):
    """Read one event per original material sentence and retain its exact span.

    Development/attested expression material is a creative component only.
    Factual source summaries require every supplied assertion to be readable.
    No question/answer fields or completed-text similarity scores are involved.
    """
    result = []
    for start, end, text in segments(source.text):
        budget.tick("candidates")
        span = Span.of(source, start, end)
        try:
            atom = read_atom(text, budget, world)
            if atom.kind != "event":
                raise ContentError("UNKNOWN_CONTENT_UNREAD", "material clause is not an event")
        except ContentError as error:
            if error.verdict == "UNKNOWN_CONTENT_BUDGET":
                raise
            if required:
                raise ContentError("UNKNOWN_CONTENT_SOURCE_UNREAD",
                                   "a required source clause cannot be read completely",
                                   source=source.id, start=start, end=end,
                                   cause=error.verdict) from error
            continue
        result.append((atom, span))
        budget.size("parse_candidates", len(result))
    return result


def _connected_source_events(candidates, wanted: int, budget: Budget, *, allow_identity_recast: bool = False):
    """Find a bounded ordered path with adjacent, properly scoped participants."""
    ordered = sorted((item for item in candidates
                      if item[0].world == "fiction" and not item[0].condition), key=lambda item: (
        item[1].source, item[1].start, item[1].end, item[0].key()))
    budget.size("parse_candidates", len(ordered))
    budget.tick(amount=max(1, len(ordered)))
    if wanted > budget.limits["events"]:
        budget.size("events", wanted)
    if wanted < 2 or wanted > len(ordered):
        raise ContentError("UNKNOWN_CONTENT_SOURCE_COMPONENTS",
                           "the requested short story needs at least two readable source events",
                           requested=wanted, candidates=len(ordered))

    def participant_keys(item):
        atom, span = item
        scope = "fiction-recast" if allow_identity_recast else span.source
        return {(scope, name) for name in atom.names()}

    def extend(path, remaining):
        if len(path) == wanted:
            return path
        budget.size("depth", len(path))
        previous = participant_keys(path[-1])
        for index, candidate in enumerate(remaining):
            budget.tick("plans")
            budget.tick("candidates")
            budget.tick()
            if not previous.intersection(participant_keys(candidate)):
                continue
            found = extend(path + [candidate], remaining[:index] + remaining[index + 1:])
            if found is not None:
                return found
        return None

    for first_index, first in enumerate(ordered):
        budget.tick("plans")
        budget.tick()
        found = extend([first], ordered[:first_index] + ordered[first_index + 1:])
        if found is not None:
            return found
    raise ContentError("UNKNOWN_CONTENT_SOURCE_COMPONENTS",
                       "source-scoped readable events do not form the requested adjacent-participant path",
                       requested=wanted, candidates=len(ordered),
                       identity_recast=allow_identity_recast)


_COUNT = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8}


def _event_set_hold(reason: str, *, projection=None, binding=None,
                    verdict: str = "UNKNOWN_CONTENT_UNREAD"):
    projection_record = projection.as_dict() if projection is not None else None
    binding_record = binding.as_dict() if binding is not None else None
    raise ContentError(
        verdict, reason,
        request_goal_projection=projection_record,
        source_event_binding=binding_record,
        source_truth_status="UNCLASSIFIED",
        semantic_event_set_complete=None,
        goal_satisfied=None,
        success_count_eligible=False,
    )


def is_event_set_request_attempt(text: str) -> bool:
    """Return a routing hint for source-event summary requests, never READY."""
    from .compositional_goal import is_event_set_request_attempt as detect
    return detect(text)


def read_brief_with_context(text: str, materials: tuple = (),
                            budget: Budget | None = None):
    """Read a brief and return optional rederived raw Goal/source binding data."""
    if is_event_set_request_attempt(text):
        return _read_event_set_brief(text, materials, budget)
    return _read_brief_regular(text, materials, budget), None, None


def read_brief(text: str, materials: tuple = (), budget: Budget | None = None) -> Ledger:
    return read_brief_with_context(text, materials, budget)[0]


def _read_event_set_brief(text: str, materials: tuple = (),
                          budget: Budget | None = None):
    from .compositional_goal import derive_request_event_set_projection
    from .multigrain_source_binding import bind_request_event_set

    budget = budget or Budget()
    budget.size("brief_chars", len(text))
    if not isinstance(materials, (tuple, list)):
        _event_set_hold("event-set input materials must be a finite tuple or list")
    budget.size("material_chars", sum(len(item.text) for item in materials
                                      if isinstance(item, Source)))
    projection = derive_request_event_set_projection(text)
    if (projection.status != "READY" or projection.action != "summarize_events"
            or projection.target_kind != "source_event"
            or projection.selection_scope != "all_matching_events"
            or projection.required_sentence_count != 2
            or projection.quantity_span is None
            or projection.raw_sha256 != Source("brief", text).sha256):
        _event_set_hold("raw source-event summary Goal remains unread or ambiguous",
                        projection=projection)

    evidence = tuple(
        item for item in materials
        if type(item) is Source and item.purpose == "evidence"
        and item.family not in ("narrative", "paraphrase_entail")
    )
    document_map = ({evidence[0].id: evidence[0].text}
                    if len(evidence) == 1 else {})
    binding = bind_request_event_set(text, document_map)
    if binding.status != "BOUND":
        _event_set_hold("original evidence did not bind every requested source event: "
                        + binding.reason, projection=projection,
                        binding=binding, verdict="UNKNOWN_CONTENT_EVIDENCE")

    material = evidence[0]
    parsed = _source_events(material, budget, "actual", required=True)
    parsed.sort(key=lambda item: (item[1].start, item[1].end, item[0].key()))
    bound_events = tuple(binding.events)
    if (material.id != binding.source_id or material.sha256 != binding.source_sha256
            or len(parsed) != len(bound_events)):
        _event_set_hold("C source events do not match the independent local-role binding",
                        projection=projection, binding=binding,
                        verdict="UNKNOWN_CONTENT_EVIDENCE")

    for (atom, span), event in zip(parsed, bound_events):
        event_roles = {role.role: role.value for role in event.roles}
        parsed_roles = {role: value for role, value in (
            ("agent", atom.agent), ("patient", atom.patient),
            ("recipient", atom.recipient)) if value}
        if (span.source != event.source_id or span.sha256 != event.source_sha256
                or (span.start, span.end) != event.clause_span
                or text_for_span(material, span) != event.clause_text
                or atom.predicate != event.predicate
                or parsed_roles != event_roles):
            _event_set_hold("event role/predicate/span differs across source readers",
                            projection=projection, binding=binding,
                            verdict="UNKNOWN_CONTENT_EVIDENCE")

    brief = Source("brief", text)
    whole = Span.of(brief)
    quantity = projection.quantity_span
    if (quantity.source != "request" or quantity.sha256 != projection.raw_sha256
            or not 0 <= quantity.start < quantity.end <= len(text)
            or text[quantity.start:quantity.end] not in ("二文", "2文")):
        _event_set_hold("exact output quantity has no verifiable raw span",
                        projection=projection, binding=binding)
    quantity_span = Span.of(brief, quantity.start, quantity.end)
    obligations = [
        Obligation("o1", "mode", whole, value="actual"),
        Obligation("o2", "source_summary", whole),
        Obligation("o3", "sentences", quantity_span, number=2),
    ]
    event_obligations = []
    for atom, span in parsed:
        budget.tick("candidates")
        obligation = Obligation("o" + str(len(obligations) + 1), "event", span,
                                atom=atom, value="material_evidence")
        obligations.append(obligation)
        event_obligations.append(obligation)
    for left, right in zip(event_obligations, event_obligations[1:]):
        budget.tick()
        obligations.append(Obligation(
            "o" + str(len(obligations) + 1), "relation", whole,
            value="o2", relation=("List", left.id, right.id)))
    budget.size("events", len(event_obligations))
    ledger = Ledger(brief, (material,), tuple(obligations), mode="actual")
    return ledger, projection.as_dict(), binding.as_dict()


def text_for_span(source: Source, span: Span) -> str:
    if (type(source) is not Source or type(span) is not Span
            or span.source != source.id or span.sha256 != source.sha256
            or type(span.start) is not int or type(span.end) is not int
            or not 0 <= span.start <= span.end <= len(source.text)):
        return ""
    return source.text[span.start:span.end]


def _read_brief_regular(text: str, materials: tuple = (), budget: Budget | None = None) -> Ledger:
    budget = budget or Budget()
    budget.size("brief_chars", len(text))
    budget.size("material_chars", sum(len(s.text) for s in materials))
    source = Source("brief", text)
    obligations, rules, unread, pending = [], [], [], []
    mode, choice, tense, previous = "", set(), "", ""
    source_summary_span = None
    pieces = tuple(segments(text))

    def add(kind: str, span: Span, **kwargs) -> Obligation:
        obligation = Obligation("o" + str(len(obligations) + 1), kind, span, **kwargs)
        obligations.append(obligation)
        return obligation

    for start, end, chunk in pieces:
        budget.tick()
        # Keep the exact original source span but remove its top-level
        # terminator from the grammar surface consumed by this finite reader.
        span, body = Span.of(source, start, end), strip_clause_terminator(chunk)
        # These operations consume only explicit meta-language. Any residual
        # content must receive an obligation or enter the unread ledger.
        outer = outside_quotes(body)
        fiction = (re.match(r"(?:架空の|創作の|短い)?(?:物語|お話|ストーリー)(?:を)?(?:書いて(?:ください)?|作って(?:ください)?|作成して(?:ください)?|を書く|を作る)?", outer)
                   if re.search(r"書いて|作って|作成して|を書く|を作る", outer) else None)
        factual = re.match(
            r"(?:資料に基づいて|資料から|資料に関する(?:(?:全|すべての)?イベントを)|資料の内容を|事実だけで)"
            r"(?:説明(?:して|する|を書いて)(?:ください)?|解説(?:して|する)(?:ください)?|"
            r"まとめ(?:て|る|てください)|要約(?:して|する)(?:ください)?)?", outer)
        if factual and re.search(r"(?:説明|解説)(?:して|する|を書いて)(?:ください)?|まとめ(?:て|る|てください)|要約(?:して|する)(?:ください)?", outer):
            source_summary_span = span
        for match, selected in ((fiction, "fiction"), (factual, "actual")):
            if match:
                if mode and mode != selected:
                    raise ContentError("CONTENT_CONSTRAINT_CONFLICT", "fact and fiction modes conflict")
                mode = selected
                add("mode", span, value=selected)
                body = body[:match.start()] + body[match.end():]
        body = body.strip(" 、,")
        count = re.match(r"([1-9][0-9]*|[一二三四五六七八])文(?:以内(?:で|に)?|で|に|$)", outside_quotes(body))
        if count:
            number = _COUNT.get(count[1], int(count[1]) if count[1].isdecimal() else 0)
            add("max_sentences" if "以内" in count[0] else "sentences", span, number=number)
            body = body.replace(count[0], "", 1)
        body = body.strip(" 、,")
        length = re.match(r"([1-9][0-9]*)[字文字]+以内(?:で|に)?", outside_quotes(body))
        if length:
            add("max_chars", span, number=int(length[1]))
            body = body.replace(length[0], "", 1)
        body = body.strip(" 、,")
        tense_match = re.match(r"(過去形|現在形)(?:で|に|$)", outside_quotes(body))
        if tense_match:
            selected = "past" if tense_match[1] == "過去形" else "present"
            if tense and tense != selected:
                raise ContentError("CONTENT_CONSTRAINT_CONFLICT", "incompatible tense obligations")
            tense = selected
            add("tense", span, value=tense)
            body = body.replace(tense_match[0], "", 1)
        body = body.strip(" 、,")
        viewpoint = re.match(r"(?:全知視点|([^、。]{1,30}?)の視点)(?:で|から|$)", outside_quotes(body))
        if viewpoint:
            add("viewpoint", span, value=viewpoint[1] or "omniscient")
            body = body.replace(viewpoint[0], "", 1)
        body = body.strip(" 、,")
        free = re.match(r"(出来事|順序)は(?:自由に決めてよい|任意に決めてよい)", outside_quotes(body))
        if free:
            scope = "events" if free[1] == "出来事" else "order"
            choice.add(scope)
            add("author_choice", span, value=scope)
            body = body.replace(free[0], "", 1)
        identity_recast = re.match(
            r"別素材の同名要素は新しい創作内の要素として結び直してよい", outside_quotes(body))
        if identity_recast:
            choice.add("identity_recast")
            add("author_choice", span, value="identity_recast")
            body = body.replace(identity_recast[0], "", 1)
        body = body.strip(" 、,：:")
        if body in ("", "書いて", "書いてください", "作って", "作ってください",
                    "説明して", "説明してください", "解説して", "解説してください",
                    "まとめて", "まとめる", "まとめてください", "要約して", "要約する", "要約してください"):
            continue
        pending.append((body, span))

    if not mode:
        raise ContentError("UNKNOWN_CONTENT_PERMISSION", "explicit fiction or evidence-only explanation mode required")
    base_world = "fiction" if mode == "fiction" else "actual"
    for body, span in pending:
        budget.tick()
        if re.match(r"(?:作品内の)?規則[：:]", body):
            if mode != "fiction":
                unread.append(span)
                continue
            rule = read_rule(re.sub(r"^(?:作品内の)?規則[：:]\s*", "", body), span, budget, base_world)
            rules.append(rule)
            add("rule", span, value=rule.id)
            continue
        word = re.fullmatch(r"[「『](.+)[」』](?:という語)?(?:を含める|は使わない|を使わない)", body, re.S)
        if word:
            add("exclude_word" if "使わない" in body else "include_word", span, value=word[1])
            continue
        state_marker = re.fullmatch(r"(初期状態|最初|終状態|最後)(?:は|[：:])(.+)", body)
        if state_marker:
            state = read_state(state_marker[2], base_world)
            if state is None:
                unread.append(span)
            else:
                add("initial" if state_marker[1] in ("初期状態", "最初") else "final", span, state=state)
            continue
        forbidden = body.startswith(("禁止：", "禁止:"))
        if forbidden:
            body = body[3:]
        body = re.sub(r"^必ず[、,]?", "", body)
        body = re.sub(r"(?:内容)?を含める$|こと$", "", body)
        relation = ""
        connector = re.match(r"^(その後で?|次に|それから|そのため|だから)[、,]?", body)
        if connector:
            relation = "Cause" if connector[1] in ("そのため", "だから") else "Before"
            body = body[connector.end():]
        causal = re.fullmatch(r"(.+?)(ため|ので)[、,](.+)", body)
        temporal = re.fullmatch(r"(.+?)(?:後に|後で|前に)[、,](.+)", body)
        try:
            if causal or temporal:
                pair = causal or temporal
                left = read_atom(pair[1], budget, base_world)
                right = read_atom(pair[3] if causal else pair[2], budget, base_world)
                if forbidden:
                    raise ContentError("UNKNOWN_CONTENT_UNREAD", "forbidden relation syntax unsupported")
                first = add("event", span, atom=left)
                second = add("event", span, atom=right)
                label = "Cause" if causal else "Before"
                a, b = (second.id, first.id) if temporal and "前に" in temporal[0] else (first.id, second.id)
                add("relation", span, relation=(label, a, b))
                previous = second.id
            else:
                atom = read_atom(body, budget, base_world)
                obligation = add("forbid_event" if forbidden else "event", span, atom=atom)
                if relation:
                    if not previous or forbidden:
                        raise ContentError("UNKNOWN_CONTENT_UNREAD", "connector lacks an unambiguous previous event")
                    add("relation", span, relation=(relation, previous, obligation.id))
                if not forbidden:
                    previous = obligation.id
        except ContentError as error:
            if error.verdict in ("UNKNOWN_CONTENT_BUDGET", "UNKNOWN_CONTENT_AMBIGUOUS", "UNKNOWN_CONTENT_REFERENT"):
                raise
            unread.append(span)
    explicit_content = any(o.kind in ("event", "forbid_event", "initial", "final", "rule", "relation")
                          for o in obligations)
    if source_summary_span is not None and mode == "actual" and not explicit_content:
        summary = add("source_summary", source_summary_span)
        assertions = []
        for material in materials:
            budget.tick()
            if (material.purpose != "evidence" or
                    material.family in ("narrative", "paraphrase_entail")):
                continue
            assertions.extend(_source_events(material, budget, "actual", required=True))
        if not assertions:
            raise ContentError("UNKNOWN_CONTENT_EVIDENCE",
                               "source summary has no readable factual event material",
                               obligation=summary.id)
        if len(assertions) > budget.limits["events"]:
            raise ContentError("UNKNOWN_CONTENT_BUDGET", "source summary exceeds the event limit",
                               counter="events", actual=len(assertions),
                               limit=budget.limits["events"])
        event_obligations = []
        for atom, span in assertions:
            budget.tick()
            event_obligations.append(add("event", span, atom=atom, value="material_evidence"))
        for left, right in zip(event_obligations, event_obligations[1:]):
            budget.tick()
            add("relation", source_summary_span,
                relation=("List", left.id, right.id), value=summary.id)

    expression_source_story = (
        mode == "fiction" and "events" in choice and not explicit_content
    )
    if expression_source_story:
        order_permission = next((o for o in obligations
                                 if o.kind == "author_choice" and o.value == "order"), None)
        candidates = []
        seen = set()
        for material in materials:
            budget.tick()
            if material.purpose != "expression":
                continue
            for atom, span in _source_events(material, budget, "fiction", required=False):
                key = (span.source, span.start, span.end, atom.key())
                if key not in seen:
                    seen.add(key)
                    candidates.append((atom, span))
        sentences = {o.number for o in obligations if o.kind == "sentences"}
        maximum = {o.number for o in obligations if o.kind == "max_sentences"}
        if len(sentences) > 1 or len(maximum) > 1:
            raise ContentError("CONTENT_CONSTRAINT_CONFLICT", "incompatible story format obligations")
        wanted = next(iter(sentences), min(3, next(iter(maximum), 3)))
        if maximum and wanted > next(iter(maximum)):
            raise ContentError("CONTENT_CONSTRAINT_CONFLICT", "exact story count exceeds its sentence limit")
        selected = _connected_source_events(
            candidates, wanted, budget, allow_identity_recast="identity_recast" in choice)
        if order_permission is None:
            raise ContentError("UNKNOWN_CONTENT_PERMISSION",
                               "material events need explicit permission to choose their story order")
        event_obligations = []
        for index, (atom, span) in enumerate(selected):
            budget.tick()
            recast = any(
                other_span.source != span.source and
                set(atom.names()).intersection(other_atom.names())
                for other_index, (other_atom, other_span) in enumerate(selected)
                if other_index != index
            )
            if recast:
                budget.tick("candidates")
            event_obligations.append(add("event", span, atom=atom,
                                         value="expression_material_recast" if recast else "expression_material"))
        for left, right in zip(event_obligations, event_obligations[1:]):
            budget.tick()
            add("relation", order_permission.span,
                relation=("Before", left.id, right.id), value=order_permission.id)

    if tense:
        def retime(atom):
            return replace(atom, tense=tense, condition=tuple(retime(a) for a in atom.condition)) if atom.kind != "quote" else atom
        for obligation in obligations:
            if (obligation.value in ("expression_material", "expression_material_recast") and obligation.atom and
                    obligation.atom.kind != "quote" and obligation.atom.tense != tense):
                raise ContentError("CONTENT_CONSTRAINT_CONFLICT",
                                   "requested tense would change the time of a supplied story event",
                                   obligation=obligation.id)
        obligations = [replace(o, atom=retime(o.atom)) if o.atom else o for o in obligations]
    budget.size("candidates", len(rules) + sum(o.atom is not None for o in obligations))
    return Ledger(source, tuple(materials), tuple(obligations), tuple(rules), tuple(unread), mode, tuple(sorted(choice)))
