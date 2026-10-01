"""Bounded relational producer. Only source clauses can supply a Bind.

Scores, neighbors, sentence positions, and old ANSWERs are not premises.
The independently implemented verifier checks every submitted derivation.
"""
from __future__ import annotations

from decimal import Decimal, Inexact, localcontext
from fractions import Fraction
from typing import Any

from .rewrite_core import match, substitute
from .semantic_ir import (Clause, EventValue, Limit, Meter, Nominal, Operator, Pattern, Plan, Proof,
                          ProofNode, Quantity, Row, Variable, View, typed, unit_type)


class Unresolved(Exception):
    def __init__(self, verdict: str, reason: str):
        self.verdict, self.reason = verdict, reason
        super().__init__(reason)


def _modality(wanted: str, actual: str) -> bool:
    if wanted == "normative":
        return actual in ("permission", "prohibition")
    return wanted == actual


def bind(pattern: Pattern, clause: Clause, initial: dict | None = None,
         *, opposite: bool = False) -> dict | None:
    if pattern.predicate not in ("*", clause.predicate) or not _modality(pattern.modality, clause.modality):
        return None
    pol = ("-" if pattern.polarity == "+" else "+") if opposite else pattern.polarity
    if pol != "*" and pol != clause.polarity:
        return None
    if pattern.time and pattern.time != clause.time:
        return None
    roles = {r.name: r.term for r in clause.roles}
    if any(name not in roles for name, _ in pattern.roles):
        return None
    terms = tuple(term for _, term in pattern.roles)
    actual = tuple(roles[name] for name, _ in pattern.roles)
    from .typed_edges import _tagger
    for wanted, value in zip(terms, actual):
        if isinstance(wanted, Nominal):
            if not isinstance(value, str):
                return None
            nouns = [t.surface for t in _tagger()(value) if t.feature.pos1 in ("名詞", "接尾辞")]
            if not nouns or nouns[-1] != wanted.head:
                return None
    terms = tuple(t.term if isinstance(t, Nominal) else t for t in terms)
    if any(isinstance(t, Variable) for t in actual):
        return None                       # no ungrounded universal instantiation
    env = match(("roles", *terms), ("roles", *actual), initial)
    if env is None:
        return None
    if any(isinstance(t, Variable) and not typed(env.get(t.name), t.sort) for t in terms):
        return None
    if pattern.event is not None:
        event = EventValue(clause.sovereign, clause.family, clause.event.name, clause.time)
        env = match(pattern.event, event, env)
        if env is None:
            return None
        if isinstance(pattern.event, Variable) and not typed(env.get(pattern.event.name), pattern.event.sort):
            return None
    return env


def _get(term: Any, env: dict) -> Any:
    if isinstance(term, Variable):
        value = substitute(term, env)
        if not typed(value, term.sort):
            raise Unresolved("UNKNOWN_TYPE", "bound value disagrees with variable sort")
        return value
    return term


def _rational(value: Any, unit: str) -> Fraction:
    if not typed(value, "quantity"):
        raise Unresolved("UNKNOWN_TYPE", "arithmetic requires a quantity")
    dim, factor = unit_type(value.unit)
    out_dim, out_factor = unit_type(unit)
    if dim != out_dim:
        raise Unresolved("UNKNOWN_UNITS", "incompatible quantity units")
    return Fraction(value.amount) * Fraction(factor) / Fraction(out_factor)


def _decimal(value: Fraction) -> Decimal:
    try:
        with localcontext() as ctx:
            ctx.prec = 128; ctx.traps[Inexact] = True
            out = Decimal(value.numerator) / Decimal(value.denominator)
        if not out.is_finite() or len(out.as_tuple().digits) > 128:
            raise Inexact
        return out
    except (Inexact, OverflowError) as exc:
        raise Unresolved("UNKNOWN_PRECISION", "result has no exact finite representation within 128 digits") from exc


def _quantity(value: Any, unit: str) -> Decimal:
    return _decimal(_rational(value, unit))


