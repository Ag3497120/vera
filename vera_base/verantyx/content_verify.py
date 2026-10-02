"""Independent gate for obligations, state replay, provenance and surface.

This module does not call the planner, producer flags, C realizer or C brief
reader. Surface validation checks explicit case slots and morphological tense
and polarity. State transitions are replayed separately from planner updates.
The gate validates a bounded contract, not general literary quality or R/E.
"""
from __future__ import annotations

from dataclasses import asdict
import re

from .content_ir import (CLAUSE_TERMINATORS, Atom, Budget, ContentError, Ledger, Plan, Realization,
                         State, digest, source_text, strip_clause_terminator)
from .content_reader import is_event_set_request_attempt, read_brief
from .frames import read_all
from .realize import conjugate
from .typed_edges import _base, _negated, _tagger


def _display(name: str, narrator: str) -> str:
    return "私" if name and name == narrator else name


def _atom_matches(atom: Atom, body: str, narrator: str, budget: Budget) -> bool:
    """Read the *controlled output* independently of the input Frame reader."""
    budget.tick()
    if atom.condition:
        if len(atom.condition) != 1 or not body.startswith("もし"):
            return False
        guard, separator, consequent = body[2:].partition("なら、")
        if not separator or not _atom_matches(atom.condition[0], guard, narrator, budget):
            return False
        body = consequent
    elif body.startswith("もし"):
        return False
    name = _display(atom.agent, narrator)
    if atom.kind == "quote":
        expected = (name + "は" if name else "引用：") + "「" + atom.quote + "」"
        if name:
            expected += "と" + ("述べた" if atom.tense == "past" else "述べる")
        return body == expected
    body = re.sub(r"[\s、,]", "", body)
    if atom.kind == "state":
        past = atom.tense == "past"
        if atom.fluent == "open":
            stem = "開いて" if atom.value == "open" else "閉じて" if atom.value == "closed" else ""
            ending = ("いなかった" if past else "いない") if atom.negated else ("いた" if past else "いる")
            return bool(stem) and body in (name + "は" + stem + ending, name + "が" + stem + ending)
        value = _display(atom.value, narrator)
        if atom.fluent == "owner":
            ending = ("ではなかった" if past else "ではない") if atom.negated else ("だった" if past else "だ")
            return any(body == name + case + value + "の" + noun + ending
                       for case in ("は", "が") for noun in ("もの", "持ち物"))
        if atom.fluent == "location":
            ending = ("いなかった" if past else "いない") if atom.negated else ("いた" if past else "いる")
            existential = ("なかった" if past else "ない") if atom.negated else ("あった" if past else "ある")
            return any(body == name + case + value + "に" + tail
                       for case in ("は", "が") for tail in (ending, existential))
        return False
    if atom.kind != "event" or not name:
        return False
    prefixes = (name + "が", name + "は")
    prefix = next((p for p in prefixes if body.startswith(p)), "")
    if not prefix:
        return False
    tail = body[len(prefix):]
    if atom.recipient:
        recipient = _display(atom.recipient, narrator) + "に"
        if not tail.startswith(recipient):
            return False
        tail = tail[len(recipient):]
    if atom.patient:
        patient = _display(atom.patient, narrator) + "を"
        if not tail.startswith(patient):
            return False
        tail = tail[len(patient):]
    licensed = set()
    for polite in (False, True):
        budget.tick()
        shape = conjugate(atom.predicate, past=atom.tense == "past", neg=atom.negated, polite=polite)
        if shape:
            licensed.add(shape)
    if tail not in licensed:
        return False
    tokens = list(_tagger()(tail))
    budget.tick(amount=max(1, len(tokens)))
    verbs = [(i, _base(t)) for i, t in enumerate(tokens) if t.feature.pos1 == "動詞"]
    if len(verbs) != 1:
        return False
    main, verb = verbs[0]
    if main:
        if verb != "する" or any(t.feature.pos1 not in ("名詞", "接尾辞") for t in tokens[:main]):
            return False
        verb = "".join(t.surface for t in tokens[:main]) + verb
    allowed = {"た", "ない", "無い", "ます"}
    for token in tokens[main + 1:]:
        budget.tick()
        if _base(token) not in allowed and "助動詞-タ" not in str(token.feature.cType):
            return False
    past = any(_base(t) == "た" or "助動詞-タ" in str(t.feature.cType) for t in tokens[main + 1:])
    return (verb == atom.predicate and _negated(tokens, main) == atom.negated
            and past == (atom.tense == "past"))


