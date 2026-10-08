"""Immutable contracts for the finite Round5-C content path.

No generated value is placed in a knowledge store. Source offsets are Python
character offsets into the *original*, unnormalised string, half open.
An expression witness never licenses an actual-world occurrence. An explicitly
authorized fiction plan may instead bind a parsed expression event as an
authored story component, with its source span retained.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from typing import Any, Tuple


CLAUSE_TERMINATORS = "。\n；;"


def strip_clause_terminator(text: str) -> str:
    """Normalize only separators recognized by the source-span segmenter."""
    return text.strip().rstrip(CLAUSE_TERMINATORS).strip()


def digest(value: Any) -> str:
    if hasattr(value, "__dataclass_fields__"):
        value = asdict(value)
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), default=asdict).encode()).hexdigest()


class ContentError(ValueError):
    def __init__(self, verdict: str, reason: str, **details: Any):
        super().__init__(reason)
        self.verdict, self.reason, self.details = verdict, reason, details


@dataclass(frozen=True)
class Source:
    id: str
    text: str
    family: str = "brief"
    purpose: str = "instruction"  # instruction | evidence | expression
    independent: str = ""

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.text.encode()).hexdigest()


@dataclass(frozen=True)
class Span:
    source: str
    start: int
    end: int
    sha256: str

    @classmethod
    def of(cls, source: Source, start: int = 0, end: int = -1) -> "Span":
        return cls(source.id, start, len(source.text) if end < 0 else end, source.sha256)


@dataclass(frozen=True)
class Atom:
    kind: str = "event"  # event | state | quote
    predicate: str = ""
    agent: str = ""
    patient: str = ""
    recipient: str = ""
    negated: bool = False
    tense: str = "present"
    world: str = "fiction"
    fluent: str = ""
    value: str = ""
    quote: str = ""
    condition: Tuple["Atom", ...] = ()

    def key(self) -> tuple:
        return (self.kind, self.predicate, self.agent, self.patient, self.recipient,
                self.negated, self.tense, self.world, self.fluent, self.value,
                self.quote, tuple(a.key() for a in self.condition))

    def event_key(self) -> tuple:
        """Rule matching ignores realization tense, never polarity/world/roles."""
        return (self.kind, self.predicate, self.agent, self.patient, self.recipient,
                self.negated, self.world, self.fluent, self.value,
                tuple(a.event_key() for a in self.condition))

    def names(self) -> tuple:
        result = [n for n in (self.agent, self.patient, self.recipient) if n]
        if self.kind == "state" and self.fluent in ("owner", "location") and self.value:
            result.append(self.value)
        for condition in self.condition:
            result.extend(condition.names())
        return tuple(sorted(set(result)))


@dataclass(frozen=True)
class State:
    subject: str
    fluent: str  # open | owner | location; exclusive and persistent, locally
    value: str
    world: str = "fiction"
    positive: bool = True

    def key(self) -> tuple:
        return self.world, self.subject, self.fluent

    def as_atom(self, tense: str = "present") -> Atom:
        return Atom(kind="state", agent=self.subject, fluent=self.fluent,
                    value=self.value, world=self.world, negated=not self.positive,
                    tense=tense)


@dataclass(frozen=True)
class Rule:
    id: str
    action: Atom
    requires: Tuple[State, ...]
    effects: Tuple[State, ...]
    source: Span
    exceptions: Tuple[State, ...] = ()


@dataclass(frozen=True)
class Obligation:
    id: str
    kind: str
    span: Span
    atom: Atom | None = None
    state: State | None = None
    # Event origin tags include material_evidence, expression_material, and
    # expression_material_recast. The latter means exact surface-name reuse
    # across sources was authorized as a new fictional role, never a source-identity claim.
    value: str = ""
    number: int = 0
    relation: Tuple[str, str, str] = ()  # Before/Cause, left obligation, right


@dataclass(frozen=True)
class Ledger:
    brief: Source
    materials: Tuple[Source, ...]
    obligations: Tuple[Obligation, ...]
    rules: Tuple[Rule, ...] = ()
    unread: Tuple[Span, ...] = ()
    mode: str = "fiction"
    choice: Tuple[str, ...] = ()  # events/order only when explicitly permitted

    @property
    def hash(self) -> str:
        return digest(self)


@dataclass(frozen=True)
class Node:
    id: str
    atom: Atom
    obligations: Tuple[str, ...] = ()
    evidence: Tuple[Span, ...] = ()
    permission: str = ""  # fiction obligation or AUTHOR_CHOICE obligation
    rule: str = ""
    accessible_to: Tuple[str, ...] = ()
    phase: str = "event"


@dataclass(frozen=True)
class Transition:
    node: str
    rule: str
    before: Tuple[State, ...]
    after: Tuple[State, ...]


@dataclass(frozen=True)
class Plan:
    ledger_hash: str
    nodes: Tuple[Node, ...]
    order: Tuple[str, ...]
    relations: Tuple[Tuple[str, str, str], ...] = ()
    initial: Tuple[State, ...] = ()
    final: Tuple[State, ...] = ()
    transitions: Tuple[Transition, ...] = ()
    narrator: str = "omniscient"
    author_choices: Tuple[str, ...] = ()

    @property
    def hash(self) -> str:
        return digest(self)


@dataclass(frozen=True)
class ClauseSpan:
    node: str
    start: int
    end: int
    derivation: str
    expression_sources: Tuple[Span, ...] = ()


@dataclass(frozen=True)
class Realization:
    plan_hash: str
    text: str
    clauses: Tuple[ClauseSpan, ...]
    grammar: str = "verantyx.realize.conjugate + C state/quote/conditional shells v1"


@dataclass
class Budget:
    """Fixed per-ask operation/size bounds; failures retain counters.

    'steps' counts C rule applications, frame candidates, bindings, state
    tests, expansions, realizations and verifier comparisons, including their
    inner loops. The existing morphological/Frame routines have a separate
    bounded character input; their internal implementation is not a C step.
    This distinction must be recorded before a preregistered adoption run.
    """
    counts: dict = field(default_factory=dict)
    limits: dict = field(default_factory=lambda: {
        "brief_chars": 1200, "material_chars": 12000, "output_chars": 800,
        "parse_candidates": 32, "entities": 4, "worlds": 4, "events": 8,
        "nodes": 16, "candidates": 256, "plans": 256, "frontier": 64,
        "depth": 8, "surfaces": 32, "steps": 4096,
    })
    stopped_at: str = ""

    def tick(self, name: str = "steps", amount: int = 1) -> None:
        self.counts[name] = self.counts.get(name, 0) + amount
        if self.counts[name] > self.limits.get(name, 4096):
            self.stopped_at = name
            raise ContentError("UNKNOWN_CONTENT_BUDGET", "fixed content budget exceeded",
                               counter=name, actual=self.counts[name],
                               limit=self.limits.get(name, 4096))

    def size(self, name: str, amount: int) -> None:
        self.counts[name] = max(amount, self.counts.get(name, 0))
        if amount > self.limits[name]:
            self.stopped_at = name
            raise ContentError("UNKNOWN_CONTENT_BUDGET", "fixed content size exceeded",
                               counter=name, actual=amount, limit=self.limits[name])

    def as_dict(self) -> dict:
        return {"counts": dict(self.counts), "limits": dict(self.limits),
                "stopped_at": self.stopped_at,
                "morphology_accounting": "character bounded; existing routine internals excluded"}


def source_text(span: Span, sources: tuple) -> str:
    for source in sources:
        if source.id == span.source:
            if source.sha256 != span.sha256 or not 0 <= span.start <= span.end <= len(source.text):
                raise ContentError("CONTENT_CONSTRAINT_VIOLATION", "invalid source span/hash")
            return source.text[span.start:span.end]
    raise ContentError("CONTENT_CONSTRAINT_VIOLATION", "unavailable source identity")


def state_holds(state: tuple, wanted: State) -> bool | None:
    """Absence is unknown. An explicit different exclusive value is false."""
    own = [s for s in state if s.key() == wanted.key()]
    if wanted in own:
        return True
    if State(wanted.subject, wanted.fluent, wanted.value, wanted.world,
             not wanted.positive) in own:
        return False
    if wanted.positive and any(s.positive and s.value != wanted.value for s in own):
        return False
    return None