def _test(left: Any, relation: str, right: Any) -> bool:
    if isinstance(left, Quantity) or isinstance(right, Quantity):
        if not isinstance(left, Quantity) or not isinstance(right, Quantity):
            raise Unresolved("UNKNOWN_TYPE", "quantity compared to a non-quantity")
        a, b = _rational(left, left.unit), _rational(right, left.unit)
    else:
        a, b = left, right
    if relation == "=":
        return a == b
    if relation == "!=":
        return a != b
    if relation in (">", "<", ">=", "<="):
        if not isinstance(left, Quantity):
            raise Unresolved("UNKNOWN_TYPE", "ordered comparison requires quantities")
        return {">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b}[relation]
    raise Unresolved("UNKNOWN_OPERATOR", "unsupported comparison")


class Producer:
    def __init__(self, view: View, sovereign: str, meter: Meter):
        self.view, self.sovereign, self.meter = view, sovereign, meter
        self.clauses: list[Clause] = []
        self.index: dict[tuple[str, str, str], list[Clause]] = {}
        self.nodes: list[ProofNode] = []
        self.by_id: dict[str, ProofNode] = {}
        self.source_ids: dict[str, str] = {}
        self.refusals: set[tuple[str, str]] = set()
        self.effective_cache: dict[tuple, str] = {}
        self.witness_cache: dict[tuple, str] = {}
        self.depths: dict[str, int] = {}
        self.guard_depth_exceeded = False
        self.predicates: set[str] = set()

    def node(self, op, plan_node="", parents=(), *, clause=None, env=None,
             covers=(), answer=()) -> str:
        self.meter.spend()
        ident = f"p{len(self.nodes)}"
        n = ProofNode(ident, op, plan_node, tuple(parents), clause,
                      tuple(sorted((env or {}).items())), tuple(sorted(set(covers))), answer)
        self.nodes.append(n); self.by_id[ident] = n
        self.depths[ident] = 1 + max((self.depths[p] for p in parents), default=0)
        return ident

    def source(self, clause: Clause) -> str:
        if clause.id not in self.source_ids:
            self.source_ids[clause.id] = self.node("Source", clause=clause)
        return self.source_ids[clause.id]

    def _match(self, pattern, clause, env=None, *, opposite=False):
        self.meter.spend(1 + len(pattern.roles))
        return bind(pattern, clause, env, opposite=opposite)

    def _dedup(self, rows: list[Row]) -> list[Row]:
        unique = {}; states = set()
        for row in rows:
            self.meter.spend()
            # Equal bindings are not equal derivations until all scope is checked.
            key = (row.bindings, tuple(sorted(row.covers)), row.sources,
                   row.pending_conditions, row.pending_exceptions)
            unique.setdefault(key, row)
            states.add(row.bindings)
        self.meter.states(len(states))    # proofs are charged to steps, not binding states
        return list(unique.values())

    def _setup(self, plan: Plan):
        if self.view.invalid:
            raise Unresolved("UNKNOWN_INVALID_EVIDENCE", "; ".join(self.view.invalid))
        todo = [op.pattern.predicate for op in plan.nodes if op.pattern]
        visited = set(); by_id = {}; families = set()
        while todo:
            predicate = todo.pop(); self.meter.spend()
            if predicate in visited:
                continue
            visited.add(predicate)
            pool = (self.view.by_sovereign.get(self.sovereign, ()) if predicate == "*"
                    else self.view.by_predicate.get((self.sovereign, predicate), ()))
            for clause in pool:
                self.meter.spend()
                if clause.id in by_id:
                    continue
                by_id[clause.id] = clause; families.add(clause.family)
                self.meter.candidates += 1
                if self.meter.candidates > self.meter.budget.candidates:
                    raise Limit("candidates")
                self.meter.spend(len(clause.conditions) + len(clause.exceptions))
                todo.extend(p.predicate for p in (*clause.conditions, *clause.exceptions))
        if len(families) > 1:
            raise Unresolved("UNKNOWN_SOVEREIGN", "distinct families cannot share bindings")
        self.clauses = list(by_id.values())
        for clause in self.clauses:
            self.meter.spend()
            self.index.setdefault((clause.predicate, clause.polarity, clause.modality), []).append(clause)
            self.predicates.add(clause.predicate)

    def _candidates(self, pattern: Pattern, *, opposite=False):
        polarity = ("-" if pattern.polarity == "+" else "+") if opposite else pattern.polarity
        polarities = ("+", "-") if polarity == "*" else (polarity,)
        modalities = ("permission", "prohibition") if pattern.modality == "normative" else (pattern.modality,)
        predicates = self.predicates if pattern.predicate == "*" else (pattern.predicate,)
        for pred in predicates:
            for pol in polarities:
                for mod in modalities:
                    self.meter.spend()
                    yield from self.index.get((pred, pol, mod), ())

    def _support(self, pattern: Pattern, env: dict, trail=()) -> list[Clause]:
        out = []
        for clause in self._candidates(pattern):
            found = self._match(pattern, clause, env)
            if found == env and self._effective(clause, env, trail) == "yes":
                out.append(clause)
        return out

    def _effective(self, clause: Clause, env: dict, trail=()) -> str:
        self.meter.spend()
        if clause.id in trail:
            return "unknown"              # circular rules are not evidence
        key = (clause.id, tuple(sorted(env.items())), frozenset(trail))
        if key in self.effective_cache:
            return self.effective_cache[key]
        if len(trail) >= self.meter.budget.depth:
            self.guard_depth_exceeded = True
            return "unknown"            # another branch may have a short witness
        if clause.unsupported:
            return "unknown"
        for guard in clause.conditions:
            self.meter.spend()
            opposite = Pattern(guard.predicate, guard.roles,
                               "-" if guard.polarity == "+" else "+", guard.modality, guard.time, guard.event)
            positive = self._support(guard, env, (*trail, clause.id))
            negative = self._support(opposite, env, (*trail, clause.id))
            if positive and negative:
                raise Unresolved("UNKNOWN_CONTRADICTION", "opposing condition evidence")
            if not positive:
                result = "no" if negative else "unknown"
                self.effective_cache[key] = result; return result
        for guard in clause.exceptions:
            self.meter.spend()
            if self._support(guard, env, (*trail, clause.id)):
                self.effective_cache[key] = "no"; return "no"
            negative = Pattern(guard.predicate, guard.roles,
                               "-" if guard.polarity == "+" else "+", guard.modality, guard.time, guard.event)
            if not self._support(negative, env, (*trail, clause.id)):
                self.effective_cache[key] = "unknown"; return "unknown"
        self.effective_cache[key] = "yes"; return "yes"

    def _witness(self, clause: Clause, env: dict, trail=()) -> str:
        if clause.id in trail:
            raise Unresolved("UNKNOWN_CONDITION", "circular guard proof")
        key = (clause.id, tuple(sorted(env.items())), frozenset(trail))
        if key in self.witness_cache:
            return self.witness_cache[key]
        parents = [self.source(clause)]
        for guard in (*clause.conditions, *clause.exceptions):
            self.meter.spend()
            wanted = guard if guard in clause.conditions else Pattern(
                guard.predicate, guard.roles, "-" if guard.polarity == "+" else "+",
                guard.modality, guard.time, guard.event)
            support = self._support(wanted, env, (*trail, clause.id))
            if not support:
                raise Unresolved("UNKNOWN_CONDITION", "guard has no grounded witness")
            parents.append(self._best_witness(support, env, (*trail, clause.id)))
        ident = self.node("Witness", parents=tuple(parents), env=env)
        self.witness_cache[key] = ident; return ident

    def _best_witness(self, support, env, trail=()):
        choices = []
        for c in support:
            self.meter.spend()
            ident = self._witness(c, env, trail)
            if self.depths[ident] <= self.meter.budget.depth:
                choices.append(ident)
        if not choices: raise Limit('depth')
        # All choices prove the very same grounded guard. Minimize dependency
        # depth so a long valid alternative cannot hide a short one by order.
        return min(choices, key=lambda ident: self.depths[ident])

    def _bind(self, op: Operator) -> list[Row]:
        rows = []
        for clause in self._candidates(op.pattern):
            env = self._match(op.pattern, clause)
            if env is None:
                continue
            if clause.unsupported:
                self.refusals.add(("UNKNOWN_UNSUPPORTED_EVIDENCE", "; ".join(clause.unsupported)))
                continue
            # Applicable opponents outside the submitted proof matter equally.
            specific = Pattern(op.pattern.predicate, op.pattern.roles, clause.polarity,
                               op.pattern.modality, op.pattern.time, op.pattern.event)
            opposed = Pattern(specific.predicate, specific.roles,
                              '-' if specific.polarity == '+' else '+', specific.modality, specific.time, specific.event)
            if op.pattern.modality == 'normative':
                opposed = Pattern(specific.predicate, specific.roles, clause.polarity,
                                  'prohibition' if clause.modality == 'permission' else 'permission', specific.time, specific.event)
            for other in self._candidates(opposed):
                    if self._match(opposed, other, env) is not None:
                        if self._effective(clause, env) == "yes" and self._effective(other, env) == "yes":
                            raise Unresolved("UNKNOWN_CONTRADICTION", "applicable opposing evidence")
            if op.relation in ("whether", "whether-negative"):
                env[op.target.name] = (clause.modality == "permission" if op.pattern.modality == "normative"
                                       else clause.polarity == ("-" if op.relation == "whether-negative" else "+"))
            ident = self.node("Bind", op.id, (self.source(clause),), env=env, covers=op.obligations)
            rows.append(Row(tuple(sorted(env.items())), ident, op.obligations, (clause.id,),
                            (clause.id,) if clause.conditions else (),
                            (clause.id,) if clause.exceptions else ()))
        return self._dedup(rows)

    def _scope(self, op: Operator, rows: list[Row]) -> list[Row]:
        out = []
        for row in rows:
            env = dict(row.bindings); supports = []; valid = True
            pending = row.pending_conditions if op.op == "ApplyCondition" else row.pending_exceptions
            for source_id in pending:
                self.meter.spend()
                clause = self.view.by_id[source_id]
                patterns = clause.conditions if op.op == "ApplyCondition" else clause.exceptions
                for pattern in patterns:
                    self.meter.spend()
                    opposite = Pattern(pattern.predicate, pattern.roles,
                                       "-" if pattern.polarity == "+" else "+", pattern.modality, pattern.time, pattern.event)
                    positive = self._support(pattern, env)
                    negative = self._support(opposite, env)
                    if positive and negative:
                        raise Unresolved("UNKNOWN_CONTRADICTION", "opposing condition evidence")
                    matching = positive if op.op == "ApplyCondition" else negative
                    if (op.op == "Except" and positive) or not matching:
                        if not matching and self.guard_depth_exceeded: raise Limit('depth')
                        verdict = "UNKNOWN_EXCEPTION" if op.op == "Except" and positive else "UNKNOWN_CONDITION"
                        self.refusals.add((verdict, "condition/exception applicability has no sufficient explicit evidence"))
                        valid = False; break
                    supports.append(self._best_witness(matching, env))
                if not valid:
                    break
            if not valid:
                continue
            covers = tuple(set(row.covers) | set(op.obligations))
            ident = self.node(op.op, op.id, (row.proof, *supports), env=env, covers=covers)
            out.append(Row(row.bindings, ident, covers, row.sources,
                           () if op.op == "ApplyCondition" else row.pending_conditions,
                           () if op.op == "Except" else row.pending_exceptions))
        return self._dedup(out)

    def run(self, plan: Plan) -> tuple[list[tuple[tuple, Proof]], dict]:
        from .semantic_validate import Invalid, plan_shape
        try:
            self.meter.shape(plan)
            plan_shape(plan, self.meter.budget.depth)
        except Invalid as exc:
            raise Unresolved("UNKNOWN_PLAN", str(exc)) from exc
        self._setup(plan)
        tables = {}; answers = {}
        for op in plan.nodes:
            self.meter.spend()
            inputs = [tables[i] for i in op.inputs]
            if op.op == "Bind":
                result = self._bind(op)
            elif op.op == "Join":
                result = []
                for left in inputs[0]:
                    for right in inputs[1]:
                        self.meter.spend()
                        env = dict(left.bindings); other = dict(right.bindings)
                        shared = env.keys() & other.keys()
                        if match(("join", *(Variable(k) for k in sorted(shared))),
                                 ("join", *(other[k] for k in sorted(shared))), env) is None:
                            continue
                        env.update(other)
                        covers = tuple(set(left.covers) | set(right.covers) | set(op.obligations))
                        ident = self.node("Join", op.id, (left.proof, right.proof), env=env, covers=covers)
                        result.append(Row(tuple(sorted(env.items())), ident, covers,
                            tuple(sorted(set(left.sources) | set(right.sources))),
                            tuple(sorted(set(left.pending_conditions) | set(right.pending_conditions))),
                            tuple(sorted(set(left.pending_exceptions) | set(right.pending_exceptions)))))
            elif op.op in ("ApplyCondition", "Except"):
                result = self._scope(op, inputs[0])
            else:
                result = []
                for row in inputs[0]:
                    self.meter.spend()
                    env = dict(row.bindings); answer = ()
                    if op.op == "Filter":
                        if not all(_test(_get(t.left, env), t.relation, _get(t.right, env)) for t in op.tests):
                            continue
                    elif op.op in ("Sum", "Difference"):
                        values = [_get(t, env) for t in op.terms]
                        if any(not isinstance(v, Quantity) or not v.amount.is_finite() for v in values):
                            raise Unresolved("UNKNOWN_TYPE", "non-finite/non-quantity operand")
                        unit = op.unit or values[0].unit
                        amounts = [_rational(v, unit) for v in values]
                        amount = sum(amounts, Fraction(0)) if op.op == "Sum" else amounts[0] - amounts[1]
                        env[op.target.name] = Quantity(_decimal(abs(amount) if op.absolute else amount), unit)
                    elif op.op == "Compare":
                        a, b = (_get(t, env) for t in op.terms)
                        decision = _test(a, op.relation, b)
                        if op.choices:
                            if _test(a, "=", b):
                                raise Unresolved("UNKNOWN_AMBIGUOUS", "comparison has equal values")
                            env[op.target.name] = _get(op.choices[0 if decision else 1], env)
                        else:
                            env[op.target.name] = decision
                    elif op.op == "Project":
                        if row.pending_conditions or row.pending_exceptions:
                            self.refusals.add(("UNKNOWN_CONDITION", "unresolved source scope at Project")); continue
                        answer = tuple((o.label, Quantity(_quantity(_get(o.term, env), o.unit), o.unit)
                                        if o.unit else _get(o.term, env)) for o in op.outputs)
                    else:
                        raise Unresolved("UNKNOWN_OPERATOR", op.op)
                    if op.target is not None and not typed(env.get(op.target.name), op.target.sort):
                        raise Unresolved("UNKNOWN_TYPE", "result type")
                    covers = tuple(set(row.covers) | set(op.obligations))
                    ident = self.node(op.op, op.id, (row.proof,), env=env, covers=covers, answer=answer)
                    if answer: answers[ident] = answer
                    result.append(Row(tuple(sorted(env.items())), ident, covers, row.sources,
                                      row.pending_conditions, row.pending_exceptions))
            tables[op.id] = self._dedup(result)
        proposals = []
        for row in tables[plan.root]:
            reachable = set(); ordered = []
            def visit(ident, depth=1):
                self.meter.spend()
                if depth > self.meter.budget.depth:
                    raise Limit("depth")
                if ident in reachable:
                    return
                reachable.add(ident)
                for parent in self.by_id[ident].parents:
                    visit(parent, depth + 1)
                ordered.append(self.by_id[ident])
            visit(row.proof)
            proof_nodes = tuple(ordered)
            proposals.append((answers[row.proof], Proof(proof_nodes, row.proof, self.sovereign)))
        if not proposals and self.refusals:
            verdict, reason = sorted(self.refusals)[0]
            raise Unresolved(verdict, reason)
        return proposals, {"steps": self.meter.steps, "candidates": self.meter.candidates,
                           "peak_bindings": self.meter.peak_bindings, "plan_depth": plan.depth(),
                           "unresolved_alternative_derivations": sorted(self.refusals)}