def _state_lookup(states: tuple, wanted: State, budget: Budget):
    exact, opposite, alternatives = False, False, False
    for state in states:
        budget.tick()
        if state.key() != wanted.key():
            continue
        exact |= state.value == wanted.value and state.positive == wanted.positive
        opposite |= state.value == wanted.value and state.positive != wanted.positive
        alternatives |= wanted.positive and state.positive and state.value != wanted.value
    if exact and (opposite or alternatives):
        raise ContentError("CONTENT_STATE_CONFLICT", "contradictory explicit state")
    return True if exact else False if opposite or alternatives else None


def _independent_update(states: tuple, effects: tuple, budget: Budget) -> tuple:
    for index, effect in enumerate(effects):
        for other in effects[index + 1:]:
            budget.tick()
            if effect.key() == other.key() and (
                effect.value == other.value and effect.positive != other.positive or
                effect.positive and other.positive and effect.value != other.value
            ):
                raise ContentError("CONTENT_STATE_CONFLICT", "contradictory rule effects")
    result = []
    for state in states:
        overwritten = False
        for effect in effects:
            budget.tick()
            if effect.key() == state.key() and (effect.positive or effect.value == state.value):
                overwritten = True
        if not overwritten:
            result.append(state)
    result.extend(effects)
    return tuple(sorted(set(result), key=lambda s: (s.key(), s.value, s.positive)))


def _expression_matches(atom: Atom, text: str, classification: str, budget: Budget) -> bool:
    text = strip_clause_terminator(text)
    if atom.kind != "event" or atom.condition or re.search(r"[「『]|なら|場合|ため|ので", text):
        return False
    frames = read_all(text)
    budget.tick(amount=max(1, len(frames)))
    if len(frames) != 1:
        return False
    frame = frames[0]
    if frame.ambiguous or frame.predicate != atom.predicate or bool(frame.patient) != bool(atom.patient) or bool(frame.recipient) != bool(atom.recipient):
        return False
    if classification == "slot_substitution":
        return True
    tokens = list(_tagger()(text))
    budget.tick(amount=max(1, len(tokens)))
    past = frame.past or any("助動詞-タ" in str(t.feature.cType) for t in tokens)
    return ((frame.agent, frame.patient, frame.recipient, frame.negated, past) ==
            (atom.agent, atom.patient, atom.recipient, atom.negated, atom.tense == "past"))


