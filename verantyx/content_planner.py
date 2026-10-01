"""Bounded content planning over prescribed events and explicit local rules.

The finite planner can insert missing rule actions only under an explicit
AUTHOR_CHOICE(events) permission. Unknown preconditions are never false and
never satisfied. Equivalent clause order is canonical; different state
histories require explicit order choice or cause typed ambiguity.
"""
from __future__ import annotations

from dataclasses import replace
from collections import deque

from .content_ir import (Atom, Budget, ContentError, Ledger, Node, Plan, Span,
                         State, Transition, digest, state_holds)
from .content_reader import read_atom, segments


def _ordered_states(states) -> tuple:
    return tuple(sorted(states, key=lambda s: (s.key(), s.value, s.positive)))


def _check_state(states: tuple, budget: Budget) -> None:
    for i, left in enumerate(states):
        for right in states[i + 1:]:
            budget.tick()
            if left.key() == right.key() and (
                left.value == right.value and left.positive != right.positive or
                left.positive and right.positive and left.value != right.value
            ):
                raise ContentError("CONTENT_STATE_CONFLICT", "exclusive local state is contradictory",
                                   subject=left.subject, fluent=left.fluent, world=left.world)


def _apply(states: tuple, effects: tuple, budget: Budget) -> tuple:
    """Declared exclusive effects end an old state; absence adds no negation."""
    _check_state(effects, budget)
    result = list(states)
    for effect in effects:
        kept = []
        for own in result:
            budget.tick()
            if own.key() != effect.key() or (
                not effect.positive and own.value != effect.value
            ):
                kept.append(own)
        kept.append(effect)
        result = kept
    result = _ordered_states(set(result))
    _check_state(result, budget)
    return result


def _holds(states: tuple, wanted: State, budget: Budget):
    budget.tick(amount=max(1, len(states)))
    return state_holds(states, wanted)


def _evidence(ledger: Ledger, budget: Budget) -> dict:
    supported = {}
    for source in ledger.materials:
        budget.tick()
        # Sovereign expression material cannot become occurrence testimony.
        if source.purpose != "evidence" or source.family in ("narrative", "paraphrase_entail"):
            continue
        for start, end, text in segments(source.text):
            budget.tick("candidates")
            try:
                atom = read_atom(text, budget, "actual")
            except ContentError as error:
                if error.verdict == "UNKNOWN_CONTENT_BUDGET":
                    raise
                continue
            supported.setdefault(atom.key(), []).append(Span.of(source, start, end))
    return {key: tuple(sorted(spans, key=lambda s: (s.source, s.start, s.end)))
            for key, spans in supported.items()}


