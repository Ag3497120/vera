"""Shape/type checks shared by the producer and the independent proof checker.

No evidence matching or interpretation happens here.
"""
from __future__ import annotations

from .semantic_ir import EventValue, Limit, Nominal, Operator, Plan, Quantity, Request, Span, Variable, typed


class Invalid(ValueError):
    pass


def occurrences(terms):
    for term in terms:
        if isinstance(term, Nominal):
            yield from occurrences((term.term,))
        elif isinstance(term, Variable):
            yield term


def variables(terms):
    out = {}
    for term in terms:
        current=term
        while isinstance(current,Nominal):
            if not isinstance(current.head,str) or not current.head: raise Invalid('nominal head type')
            current=current.term
        if current is not None and not isinstance(current,(Variable,str,bool,Quantity,EventValue)):
            raise Invalid('unsupported literal term type')
        if isinstance(current,Quantity) and not typed(current,'quantity'): raise Invalid('invalid literal quantity')
        if isinstance(current,EventValue) and not typed(current,'event'): raise Invalid('invalid event identity')
    for term in occurrences(terms):
        if not isinstance(term.name,str) or not term.name or term.sort not in ("entity", "event", "quantity", "value"):
            raise Invalid("unknown variable sort")
        if term.name in out and out[term.name] != term.sort:
            raise Invalid("variable has inconsistent sorts")
        out[term.name] = term.sort
    return out


def plan_shape(plan: Plan, depth: int = 8) -> dict[str, Operator]:
    if not plan.nodes or plan.nodes[-1].id != plan.root or plan.nodes[-1].op != "Project":
        raise Invalid("root must be the final Project")
    nodes = {}; bound = {}; sorts = {}
    for op in plan.nodes:
        if (not isinstance(op,Operator) or not isinstance(op.id,str) or not op.id or not isinstance(op.op,str)
            or not all(isinstance(getattr(op,f),tuple) for f in ('inputs','tests','terms','choices','outputs','obligations'))
            or not isinstance(op.unit,str) or not isinstance(op.relation,str) or type(op.absolute) is not bool):
            raise Invalid('operator field types')
        if op.id in nodes or any(i not in nodes for i in op.inputs):
            raise Invalid("duplicate/forward/cyclic plan reference")
        arity = {"Bind": 0, "Join": 2, "Filter": 1, "ApplyCondition": 1,
                 "Except": 1, "Sum": 1, "Difference": 1, "Compare": 1, "Project": 1}
        if op.op not in arity or len(op.inputs) != arity[op.op]:
            raise Invalid("operator arity")
        allowed = {
            "Bind": {"pattern", "relation", "target"}, "Join": set(),
            "ApplyCondition": set(), "Except": set(), "Filter": {"tests"},
            "Sum": {"terms", "target", "unit"},
            "Difference": {"terms", "target", "unit", "absolute"},
            "Compare": {"terms", "target", "relation", "choices"}, "Project": {"outputs"},
        }[op.op]
        if any(getattr(op, field) and field not in allowed for field in
               ("pattern", "tests", "terms", "target", "relation", "unit", "absolute", "choices", "outputs")):
            raise Invalid("unused operator field")
        available = set().union(*(bound[i] for i in op.inputs)) if op.inputs else set()
        declared = []
        if op.op == "Bind":
            if op.pattern is None or not op.pattern.predicate:
                raise Invalid("Bind requires a predicate")
            if not isinstance(op.pattern.roles,tuple) or not isinstance(op.pattern.modality,str) or not isinstance(op.pattern.time,str):
                raise Invalid('pattern field types')
            names = [k for k, _ in op.pattern.roles]
            if len(names) != len(set(names)):
                raise Invalid("duplicate pattern role")
            if op.pattern.polarity not in ("+", "-", "*"):
                raise Invalid("polarity")
            declared = list(op.pattern.terms()) + [op.pattern.event]
            if isinstance(op.pattern.event, Variable) and op.pattern.event.sort != "event":
                raise Invalid("event variable must have event sort")
            available.update(variables(declared))
            if op.relation:
                if op.relation not in ("whether", "whether-negative") or op.target is None or op.target.sort != "value":
                    raise Invalid("Bind result type")
                if op.target.name in available:
                    raise Invalid("target reassignment")
                available.add(op.target.name); declared.append(op.target)
            elif op.target is not None:
                raise Invalid("unexpected Bind target")
        else:
            if op.pattern is not None:
                raise Invalid("unexpected pattern")
            operands = [*op.terms, *op.choices, *(o.term for o in op.outputs),
                        *(t.left for t in op.tests), *(t.right for t in op.tests)]
            if set(variables(operands)) - available:
                raise Invalid("unbound operand")
            declared = operands
            if op.op in ("Sum", "Difference", "Compare"):
                if op.target is None or op.target.name in available:
                    raise Invalid("missing/reassigned target")
                expected = "quantity" if op.op in ("Sum", "Difference") else ("entity" if op.choices else "value")
                if op.target.sort != expected:
                    raise Invalid("target type")
                if (op.op == "Sum" and not op.terms or
                    op.op in ("Difference", "Compare") and len(op.terms) != 2):
                    raise Invalid("arithmetic operand arity")
                if op.op == "Compare" and (op.relation not in ("=", "!=", ">", "<", ">=", "<=")
                                            or len(op.choices) not in (0, 2)):
                    raise Invalid("comparison contract")
                available.add(op.target.name); declared.append(op.target)
            elif op.target is not None:
                raise Invalid("unexpected target")
            if op.op == "Filter" and (not op.tests or any(t.relation not in ("=", "!=", ">", "<", ">=", "<=") for t in op.tests)):
                raise Invalid("filter contract")
            if op.op == "Project":
                labels = [o.label for o in op.outputs]; ids = [o.obligation for o in op.outputs]
                if not labels or len(labels) != len(set(labels)) or len(ids) != len(set(ids)):
                    raise Invalid("duplicate/missing output")
        for occurrence in occurrences(declared):
            name, sort = occurrence.name, occurrence.sort
            if name in sorts and sorts[name] != sort:
                raise Invalid("variable has inconsistent sorts")
            sorts[name] = sort
        nodes[op.id] = op; bound[op.id] = available
    reachable = set(); todo = [plan.root]
    while todo:
        key = todo.pop()
        if key not in reachable:
            reachable.add(key); todo.extend(nodes[key].inputs)
    if reachable != set(nodes):
        raise Invalid("unreachable plan node")
    if plan.depth() > depth:
        raise Limit("depth")
    return nodes