def verify_content(ledger: Ledger, plan: Plan, realization: Realization,
                   budget: Budget | None = None) -> dict:
    budget = budget or Budget()
    checks = []

    def require(condition: bool, name: str, reason: str, verdict="CONTENT_CONSTRAINT_VIOLATION"):
        budget.tick()
        if not condition:
            raise ContentError(verdict, reason, check=name)
        checks.append({"check": name, "passed": True})

    if is_event_set_request_attempt(ledger.brief.text):
        # Raw request and direct materials are the consumer's trust boundary.
        # Re-run the Goal producer and source binder through the reader; no
        # caller metadata or preverified flag can authorize this ledger.
        rederived_ledger = read_brief(ledger.brief.text, ledger.materials, budget)
        require(ledger == rederived_ledger, "event_set_ledger_rederived",
                "raw Goal, source binding, or C obligations differ from fresh derivation")

    require(not ledger.unread, "brief_read", "unread mandatory obligations")
    require(plan.ledger_hash == ledger.hash, "ledger_hash", "plan uses a different ledger")
    require(realization.plan_hash == plan.hash, "plan_hash", "surface uses a different plan")
    sources = (ledger.brief,) + ledger.materials
    require(len({s.id for s in sources}) == len(sources), "source_identity", "source IDs are not unique")
    source_map = {s.id: s for s in sources}
    obligations = {o.id: o for o in ledger.obligations}
    require(len(obligations) == len(ledger.obligations), "obligation_ids", "duplicate obligation IDs")
    for obligation in ledger.obligations:
        budget.tick()
        source_text(obligation.span, sources)
    for rule in ledger.rules:
        budget.tick()
        source_text(rule.source, sources)
        permissions = [o for o in ledger.obligations if o.kind == "rule" and o.value == rule.id]
        budget.tick(amount=max(1, len(ledger.obligations)))
        require(len(permissions) == 1 and permissions[0].span == rule.source,
                "rule_source_binding", "rule witness does not match its rule obligation")
    nodes = {node.id: node for node in plan.nodes}
    require(len(nodes) == len(plan.nodes), "node_ids", "duplicate node IDs")
    require(len(plan.order) == len(nodes) and set(plan.order) == set(nodes), "node_order", "missing or duplicate realization nodes")
    initial_ids = [node_id for node_id in plan.order if nodes[node_id].phase == "initial"]
    final_ids = [node_id for node_id in plan.order if nodes[node_id].phase == "final"]
    require(list(plan.order[:len(initial_ids)]) == initial_ids and
            (not final_ids or list(plan.order[-len(final_ids):]) == final_ids),
            "state_phase_order", "initial/final statement is at the wrong narrative position")
    budget.size("nodes", len(nodes))
    budget.size("events", sum(n.atom.kind == "event" for n in plan.nodes))
    for node in plan.nodes:
        budget.tick()
        require(node.atom.kind in ("event", "state", "quote"), "node_kind", "unsupported node kind")
        require(node.atom.tense in ("past", "present"), "node_tense", "unsupported tense")
        require(all(o in obligations for o in node.obligations), "node_obligations", "invented obligation reference")
        require(all(obligations[o].kind in ("event", "initial", "final") for o in node.obligations),
                "content_obligation_role", "metadata obligation used to licence extra content")
        if ledger.mode == "fiction":
            permission = obligations.get(node.permission)
            linked_expression_events = bool(node.obligations) and all(
                obligations[o].kind == "event" and obligations[o].value in
                ("expression_material", "expression_material_recast")
                for o in node.obligations
            )
            allowed = bool(permission and (
                permission.kind == "mode" and permission.value == "fiction" and bool(node.obligations) or
                permission.kind == "author_choice" and permission.value == "events" and
                (not node.obligations or linked_expression_events)
            ))
            require(allowed, "fiction_permission", "fiction event is outside brief permission")
        else:
            require(not node.permission, "fact_permission", "fiction permission applied to factual output")
        if not node.obligations:
            licensed = [r for r in ledger.rules if r.id == node.rule and r.action.event_key() == node.atom.event_key()]
            require(bool(licensed), "author_choice_action", "extra event is not a supplied rule action")
        for span in node.evidence:
            budget.tick()
            body = source_text(span, sources)
            if node.atom.kind == "quote" and body == node.atom.quote:
                continue
            if ledger.mode == "actual":
                source = source_map[span.source]
                require(source.purpose == "evidence" and source.family not in ("narrative", "paraphrase_entail"),
                        "fact_source_role", "expression witness used as occurrence evidence")
                require(_atom_matches(node.atom, strip_clause_terminator(body), "omniscient", budget),
                        "fact_source_semantics", "evidence does not support roles/time/world/polarity")
        if ledger.mode == "actual" and not (node.atom.kind == "quote" and not node.atom.agent):
            require(any(source_map[s.source].purpose == "evidence" and source_map[s.source].family not in ("narrative", "paraphrase_entail") and
                        _atom_matches(node.atom, strip_clause_terminator(source_text(s, sources)), "omniscient", budget)
                        for s in node.evidence), "fact_evidence", "factual clause has no occurrence witness")
        if node.atom.condition:
            require(len(node.atom.condition) == 1 and node.atom.world.startswith("hyp:") and
                    node.atom.condition[0].world == node.atom.world,
                    "hypothetical_world", "conditional escaped its hypothetical world")
        else:
            require(node.atom.world == ("fiction" if ledger.mode == "fiction" else "actual"),
                    "assertion_world", "assertion escaped its authorized world")
    allowed_kinds = {"mode", "sentences", "max_sentences", "max_chars", "tense", "viewpoint",
                     "author_choice", "event", "forbid_event", "initial", "final", "relation",
                     "include_word", "exclude_word", "rule", "source_summary"}
    expected_relations = []
    for obligation in ledger.obligations:
        budget.tick()
        require(obligation.kind in allowed_kinds, "obligation_kind", "unverified obligation kind")
        linked = [n for n in plan.nodes if obligation.id in n.obligations]
        budget.tick(amount=max(1, len(plan.nodes)))
        if obligation.kind in ("event", "initial", "final"):
            expected = obligation.atom or obligation.state.as_atom(next((o.value for o in ledger.obligations if o.kind == "tense"), "present"))
            require(len(linked) == 1 and linked[0].atom.key() == expected.key() and linked[0].phase == obligation.kind,
                    "obligation_content", "required node missing or semantic roles/world/polarity changed")
            if obligation.value in ("expression_material", "expression_material_recast"):
                source = source_map[obligation.span.source]
                required_node = linked[0]
                body = strip_clause_terminator(source_text(obligation.span, sources))
                require(ledger.mode == "fiction" and source.purpose == "expression" and
                        required_node.permission in {o.id for o in ledger.obligations
                                                    if o.kind == "author_choice" and o.value == "events"} and
                        obligation.span in required_node.evidence and
                        _expression_matches(expected, body, "paraphrase", budget),
                        "expression_event_binding",
                        "authored story event is not bound to its exact nonfactual material clause")
                if obligation.value == "expression_material_recast":
                    recast_permissions = [o for o in ledger.obligations
                                          if o.kind == "author_choice" and o.value == "identity_recast"]
                    peers = [o for o in ledger.obligations
                             if o.kind == "event" and o.id != obligation.id and
                             o.value == "expression_material_recast" and
                             o.span.source != obligation.span.source and o.atom is not None and
                             set(expected.names()).intersection(o.atom.names())]
                    require(len(recast_permissions) == 1 and bool(peers) and
                            "identity_recast" in plan.author_choices,
                            "fiction_identity_recast",
                            "cross-source name reuse requires explicit new-fiction-role permission")
            elif obligation.value == "material_evidence":
                source = source_map[obligation.span.source]
                body = strip_clause_terminator(source_text(obligation.span, sources))
                require(ledger.mode == "actual" and source.purpose == "evidence" and
                        source.family not in ("narrative", "paraphrase_entail") and
                        _atom_matches(expected, body, "omniscient", budget),
                        "summary_event_binding",
                        "summary event is not bound to its exact direct evidence clause")
            else:
                require(obligation.value == "", "event_origin", "unknown event origin marker")
        elif obligation.kind == "forbid_event":
            require(not any(n.atom.event_key() == obligation.atom.event_key() for n in plan.nodes),
                    "forbidden_event", "forbidden event occurs")
        elif obligation.kind == "relation":
            label, left, right = obligation.relation
            require(left in obligations and right in obligations,
                    "relation_obligation_targets", "relation references an absent obligation")
            a = [n.id for n in plan.nodes if left in n.obligations]
            b = [n.id for n in plan.nodes if right in n.obligations]
            left_obligation, right_obligation = obligations[left], obligations[right]
            allowed_label = label in ("Before", "Cause", "List")
            require(len(a) == len(b) == 1 and allowed_label, "relation_targets", "relation target/label missing")
            if label == "List":
                summary = obligations.get(obligation.value)
                require(ledger.mode == "actual" and summary is not None and
                        summary.kind == "source_summary" and
                        left_obligation.value == right_obligation.value == "material_evidence",
                        "list_relation_permission", "neutral listing is reserved for source-summary clauses")
            else:
                require(not (ledger.mode == "actual" and label in ("Before", "Cause")),
                        "relation_evidence", "factual material does not prove a temporal or causal relation",
                        "UNKNOWN_CONTENT_EVIDENCE")
                if obligation.value:
                    order_permission = obligations.get(obligation.value)
                    expression_values = ("expression_material", "expression_material_recast")
                    shared_names = set(nodes[a[0]].atom.names()).intersection(nodes[b[0]].atom.names())
                    same_source_identity = (left_obligation.span.source == right_obligation.span.source and
                                            bool(shared_names))
                    recast_identity = (left_obligation.span.source != right_obligation.span.source and
                                       left_obligation.value == right_obligation.value ==
                                       "expression_material_recast" and bool(shared_names) and
                                       sum(o.kind == "author_choice" and o.value == "identity_recast"
                                           for o in ledger.obligations) == 1 and
                                       "identity_recast" in plan.author_choices)
                    endpoints = (left_obligation.value in expression_values and
                                 right_obligation.value in expression_values and
                                 order_permission is not None and order_permission.kind == "author_choice" and
                                 order_permission.value == "order" and
                                 obligation.span == order_permission.span and ledger.mode == "fiction")
                    require(label == "Before" and endpoints and
                            (same_source_identity or recast_identity),
                            "material_order_permission",
                            "material story ordering lacks explicit order permission or shared participants")
                require(nodes[a[0]].atom.world == nodes[b[0]].atom.world and
                        not nodes[a[0]].atom.condition and not nodes[b[0]].atom.condition,
                        "relation_scope", "relation crosses an unsupported hypothetical/world scope", "UNKNOWN_CONTENT_SCOPE")
            expected_relations.append((label, a[0], b[0]))
        elif obligation.kind == "source_summary":
            summary_events = [o for o in ledger.obligations
                              if o.kind == "event" and o.value == "material_evidence"]
            require(ledger.mode == "actual" and not linked and bool(summary_events),
                    "source_summary_scope", "source summary needs one or more direct evidence events")
            request = source_text(obligation.span, sources)
            event_set_request = is_event_set_request_attempt(request)
            require(obligation.span.source == ledger.brief.id and
                    (event_set_request or bool(re.search(
                        r"(?:資料に基づいて|資料から|資料に関する(?:(?:全|すべての)?イベントを)|"
                        r"資料の内容を|事実だけで).*(?:説明|解説|まとめ|要約)", request))),
                    "source_summary_request", "source summary marker is not attached to a recognized raw request")
            require(sum(o.kind == "mode" and o.value == "actual" for o in ledger.obligations) == 1,
                    "source_summary_mode", "source summary needs exactly one actual-world mode")
            require(not any(o.kind == "event" and o.value != "material_evidence"
                            for o in ledger.obligations),
                    "source_summary_completeness", "source summary cannot mix unsourced user assertions")
            expected_pairs = [(left.id, right.id) for left, right in
                              zip(summary_events, summary_events[1:])]
            list_edges = [o for o in ledger.obligations
                          if o.kind == "relation" and o.relation and o.relation[0] == "List"]
            require([(o.relation[1], o.relation[2]) for o in list_edges] == expected_pairs and
                    all(o.value == obligation.id for o in list_edges),
                    "source_summary_order", "summary listing must preserve its exact extracted clause order")
            evidence_sources = [source for source in ledger.materials
                                if source.purpose == "evidence" and
                                source.family not in ("narrative", "paraphrase_entail")]
            for source in evidence_sources:
                budget.tick()
                marks = sorted((o.span for o in summary_events if o.span.source == source.id),
                               key=lambda s: (s.start, s.end))
                uncovered, cursor = [], 0
                for span in marks:
                    require(span.sha256 == source.sha256 and 0 <= span.start < span.end <= len(source.text),
                            "summary_source_span", "summary span is outside its evidence source")
                    require(span.start >= cursor, "summary_source_overlap", "summary source clauses overlap")
                    uncovered.append(source.text[cursor:span.start])
                    cursor = span.end
                uncovered.append(source.text[cursor:])
                # Charge the bounded scan once, rather than letting hidden
                # character iteration escape the shared step budget.
                budget.tick(amount=len(source.text))
                gaps = "".join(uncovered)
                require(not any(char not in CLAUSE_TERMINATORS and not char.isspace() for char in gaps),
                        "summary_source_completeness", "an evidence-source clause was omitted")
        elif obligation.kind == "author_choice":
            allowed_choice_text = {
                "events": {"出来事は自由に決めてよい", "出来事は任意に決めてよい"},
                "order": {"順序は自由に決めてよい", "順序は任意に決めてよい"},
                "identity_recast": {"別素材の同名要素は新しい創作内の要素として結び直してよい"},
            }
            require(obligation.value in allowed_choice_text and
                    obligation.span.source == ledger.brief.id and
                    strip_clause_terminator(source_text(obligation.span, sources)) in
                    allowed_choice_text.get(obligation.value, set()),
                    "author_choice_source", "author-choice metadata must match an explicit raw-brief grant")
        elif obligation.kind == "sentences":
            require(len(realization.clauses) == obligation.number, "sentence_count", "exact sentence count violated")
        elif obligation.kind == "max_sentences":
            require(len(realization.clauses) <= obligation.number, "sentence_limit", "sentence limit violated")
        elif obligation.kind == "max_chars":
            require(len(realization.text) <= obligation.number, "character_limit", "character limit violated")
        elif obligation.kind == "tense":
            atoms = [n.atom for n in plan.nodes] + [a for n in plan.nodes for a in n.atom.condition]
            require(all(atom.tense == obligation.value for atom in atoms if atom.kind != "quote"),
                    "tense_constraint", "requested tense is not preserved")
        elif obligation.kind == "viewpoint":
            require(plan.narrator == obligation.value, "viewpoint_constraint", "requested viewpoint changed")
        elif obligation.kind == "include_word":
            require(obligation.value in realization.text, "required_word", "required word absent")
        elif obligation.kind == "exclude_word":
            require(obligation.value not in realization.text, "forbidden_word", "forbidden word emitted")
    expression_events = [o for o in ledger.obligations
                         if o.kind == "event" and o.value in
                         ("expression_material", "expression_material_recast")]
    uses_identity_recast = any(o.value == "expression_material_recast" for o in expression_events)
    require(("identity_recast" in plan.author_choices) == uses_identity_recast,
            "fiction_recast_reporting", "plan author-choice metadata disagrees with source identity handling")
    if expression_events:
        order_ids = {o.id for o in ledger.obligations
                     if o.kind == "author_choice" and o.value == "order"}
        expected_order_pairs = [(left.id, right.id)
                                for left, right in zip(expression_events, expression_events[1:])]
        authored_order_edges = [o for o in ledger.obligations
                                if o.kind == "relation" and o.value in order_ids]
        require(ledger.mode == "fiction" and len(expression_events) >= 2 and len(order_ids) == 1 and
                [(o.relation[1], o.relation[2]) for o in authored_order_edges] == expected_order_pairs and
                all(o.relation[0] == "Before" for o in authored_order_edges),
                "expression_story_order", "material story requires explicit order for every selected event")
        if uses_identity_recast:
            require("identity_recast" in plan.author_choices and
                    sum(o.kind == "author_choice" and o.value == "identity_recast"
                        for o in ledger.obligations) == 1,
                    "fiction_recast_choice", "fictional identity remapping lacks its explicit author choice")
    require(sorted(plan.relations) == sorted(expected_relations), "relation_licence", "missing or extra causal/temporal assertion")
    for label, left, right in plan.relations:
        budget.tick()
        require(plan.order.index(left) < plan.order.index(right), "temporal_order", "causal/temporal order violated")
    declared_narrators = {o.value for o in ledger.obligations if o.kind == "viewpoint"}
    require(plan.narrator in (declared_narrators or {"omniscient"}), "narrator_licence", "unlicensed narrator")
    if plan.narrator != "omniscient":
        for node in plan.nodes:
            budget.tick()
            require(node.atom.agent == plan.narrator and
                    all(a.agent == plan.narrator for a in node.atom.condition),
                    "viewpoint_access", "focal narrator lacks an explicit access path", "UNKNOWN_CONTENT_VIEWPOINT")
    initial = tuple(sorted({o.state for o in ledger.obligations if o.kind == "initial"}, key=lambda s: (s.key(), s.value, s.positive)))
    require(initial == plan.initial, "initial_state", "initial state altered or fabricated")
    for state in initial:
        _state_lookup(initial, state, budget)
    states = initial
    transitions = {t.node: t for t in plan.transitions}
    require(len(transitions) == len(plan.transitions), "transition_ids", "duplicate transition")
    require(set(transitions).issubset(nodes), "transition_nodes", "transition refers to absent event")
    rules = {rule.id: rule for rule in ledger.rules}
    require(len(rules) == len(ledger.rules), "rule_identity", "duplicate rule identity")
    for node_id in plan.order:
        budget.tick()
        node = nodes[node_id]
        if node.atom.kind == "state" and node.phase != "initial" and not node.atom.condition:
            wanted = State(node.atom.agent, node.atom.fluent, node.atom.value,
                           node.atom.world, not node.atom.negated)
            known = _state_lookup(states, wanted, budget)
            require(known is True, "narrated_state", "narrated state false or unknown at this point",
                    "CONTENT_STATE_CONFLICT" if known is False else "UNKNOWN_CONTENT_STATE")
        matching = [r for r in ledger.rules if r.action.event_key() == node.atom.event_key()]
        budget.tick(amount=max(1, len(ledger.rules)))
        if matching:
            require(node.rule in rules and node_id in transitions, "transition_required", "declared action effects omitted")
        if not node.rule:
            require(node_id not in transitions, "transition_licence", "transition without a rule")
            continue
        require(node.rule in rules and node_id in transitions, "transition_rule", "unknown transition rule")
        rule, transition = rules[node.rule], transitions[node_id]
        supported = []
        for candidate in matching:
            budget.tick()
            if (all(_state_lookup(states, required, budget) is True for required in candidate.requires) and
                    all(_state_lookup(states, excluded, budget) is False for excluded in candidate.exceptions)):
                supported.append(candidate)
        effect_sets = {digest(tuple(sorted(r.effects, key=lambda s: (s.key(), s.value, s.positive)))) for r in supported}
        require(len(effect_sets) <= 1, "rule_effect_ambiguity", "different supported rule effects were arbitrarily chosen",
                "UNKNOWN_CONTENT_RULE_AMBIGUOUS")
        require(rule.action.event_key() == node.atom.event_key(), "rule_action", "rule applied to different roles/world/polarity")
        require(transition.rule == rule.id and transition.before == states, "transition_before", "state before transition is false")
        require(all(_state_lookup(states, state, budget) is True for state in rule.requires),
                "rule_preconditions", "rule precondition false or unknown", "UNKNOWN_CONTENT_PRECONDITION")
        require(all(_state_lookup(states, state, budget) is False for state in rule.exceptions),
                "rule_exceptions", "rule exception true or unknown", "UNKNOWN_CONTENT_EXCEPTION")
        states = _independent_update(states, rule.effects, budget)
        require(transition.after == states, "transition_effects", "wrong state effects")
    require(plan.final == states, "final_replay", "final plan state differs from replay")
    for obligation in ledger.obligations:
        budget.tick()
        if obligation.kind == "final":
            require(_state_lookup(states, obligation.state, budget) is True,
                    "final_goal", "requested final state false or unknown", "UNKNOWN_CONTENT_NO_PLAN")
    require(len(realization.clauses) == len(plan.order), "surface_coverage", "missing or extra surface clause")
    cursor, provenance = 0, []
    for index, clause in enumerate(realization.clauses):
        budget.tick()
        require(clause.node == plan.order[index] and clause.start == cursor and
                clause.start < clause.end <= len(realization.text),
                "surface_span", "surface span or node identity is invalid")
        body = realization.text[clause.start:clause.end]
        require(body.endswith("。"), "surface_terminator", "clause terminator absent")
        body = body[:-1]
        node = nodes[clause.node]
        prefix = "最初は、" if node.phase == "initial" else "最後は、" if node.phase == "final" else ""
        related = [r for r in plan.relations if r[2] == node.id]
        if related:
            require(len(related) == 1, "surface_relation", "multiple antecedents unsupported")
            label, left, _ = related[0]
            before = plan.order.index(left)
            if label == "List":
                prefix = "また、"
            elif before == index - 1:
                permitted = ("そのため、", "だから、") if label == "Cause" else ("その後、", "続いて、")
                prefix = next((p for p in permitted if body.startswith(p)), "<missing>")
            else:
                prefix = f"第{before + 1}文の出来事" + ("が原因で、" if label == "Cause" else "の後で、")
        require(body.startswith(prefix), "surface_discourse", "temporal/causal/phase connector changed")
        require(_atom_matches(node.atom, body[len(prefix):], plan.narrator, budget),
                "surface_semantics", "surface changes roles, polarity, time, quote or condition")
        for span in clause.expression_sources:
            budget.tick()
            source_text(span, sources)
            require(source_map[span.source].purpose == "expression", "expression_role", "expression source has wrong role")
            require(_expression_matches(node.atom, source_text(span, sources), clause.derivation, budget),
                    "expression_semantics", "expression witness does not license this grammar/derivation")
        require(clause.derivation in ("quotation", "paraphrase", "slot_substitution", "provenance_unknown"),
                "provenance_class", "unverified novelty/extraction classification")
        if clause.derivation == "quotation":
            require(node.atom.kind == "quote" and any(source_text(s, sources) == node.atom.quote for s in node.evidence),
                    "quotation_source", "quote is not an exact original substring")
        expression_obligations = [obligations[o] for o in node.obligations
                                  if obligations[o].value in
                                  ("expression_material", "expression_material_recast")]
        if expression_obligations:
            require(all(obligation.span in clause.expression_sources
                        for obligation in expression_obligations),
                    "expression_event_surface_binding",
                    "authored event surface lost its exact expression-source witness")
        if clause.derivation in ("paraphrase", "slot_substitution"):
            require(bool(clause.expression_sources), "expression_provenance", "expression classification has no witness")
        provenance.append({"node": node.id, "derivation": clause.derivation,
                           "expression_sources": [asdict(s) for s in clause.expression_sources],
                           "occurrence_evidence": [asdict(s) for s in node.evidence if source_map[s.source].purpose == "evidence"],
                           "creation_permission": node.permission,
                           "novelty_verified": False})
        cursor = clause.end
    require(cursor == len(realization.text), "surface_extra", "extra text outside licensed clauses")
    budget.size("output_chars", len(realization.text))
    return {"passed": True, "checks": checks, "provenance": provenance,
            "obligations": [{"id": o.id, "status": "satisfied"} for o in ledger.obligations],
            "quality": "unassessed", "novelty_verified": False}