def build_plan(ledger: Ledger, budget: Budget | None = None) -> Plan:
    budget = budget or Budget()
    if ledger.unread:
        raise ContentError("UNKNOWN_CONTENT_UNREAD", "mandatory brief text remains uninterpreted",
                           unread=[(s.start, s.end) for s in ledger.unread])
    obligations = {o.id: o for o in ledger.obligations}
    if len(obligations) != len(ledger.obligations):
        raise ContentError("CONTENT_CONSTRAINT_VIOLATION", "duplicate obligation identity")
    permission = next((o.id for o in ledger.obligations if o.kind == "mode" and o.value == "fiction"), "")
    author_events = next((o.id for o in ledger.obligations if o.kind == "author_choice" and o.value == "events"), "")
    author_order = next((o.id for o in ledger.obligations if o.kind == "author_choice" and o.value == "order"), "")
    tense = next((o.value for o in ledger.obligations if o.kind == "tense"), "present")
    narrators = {o.value for o in ledger.obligations if o.kind == "viewpoint"}
    if len(narrators) > 1:
        raise ContentError("CONTENT_CONSTRAINT_CONFLICT", "incompatible viewpoints")
    narrator = next(iter(narrators), "omniscient")
    initial = _ordered_states({o.state for o in ledger.obligations if o.kind == "initial"})
    final_required = tuple(o.state for o in ledger.obligations if o.kind == "final")
    _check_state(initial, budget)
    _check_state(final_required, budget)
    sentences = {o.number for o in ledger.obligations if o.kind == "sentences"}
    if len(sentences) > 1:
        raise ContentError("CONTENT_CONSTRAINT_CONFLICT", "incompatible exact sentence counts")
    target_sentences = next(iter(sentences), 0)
    facts = _evidence(ledger, budget) if ledger.mode == "actual" else {}
    fixed, initial_nodes, final_nodes = [], [], []
    forbidden = tuple(o.atom for o in ledger.obligations if o.kind == "forbid_event")
    for obligation in ledger.obligations:
        budget.tick()
        if obligation.kind not in ("event", "initial", "final"):
            continue
        atom = obligation.atom or obligation.state.as_atom(tense)
        for ban in forbidden:
            budget.tick()
            if atom.event_key() == ban.event_key():
                raise ContentError("CONTENT_CONSTRAINT_CONFLICT", "a mandatory event is also forbidden",
                                   obligation=obligation.id)
        evidence = facts.get(atom.key(), ())
        if obligation.value in ("material_evidence", "expression_material", "expression_material_recast"):
            # A material-derived obligation remains bound to the exact source
            # clause that the reader parsed; matching duplicates cannot replace it.
            evidence = (obligation.span,)
        if atom.kind == "quote":
            original = ledger.brief.text[obligation.span.start:obligation.span.end]
            offset = original.find(atom.quote)
            if offset < 0:
                raise ContentError("CONTENT_CONSTRAINT_VIOLATION", "quoted substring unavailable")
            evidence += (Span.of(ledger.brief, obligation.span.start + offset,
                                 obligation.span.start + offset + len(atom.quote)),)
        if ledger.mode == "actual" and not evidence:
            raise ContentError("UNKNOWN_CONTENT_EVIDENCE", "no complete evidence for the requested clause",
                               obligation=obligation.id)
        if ledger.mode == "actual" and atom.kind == "quote" and atom.agent and atom.key() not in facts:
            raise ContentError("UNKNOWN_CONTENT_EVIDENCE", "quote does not establish that the speaker said it")
        node_permission = (author_events if obligation.value in ("expression_material", "expression_material_recast")
                           else permission if ledger.mode == "fiction" else "")
        node = Node("n:" + obligation.id, atom, (obligation.id,), evidence,
                    node_permission,
                    accessible_to=(atom.agent,) if atom.agent else (), phase=obligation.kind)
        if obligation.kind == "initial":
            initial_nodes.append(node)
        elif obligation.kind == "final":
            final_nodes.append(node)
        else:
            fixed.append(node)
    if not fixed and not final_nodes and not initial_nodes:
        raise ContentError("UNKNOWN_CONTENT_NO_PLAN", "no supported required content")
    required_edges = []
    for obligation in ledger.obligations:
        budget.tick()
        if obligation.kind == "relation":
            label, left, right = obligation.relation
            if left not in obligations or right not in obligations:
                raise ContentError("CONTENT_CONSTRAINT_VIOLATION", "relation references an absent obligation")
            if ledger.mode == "actual":
                summary = obligations.get(obligation.value)
                if (label != "List" or summary is None or summary.kind != "source_summary" or
                        obligations[left].value != "material_evidence" or
                        obligations[right].value != "material_evidence"):
                    raise ContentError("UNKNOWN_CONTENT_EVIDENCE",
                                       "factual material supports clauses, not an inferred causal/temporal relation")
                required_edges.append((label, "n:" + left, "n:" + right))
                continue
            if label == "List":
                raise ContentError("UNKNOWN_CONTENT_PERMISSION", "a neutral source-list relation is limited to source summaries")
            left_atom, right_atom = obligations[left].atom, obligations[right].atom
            if (left_atom is None or right_atom is None or left_atom.condition or right_atom.condition or
                    left_atom.world != right_atom.world):
                raise ContentError("UNKNOWN_CONTENT_SCOPE", "C1 relation cannot cross a conditional/world scope")
            required_edges.append((label, "n:" + left, "n:" + right))
    base_nodes = len(initial_nodes) + len(final_nodes)
    if target_sentences and base_nodes + len(fixed) > target_sentences:
        raise ContentError("CONTENT_CONSTRAINT_CONFLICT", "too many mandatory clauses for exact sentence count")
    entities = set()
    worlds = {"fiction" if ledger.mode == "fiction" else "actual"}
    for atom in [n.atom for n in fixed + initial_nodes + final_nodes] + [r.action for r in ledger.rules]:
        budget.tick()
        entities.update(atom.names())
        if atom.kind == "state" and atom.fluent in ("owner", "location"):
            entities.add(atom.value)
        worlds.add(atom.world)
    for rule in ledger.rules:
        for state in rule.requires + rule.effects + rule.exceptions:
            budget.tick()
            entities.add(state.subject)
            if state.fluent in ("owner", "location"):
                entities.add(state.value)
            worlds.add(state.world)
    budget.size("entities", len(entities))
    budget.size("worlds", len(worlds))
    budget.size("nodes", base_nodes + len(fixed))
    budget.size("events", sum(n.atom.kind == "event" for n in fixed))
    if narrator != "omniscient" and narrator not in entities:
        raise ContentError("UNKNOWN_CONTENT_VIEWPOINT", "focal entity is not identified")
    if narrator != "omniscient":
        for node in fixed + initial_nodes + final_nodes:
            budget.tick()
            if narrator not in node.accessible_to:
                raise ContentError("UNKNOWN_CONTENT_VIEWPOINT", "no supplied access path for focal narrator", node=node.id)
    # Sequence search counts every expansion, precondition, state update and
    # inner binding. Input order is not a chronology licence.
    queue = deque([(tuple(fixed), initial, (), (), frozenset())])
    solutions, blocked_preconditions, blocked_exceptions = {}, False, False
    blocked_state_false = blocked_state_unknown = False
    while queue:
        budget.size("frontier", len(queue))
        remaining, states, sequence, transitions, used_optional = queue.popleft()
        budget.tick("plans")
        budget.tick()
        depth = len(sequence)
        budget.size("depth", depth)
        goals = all(_holds(states, goal, budget) is True for goal in final_required)
        exact = not target_sentences or base_nodes + depth == target_sentences
        if not remaining and goals and exact:
            # Neutral clauses are order-equivalent. State histories are not.
            signature = digest((sorted(n.atom.key() for n in sequence),
                                sorted(required_edges),
                                [(next(n.atom.key() for n in sequence if n.id == t.node), t.before, t.after)
                                 for t in transitions]))
            candidate = (sequence, transitions, states)
            if signature not in solutions or digest(candidate) < digest(solutions[signature]):
                solutions[signature] = candidate
            continue
        if depth >= budget.limits["depth"] or target_sentences and base_nodes + depth >= target_sentences:
            continue
        options = [(node, False) for node in remaining]
        if author_events and ledger.mode == "fiction":
            for rule in sorted(ledger.rules, key=lambda r: (r.action.key(), r.id)):
                budget.tick()
                if rule.id not in used_optional and not any(rule.action.event_key() == n.atom.event_key() for n in remaining):
                    atom = replace(rule.action, tense=tense)
                    options.append((Node("a:" + rule.id, atom, (), (rule.source,), author_events), True))
        for node, optional in sorted(options, key=lambda pair: (pair[0].atom.key(), pair[0].id)):
            budget.tick("candidates")
            budget.tick()
            emitted = {n.id for n in sequence}
            ready = True
            for label, left, right in required_edges:
                budget.tick()
                if right == node.id and left not in emitted:
                    ready = False
            if not ready:
                continue
            if node.atom.kind == "state" and not node.atom.condition:
                wanted = State(node.atom.agent, node.atom.fluent, node.atom.value,
                               node.atom.world, not node.atom.negated)
                holds = _holds(states, wanted, budget)
                if holds is not True:
                    blocked_state_false |= holds is False
                    blocked_state_unknown |= holds is None
                    continue
            if any(node.atom.event_key() == ban.event_key() for ban in forbidden):
                budget.tick(amount=max(1, len(forbidden)))
                continue
            matches = []
            for rule in ledger.rules:
                budget.tick()
                if node.atom.event_key() == rule.action.event_key():
                    matches.append(rule)
            applicable = []
            for rule in matches:
                budget.tick()
                conditions = [_holds(states, required, budget) for required in rule.requires]
                exceptions = [_holds(states, excluded, budget) for excluded in rule.exceptions]
                # Unknown exceptions do not mean 'exception absent'.
                if any(value is not False for value in exceptions):
                    blocked_exceptions = True
                    continue
                if all(value is True for value in conditions):
                    applicable.append(rule)
                else:
                    blocked_preconditions = True
            if matches and not applicable:
                continue
            effects = {digest(tuple(sorted(rule.effects, key=lambda s: (s.key(), s.value, s.positive)))) for rule in applicable}
            if len(effects) > 1:
                raise ContentError("UNKNOWN_CONTENT_RULE_AMBIGUOUS", "supported local rules disagree on action effects")
            if not matches:
                applicable = [None]
            for rule in applicable:
                budget.tick()
                updated = _apply(states, rule.effects, budget) if rule else states
                if optional and updated == states:
                    continue
                emitted_node = replace(node, rule=rule.id, evidence=tuple(sorted(set(
                    node.evidence + tuple(r.source for r in applicable if r is not None)
                ), key=lambda s: (s.source, s.start, s.end)))) if rule else node
                additions = (Transition(node.id, rule.id, states, updated),) if rule else ()
                next_remaining = tuple(n for n in remaining if n.id != node.id)
                next_used = used_optional | ({rule.id} if optional else set())
                queue.append((next_remaining, updated, sequence + (emitted_node,),
                              transitions + additions, frozenset(next_used)))
                budget.size("frontier", len(queue))
    if not solutions:
        if blocked_state_false:
            raise ContentError("CONTENT_STATE_CONFLICT", "a narrated state contradicts the current explicit state")
        if blocked_state_unknown:
            raise ContentError("UNKNOWN_CONTENT_STATE", "a narrated state has no explicit current-state support")
        if blocked_exceptions:
            raise ContentError("UNKNOWN_CONTENT_EXCEPTION", "rule exception is true or unresolved")
        if blocked_preconditions:
            raise ContentError("UNKNOWN_CONTENT_PRECONDITION", "no complete supplied rule preconditions")
        if required_edges and not final_required:
            raise ContentError("CONTENT_CONSTRAINT_CONFLICT", "required temporal/causal graph has no plan")
        raise ContentError("UNKNOWN_CONTENT_NO_PLAN", "final state or format cannot be achieved with licensed actions")
    if len(solutions) > 1 and not author_order and not author_events:
        raise ContentError("UNKNOWN_CONTENT_AMBIGUOUS", "distinct permitted state histories remain", candidates=len(solutions))
    sequence, transitions, final = min(solutions.values(), key=digest)
    nodes = tuple(initial_nodes) + sequence + tuple(final_nodes)
    budget.size("nodes", len(nodes))
    budget.size("events", sum(n.atom.kind == "event" for n in nodes))
    used_material_events = any(
        obligations[obligation_id].value in ("expression_material", "expression_material_recast")
        for node in sequence for obligation_id in node.obligations
    )
    used_identity_recast = any(
        obligations[obligation_id].value == "expression_material_recast"
        for node in sequence for obligation_id in node.obligations
    )
    used_material_order = any(
        obligation.kind == "relation" and obligation.value == author_order
        for obligation in ledger.obligations
    ) if author_order else False
    choices = tuple(x for x in (
        "events" if any(n.id.startswith("a:") for n in sequence) or used_material_events else "",
        "identity_recast" if used_identity_recast else "",
        "order" if used_material_order or len(solutions) > 1 and author_order else "",
    ) if x)
    return Plan(ledger.hash, nodes, tuple(n.id for n in nodes), tuple(required_edges),
                initial, final, transitions, narrator, choices)
