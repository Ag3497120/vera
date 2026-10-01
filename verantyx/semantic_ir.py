"""Source-bound clauses and relational plans for the opt-in Round5-A path.

This is an evidence contract, not another generic rewriting engine. Variables
are rewrite_core.Var with a sort; the producer uses its existing matcher.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from decimal import Decimal
from typing import Any

from .rewrite_core import Var


@dataclass(frozen=True)
class Variable(Var):
    sort: str = "entity"                  # entity / value / quantity / event


@dataclass(frozen=True)
class Span:
    source: str
    start: int
    end: int
    text: str

    def valid(self, sources: dict[str, str]) -> bool:
        if (not isinstance(self.source,str) or not isinstance(self.text,str) or
            type(self.start) is not int or type(self.end) is not int): return False
        raw = sources.get(self.source)
        return (raw is not None and 0 <= self.start < self.end <= len(raw)
                and raw[self.start:self.end] == self.text)


@dataclass(frozen=True)
class Quantity:
    amount: Decimal
    unit: str

    def __str__(self) -> str:
        # Decimal.normalize() applies the ambient precision, even for display.
        raw = format(self.amount, 'f')
        if '.' in raw:
            raw = raw.rstrip('0').rstrip('.')
        return raw + self.unit


@dataclass(frozen=True)
class EventValue:
    sovereign: str
    family: str
    identity: str
    time: str


@dataclass(frozen=True)
class Nominal:
    """A syntactic noun head restriction, not substring similarity."""
    head: str
    term: Any


# Physical conversions are proof rules, not vocabulary/route similarity.
UNITS = {
    "kg": ("mass", Decimal(1000)), "g": ("mass", Decimal(1)),
    "m": ("length", Decimal(1)), "cm": ("length", Decimal('.01')),
    "km": ("length", Decimal(1000)), "L": ("volume", Decimal(1)),
    "ml": ("volume", Decimal('.001')), "mL": ("volume", Decimal('.001')),
    "時間": ("duration", Decimal(3600)), "分": ("duration", Decimal(60)),
    "秒": ("duration", Decimal(1)),
}


def unit_type(unit: str) -> tuple[str, Decimal]:
    return UNITS.get(unit, ("counter:" + unit, Decimal(1)))


@dataclass(frozen=True)
class Role:
    name: str
    term: Any
    span: Span
    rule: str = "literal"                 # literal / quantity / nominal / frame


@dataclass(frozen=True)
class Pattern:
    predicate: str
    roles: tuple[tuple[str, Any], ...]
    polarity: str = "+"
    modality: str = "assert"
    time: str = ""                       # empty means no time restriction
    event: Variable | EventValue | None = None

    def terms(self) -> tuple[Any, ...]:
        return tuple(term for _, term in self.roles)


@dataclass(frozen=True)
class Clause:
    id: str
    event: Variable
    predicate: str
    predicate_span: Span
    roles: tuple[Role, ...]
    span: Span
    body_span: Span | None = None
    polarity: str = "+"
    modality: str = "assert"
    time: str = ""                       # past / nonpast / explicit time text
    conditions: tuple[Pattern, ...] = ()
    condition_spans: tuple[Span, ...] = ()
    exceptions: tuple[Pattern, ...] = ()
    exception_spans: tuple[Span, ...] = ()
    exception_of: str = ""
    rule: str = "frame"
    sovereign: str = "document"
    family: str = "document"
    unsupported: tuple[str, ...] = ()

    def pattern(self) -> Pattern:
        return Pattern(self.predicate, tuple((r.name, r.term) for r in self.roles),
                       self.polarity, self.modality, self.time)


@dataclass(frozen=True)
class Obligation:
    id: str
    span: Span
    kind: str
    node: str
    detail: str = ""


@dataclass(frozen=True)
class Unread:
    span: Span
    reason: str


@dataclass(frozen=True)
class Test:
    left: Any
    relation: str
    right: Any


@dataclass(frozen=True)
class Output:
    label: str
    term: Any
    obligation: str
    unit: str = ""
    span: Span | None = None


@dataclass(frozen=True)
class Operator:
    """Typed operator record. Each op has a closed arity and contract.

    Bind(pattern); Join(two relations); Filter(tests); ApplyCondition;
    Except; Sum/Difference/Compare(terms -> target); Project(outputs).
    A proof's operator must agree with the original plan, not just its name.
    """
    id: str
    op: str
    inputs: tuple[str, ...] = ()
    pattern: Pattern | None = None
    tests: tuple[Test, ...] = ()
    terms: tuple[Any, ...] = ()
    target: Variable | None = None
    relation: str = ""
    unit: str = ""
    absolute: bool = False
    choices: tuple[Any, ...] = ()
    outputs: tuple[Output, ...] = ()
    obligations: tuple[str, ...] = ()
    span: Span | None = None


@dataclass(frozen=True)
class Plan:
    nodes: tuple[Operator, ...]
    root: str

    def depth(self) -> int:
        seen: dict[str, int] = {}
        for node in self.nodes:
            if node.id in seen or any(i not in seen for i in node.inputs):
                raise ValueError("plan is not a topological DAG")
            seen[node.id] = 1 + max((seen[i] for i in node.inputs), default=0)
        return seen[self.root]


@dataclass(frozen=True)
class Request:
    text: str
    plans: tuple[Plan, ...]
    obligations: tuple[Obligation, ...]
    covered: tuple[Span, ...]
    unread: tuple[Unread, ...] = ()
    stages: tuple[Any, ...] = ()
    rules: tuple[str, ...] = ()


@dataclass(frozen=True)
class Budget:
    parse: int = 32
    depth: int = 8
    candidates: int = 256
    bindings: int = 64
    steps: int = 4096


@dataclass
class Meter:
    budget: Budget = field(default_factory=Budget)
    steps: int = 0
    peak_bindings: int = 0
    candidates: int = 0

    def spend(self, n: int = 1) -> None:
        self.steps += n
        if self.steps > self.budget.steps:
            raise Limit("steps")

    def states(self, n: int) -> None:
        self.peak_bindings = max(self.peak_bindings, n)
        if n > self.budget.bindings:
            raise Limit("bindings")

    def shape(self, plan, request=None):
        # Charge each node/dependency/term and the validation traversals.
        self.spend(sum(3 + len(n.inputs) + len(n.obligations) + len(n.terms) + len(n.choices)
                       + 2*len(n.tests) + len(n.outputs) + (len(n.pattern.roles)+1 if n.pattern else 0)
                       for n in plan.nodes))
        if request is not None:
            self.spend(len(request.plans) + 2*len(request.obligations) + len(request.covered))


class Limit(Exception):
    pass


@dataclass(frozen=True)
class ProofNode:
    id: str
    op: str
    plan_node: str = ""
    parents: tuple[str, ...] = ()
    clause: Clause | None = None
    bindings: tuple[tuple[str, Any], ...] = ()
    covers: tuple[str, ...] = ()
    answer: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True)
class Proof:
    nodes: tuple[ProofNode, ...]
    root: str
    sovereign: str


@dataclass(frozen=True)
class Row:
    bindings: tuple[tuple[str, Any], ...]
    proof: str
    covers: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()
    pending_conditions: tuple[str, ...] = ()
    pending_exceptions: tuple[str, ...] = ()


@dataclass
class View:
    sources: dict[str, str]
    clauses: tuple[Clause, ...]
    unread: tuple[Unread, ...] = ()
    ingest_ms: float = 0.0
    by_id: dict[str, Clause] = field(init=False, repr=False, default_factory=dict)
    by_predicate: dict[tuple[str, str], tuple[Clause, ...]] = field(init=False, repr=False, default_factory=dict)
    by_sovereign: dict[str, tuple[Clause, ...]] = field(init=False, repr=False, default_factory=dict)
    invalid: tuple[str, ...] = field(init=False, default=())

    def __post_init__(self) -> None:
        groups: dict[tuple[str, str], list[Clause]] = {}
        invalid = []
        for clause in self.clauses:
            if clause.id in self.by_id:
                invalid.append("duplicate clause ID: " + clause.id)
            self.by_id[clause.id] = clause
            names = [r.name for r in clause.roles]
            if len(names) != len(set(names)):
                invalid.append("duplicate role: " + clause.id)
            groups.setdefault((clause.sovereign, clause.predicate), []).append(clause)
        self.by_predicate = {k: tuple(v) for k, v in groups.items()}
        sovereigns: dict[str, list[Clause]] = {}
        for clause in self.clauses:
            sovereigns.setdefault(clause.sovereign, []).append(clause)
        self.by_sovereign = {k: tuple(v) for k, v in sovereigns.items()}
        self.invalid = tuple(invalid)


def typed(value: Any, sort: str) -> bool:
    if sort == "quantity":
        return (isinstance(value, Quantity) and isinstance(value.amount, Decimal) and value.amount.is_finite()
                and len(value.amount.as_tuple().digits) <= 128
                and abs(value.amount.as_tuple().exponent) <= 256 and isinstance(value.unit, str) and bool(value.unit))
    if sort == "entity":
        return isinstance(value, str) and bool(value)
    if sort == "value":
        return isinstance(value, (str, bool)) or typed(value, "quantity")
    if sort == "event":
        return (isinstance(value, EventValue) and all(isinstance(v,str) for v in
                (value.sovereign,value.family,value.identity,value.time)) and
                bool(value.sovereign and value.family and value.identity))
    return False


def data(value: Any) -> Any:
    """JSON representation; Decimal is never rounded through float."""
    if isinstance(value, Decimal):
        return str(value)
    if is_dataclass(value):
        return data(asdict(value))
    if isinstance(value, dict):
        return {str(k): data(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [data(v) for v in value]
    return value