def request_shape(request: Request, plan: Plan, budget) -> dict[str, Operator]:
    if request.unread:
        raise Invalid("unread mandatory request")
    if len(request.plans) > budget.parse:
        raise Limit("parse")
    if plan not in request.plans:
        raise Invalid("plan differs from the fixed request")
    nodes = plan_shape(plan, budget.depth)
    ids = [o.id for o in request.obligations]
    if not ids or len(ids) != len(set(ids)):
        raise Invalid("duplicate/missing obligation")
    spans = {"question": request.text}
    if any(not s.valid(spans) for s in request.covered):
        raise Invalid("request coverage span")
    covered = set(i for s in request.covered for i in range(s.start, s.end))
    if any(i not in covered for i, ch in enumerate(request.text) if not ch.isspace()):
        raise Invalid("uncovered request text")
    actual = [oid for n in plan.nodes for oid in n.obligations]
    if sorted(actual) != sorted(ids):
        raise Invalid("obligations do not correspond one-to-one to operators")
    for obligation in request.obligations:
        if (not obligation.span.valid(spans) or obligation.node not in nodes or
            obligation.id not in nodes[obligation.node].obligations):
            raise Invalid("obligation source/operator mismatch")
        operator = nodes[obligation.node]
        output = next((o for o in operator.outputs if o.obligation == obligation.id), None)
        origin = (output.span if output else None) or operator.span or Span('question',0,len(request.text),request.text)
        if obligation.span != origin: raise Invalid('obligation moved from its fixed operator source')
    outputs = nodes[plan.root].outputs
    output_ids = {o.id for o in request.obligations if o.kind == "output"}
    if {o.obligation for o in outputs} != output_ids:
        raise Invalid("output obligation missing or extra")
    return nodes
