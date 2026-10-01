"""Plan-only realization: no raw brief, stored answer or lexical random walk.

Ordinary clauses reuse Frame's existing conjugation. C adds only finite state,
quotation, conditional and relation shells. The planner supplies all event
roles; expression sources remain nonfactual witnesses and cannot add effects.
"""
from __future__ import annotations

from .content_ir import Atom, Budget, ClauseSpan, ContentError, Plan, Realization, Span
from .content_reader import read_atom, segments
from .realize import conjugate


def _name(name: str, narrator: str) -> str:
    return "私" if name and name == narrator else name


def atom_text(atom: Atom, narrator: str = "omniscient", budget: Budget | None = None) -> str:
    budget = budget or Budget()
    budget.tick()
    past = atom.tense == "past"
    name = _name(atom.agent, narrator)
    if atom.kind == "event":
        verb = conjugate(atom.predicate, past=past, neg=atom.negated)
        if not verb or not name:
            raise ContentError("UNKNOWN_CONTENT_REALIZATION", "event has no licensed verb realization")
        result = name + "が"
        if atom.recipient:
            result += _name(atom.recipient, narrator) + "に"
        if atom.patient:
            result += _name(atom.patient, narrator) + "を"
        result += verb
    elif atom.kind == "state":
        if atom.fluent == "open" and atom.value in ("open", "closed"):
            stem = "開いて" if atom.value == "open" else "閉じて"
            ending = ("いなかった" if past else "いない") if atom.negated else ("いた" if past else "いる")
            result = name + "は" + stem + ending
        elif atom.fluent == "owner":
            ending = ("ではなかった" if past else "ではない") if atom.negated else ("だった" if past else "だ")
            result = name + "は" + _name(atom.value, narrator) + "の持ち物" + ending
        elif atom.fluent == "location":
            ending = ("いなかった" if past else "いない") if atom.negated else ("いた" if past else "いる")
            result = name + "は" + _name(atom.value, narrator) + "に" + ending
        else:
            raise ContentError("UNKNOWN_CONTENT_REALIZATION", "unsupported finite state fluent")
    elif atom.kind == "quote":
        result = (name + "は" if name else "引用：") + "「" + atom.quote + "」"
        if name:
            result += "と" + ("述べた" if past else "述べる")
    else:
        raise ContentError("UNKNOWN_CONTENT_REALIZATION", "unsupported node kind")
    if atom.condition:
        if len(atom.condition) != 1:
            raise ContentError("UNKNOWN_CONTENT_REALIZATION", "only one explicit conditional antecedent is supported")
        antecedent = atom_text(atom.condition[0], narrator, budget)
        # This remains in a hypothetical world; no antecedent occurrence is asserted.
        result = "もし" + antecedent + "なら、" + result
    return result


def connector(plan: Plan, node_id: str) -> str:
    relations = [r for r in plan.relations if r[2] == node_id]
    if not relations:
        return ""
    # A single anaphoric connector must have a unique licensed antecedent.
    if len(relations) != 1:
        raise ContentError("UNKNOWN_CONTENT_REALIZATION", "multiple relation antecedents need a richer shell")
    label, left, right = relations[0]
    before = plan.order.index(left)
    current = plan.order.index(right)
    if before >= current:
        raise ContentError("CONTENT_CONSTRAINT_VIOLATION", "relation disagrees with narrative order")
    if label == "List":
        return "また、"
    if before == current - 1:
        return "そのため、" if label == "Cause" else "その後、"
    return (f"第{before + 1}文の出来事が原因で、" if label == "Cause" else
            f"第{before + 1}文の出来事の後で、")


def realize_plan(plan: Plan, *, expression_materials: tuple = (), budget: Budget | None = None) -> Realization:
    budget = budget or Budget()
    budget.tick("surfaces")
    expressions = []
    for source in expression_materials:
        budget.tick()
        if source.purpose != "expression":
            continue
        for start, end, text in segments(source.text):
            budget.tick()
            try:
                atom = read_atom(text, budget, "fiction")
            except ContentError as error:
                if error.verdict == "UNKNOWN_CONTENT_BUDGET":
                    raise
                continue
            expressions.append((atom, Span.of(source, start, end)))
    by_id = {n.id: n for n in plan.nodes}
    text, clauses = "", []
    for node_id in plan.order:
        budget.tick()
        if node_id not in by_id:
            raise ContentError("CONTENT_CONSTRAINT_VIOLATION", "unavailable realization node")
        node = by_id[node_id]
        prefix = "最初は、" if node.phase == "initial" else "最後は、" if node.phase == "final" else connector(plan, node_id)
        sentence = prefix + atom_text(node.atom, plan.narrator, budget) + "。"
        witnesses, derivation = [], "provenance_unknown"
        # Actual-world nodes must cite their evidence sources through the
        # planner's separate occurrence evidence path. Fiction nodes selected
        # from material obligations must keep the exact source clause chosen
        # by that obligation; structurally similar clauses from other sources
        # cannot be attached as extra witnesses.
        if node.atom.world != "fiction":
            eligible_expressions = ()
        elif node.permission and node.evidence:
            expected_spans = {
                (span.source, span.start, span.end, span.sha256)
                for span in node.evidence
            }
            eligible_expressions = tuple(
                (expression, span) for expression, span in expressions
                if (span.source, span.start, span.end, span.sha256) in expected_spans
            )
        else:
            eligible_expressions = expressions
        for expression, span in eligible_expressions:
            budget.tick()
            if (expression.kind == node.atom.kind == "event" and
                    not expression.condition and not node.atom.condition and
                    expression.predicate == node.atom.predicate and
                    bool(expression.patient) == bool(node.atom.patient) and
                    bool(expression.recipient) == bool(node.atom.recipient)):
                witnesses.append(span)
                derivation = "paraphrase" if expression.key() == node.atom.key() else "slot_substitution"
        if node.atom.kind == "quote":
            derivation = "quotation"
        start = len(text)
        text += sentence
        clauses.append(ClauseSpan(node.id, start, len(text), derivation,
                                  tuple(sorted(witnesses, key=lambda s: (s.source, s.start, s.end)))))
        budget.size("output_chars", len(text))
    return Realization(plan.hash, text, tuple(clauses))
