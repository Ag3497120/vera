"""Which agent does which job: typed records, and a router that only reads records.

Three layers, pointing one way (docs/AGENT_ROUTING.md):

* a **producer** reads some human description and makes records.  The Markdown frame
  DSL (``verantyx/project_frame.py``) is one producer; a plain dictionary is another
  (used by the tests); a reader of free-form prose can be a third.  A producer only
  checks the *shape* of what it read.
* the **record layer** (this module, ``build_routing_table``) checks the *meaning*:
  vocabulary, duplicates, a default for every role, references, cycles.  Every producer
  goes through the same checks, so a rejection has one type whichever way the human
  wrote it.
* the **router** (``route``) takes a ``RoutingTable`` and a ``RoutingRequest`` and returns
  a typed ``RoutingDecision``.  It does not know the DSL.

This module imports neither ``project_frame`` nor ``conductor_run`` nor ``cli``.

What a human wrote about an agent ("fast", "good at review") is testimony: every record
carries a ``Basis`` that says where it came from (``declared_dsl`` with the line, or
``declared_text`` with the sentence or sentences it was read from).  A record states only
what the human said: a value the human did not say (a reason, a number of parallel runs, an
effort) is ``None``, never a made-up one.  Nothing measured is ever stored in
a record, and the router reads no measurement.  The ledger rows keep the two apart:
``ledger_fields`` (declared) and ``measured_fields`` (measured) share no key except the
job id and the ``values`` marker.

Ties are not broken by position.  Order of rows in a producer's input never decides; an
order *inside* a preference list is a human-declared priority and is used.  Where this
module sorts, it is only to print a stable listing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Mapping, Optional

from .agent_adapter import validate_effort, validate_model
from .llm_choice import ChoiceCandidate

ADAPTERS = ("codex", "claude", "fake")
ROLES = ("implement", "verify", "review", "generate", "read", "answer")
TASK_KINDS = ("small_fix", "feature", "large_refactor", "test_authoring", "review", "verification",
              "attack", "bulk_generation", "read_large_file", "closed_choice")
SIZES = ("small", "medium", "large")
BASIS_KINDS = ("declared_dsl", "declared_text")
LINEAGE_RELATIONS = ("same", "distinct")                 # what a human can say about two agents
LINEAGE_VERDICTS = ("same", "distinct", "undeclared")    # what the record layer can conclude about two agents
CONDITION_FIELDS = ("role", "kind", "size", "independent_of")
NO_INDEPENDENCE = "none"

# Design values (decided by the author of this module; nothing was measured to choose them).
# The size of a job is the larger of two bands.  A number at or below ``small_max`` is small, at or
# below ``medium_max`` medium, above that large.
SIZE_THRESHOLDS = {
    "allowlist_paths": {"small_max": 2, "medium_max": 5},   # 1-2 small, 3-5 medium, 6 or more large
    "criteria": {"small_max": 3, "medium_max": 7},          # 1-3 small, 4-7 medium, 8 or more large
}

RECORD_ERRORS = (
    "UNKNOWN_ADAPTER", "UNKNOWN_ROLE", "UNKNOWN_KIND", "UNKNOWN_SIZE", "BAD_VALUE",
    "DUPLICATE_AGENT_ID", "DUPLICATE_RULE_ID", "UNKNOWN_AGENT_REF", "UNKNOWN_RULE_REF",
    "MISSING_ROLE_CONDITION", "BAD_CONDITION", "RULE_AGENT_MISMATCH", "MISSING_ROLE_DEFAULT", "DUPLICATE_FALLBACK",
    "INDEPENDENCE_CYCLE", "PRECEDENCE_CYCLE", "DUPLICATE_PRECEDENCE", "PRECEDENCE_ON_DEFAULT",
    "EMPTY_TABLE", "LINEAGE_CONFLICT", "DUPLICATE_LINEAGE_RELATION",
)
# Codes only a producer of the DSL form uses (the shape of a row, not its meaning).
DSL_ERRORS = ("MALFORMED_ROW", "UNKNOWN_FIELD", "MISSING_FIELD", "DUPLICATE_FIELD", "MISSING_SECTION",
              "AGENT_SETTINGS_CONFLICT")
UNDECIDED_REASONS = ("ROLE_NOT_ROUTABLE", "NO_VIABLE_CANDIDATE", "TESTIMONY_UNAVAILABLE",
                     "TESTIMONY_ABSTAINED", "TESTIMONY_FAILED", "TESTIMONY_REFUSED", "TESTIMONY_OUT_OF_SET")
EXCLUSION_REASONS = ("ROLE_NOT_DECLARED", "KIND_NOT_DECLARED", "CONCURRENCY_FULL", "CONCURRENCY_UNDECLARED",
                     "SAME_LINEAGE", "PRIOR_ROLE_UNUSED", "LINEAGE_UNDECLARED")
KIND_FIT_VALUES = ("declared", "undeclared")
STAGES = ("rule", "precedence", "llm_testimony", "NONE")

# Ledger row keys.  ``values`` says which kind of value the row holds; ``job_id`` joins a decision
# to its later measurement.  The two key sets below do not intersect (checked at import).
JOIN_KEYS = ("job_id", "values")
DECLARED_KEYS = ("role", "task_kind", "size", "size_basis", "agent_id", "stage", "decided_by", "matched_rules",
                 "candidates", "excluded", "kind_fit", "role_fit", "precedence_used", "testimony", "independence",
                 "independence_basis", "undecided_reason", "agent_basis")
MEASURED_KEYS = ("outcome", "rounds", "elapsed_seconds")
assert not set(DECLARED_KEYS) & set(MEASURED_KEYS) and not set(JOIN_KEYS) & (set(DECLARED_KEYS) | set(MEASURED_KEYS))

_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")       # ids a producer gives to rules and precedence entries
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")     # ``note``: a short identifier, never prose


def _human_name(value: Any) -> bool:
    """An agent id or a lineage as a human says it: a non-empty string with no leading or trailing
    space and no control character.  ('Sonnet 5.5', 'ソネット' and 'Claude系' are all fine.)  The narrower
    token form a row of the DSL needs is the DSL producer's check, not a rule of the record."""
    return (isinstance(value, str) and bool(value) and value == value.strip()
            and not any(ord(ch) < 32 or ord(ch) == 127 for ch in value))


# ---------------------------------------------------------------------------------------------
# records
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Basis:
    """Where a declared record came from.  Always testimony, never a measurement.

    ``declared_dsl``: the line of the frame (and the row as written).  ``declared_text``: one or more
    sentences of the human's own text; a value that two sentences together state keeps both of them.
    """

    kind: str
    source: str
    line: Optional[int] = None
    witnesses: tuple = ()

    def __post_init__(self) -> None:
        if self.kind not in BASIS_KINDS:
            raise ValueError(f"basis kind must be one of {', '.join(BASIS_KINDS)}")
        if not isinstance(self.source, str) or not self.source:
            raise ValueError("a basis names its source")
        if isinstance(self.witnesses, (str, bytes)):
            raise TypeError("witnesses is a sequence of sentences, not one string")
        witnesses = tuple(self.witnesses)
        if any(not isinstance(item, str) for item in witnesses):
            raise ValueError("every witness is a sentence (a string)")
        object.__setattr__(self, "witnesses", witnesses)
        if self.kind == "declared_dsl":
            if type(self.line) is not int or self.line < 1:
                raise ValueError("a declared_dsl basis needs the line it was read from")
        elif not witnesses or any(not item.strip() for item in witnesses):
            raise ValueError("a declared_text basis needs at least one sentence it was read from "
                             "(witnesses), and none of them blank")

    @classmethod
    def dsl(cls, source: str, line: int, row: Optional[str] = None) -> "Basis":
        return cls("declared_dsl", source, line, (row,) if row else ())

    @classmethod
    def text(cls, source: str, witness: Any, line: Optional[int] = None) -> "Basis":
        """``witness``: one sentence, or a sequence of the sentences the record was read from."""
        if witness is None:
            raise ValueError("a declared_text basis needs the sentence it was read from")
        sentences = (witness,) if isinstance(witness, str) else tuple(witness)
        return cls("declared_text", source, line, sentences)

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "source": self.source, "line": self.line, "witnesses": list(self.witnesses)}


@dataclass(frozen=True)
class AgentRecord:
    """One agent as a human described it.  ``model``, ``effort``, ``concurrency``, ``roles``, ``kinds`` and
    ``lineage`` are ``None`` when the human did not say; the router and the conductor then treat them as
    unknown, not as a default and not as "everything": an agent with no ``kinds`` was named for its roles
    without a limit on the kind of job (the decision says so, ``kind_fit``), an agent with no ``roles`` was
    named for kinds of job without a limit on the role (``role_fit``), and an agent with no ``lineage`` is
    one whose independence of another agent can be judged only by a ``LineageRelation`` (else
    ``LINEAGE_UNDECLARED``).  A ``lineage`` is a label the producer decided: within one table the same
    label is the same lineage and two different labels are two lineages (docs/AGENT_ROUTING.md, chapter 0)."""

    id: str
    adapter: str
    roles: Optional[frozenset]
    basis: Basis
    kinds: Optional[frozenset] = None
    lineage: Optional[str] = None
    model: Optional[str] = None
    effort: Optional[str] = None
    concurrency: Optional[int] = None
    note: Optional[str] = None

    def __post_init__(self) -> None:
        for name in ("roles", "kinds"):
            value = getattr(self, name)
            if value is None:
                continue
            if isinstance(value, (str, bytes)):
                raise TypeError(f"{name} must be a collection of names, not one string")
            object.__setattr__(self, name, frozenset(value))


@dataclass(frozen=True)
class Condition:
    field: str
    value: str


@dataclass(frozen=True)
class RoutingRule:
    """``fallback`` marks the one rule per role the human declared as the last resort ("otherwise ...");
    it is a field of the record, not a name.  ``reason`` is ``None`` when the human gave none."""

    id: str
    conditions: tuple
    preference: tuple
    reason: Optional[str]
    basis: Basis
    fallback: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "conditions", tuple(self.conditions))
        object.__setattr__(self, "preference", tuple(self.preference))

    def _value(self, name: str) -> Optional[str]:
        for item in self.conditions:
            if item.field == name:
                return item.value
        return None

    def content(self) -> tuple:
        """What the rule says, without the name a producer gave it (conditions, preference, fallback)."""
        return (frozenset((item.field, item.value) for item in self.conditions), self.preference, self.fallback)

    @property
    def role(self) -> Optional[str]:
        return self._value("role")

    @property
    def kind(self) -> Optional[str]:
        return self._value("kind")

    @property
    def size(self) -> Optional[str]:
        return self._value("size")

    @property
    def independent_of(self) -> Optional[str]:
        return self._value("independent_of")

    @property
    def waives_independence(self) -> bool:
        return self.role == "verify" and self.independent_of == NO_INDEPENDENCE

    def independent_roles_for(self, request_role: str) -> tuple:
        """Roles whose agents' lineages this rule's candidates must differ from, for a request of ``request_role``.

        The role is the *request's*: a rule with no ``role=`` matches a request of any role, and a request
        for ``verify`` is independent of ``implement`` whichever rule matched.  Only a rule written
        ``role=verify & independent_of=none`` waives it.
        """
        if self.role is None:
            return ("implement",) if request_role == "verify" else ()
        explicit = self.independent_of
        roles: list[str] = []
        if self.role == "verify" and explicit != NO_INDEPENDENCE:
            roles.append("implement")
        if explicit is not None and explicit != NO_INDEPENDENCE and explicit not in roles:
            roles.append(explicit)
        return tuple(roles)

    @property
    def independent_roles(self) -> tuple:
        """The independence of the rule's *own* role (``()`` for a rule with no ``role=``).  The router does
        not use this: it uses ``independent_roles_for(request.role)``."""
        return self.independent_roles_for(self.role) if self.role is not None else ()

    def matches(self, request: "RoutingRequest") -> bool:
        return (self.role in (None, request.role) and self.kind in (None, request.kind)
                and self.size in (None, request.size))


@dataclass(frozen=True)
class RoutingPrecedence:
    id: str
    higher: str
    lower: str
    reason: Optional[str]
    basis: Basis


@dataclass(frozen=True)
class LineageRelation:
    """What a human said about two agents' lineage: "A and B are the same lineage" / "A and B are different
    lineages".  ``a`` and ``b`` are agent ids; the relation has no direction.  It is testimony (``basis``).
    A producer that cannot tell whether two names of a lineage are one lineage gives no label and passes the
    relations it was told instead."""

    a: str
    b: str
    relation: str
    basis: Basis

    def pair(self) -> frozenset:
        return frozenset((self.a, self.b))

    def as_dict(self) -> dict[str, Any]:
        first, second = _display((self.a, self.b)) if self.a != self.b else (self.a, self.b)   # display order only
        return {"a": first, "b": second, "relation": self.relation,
                "basis": self.basis.as_dict() if isinstance(self.basis, Basis) else None}


@dataclass(frozen=True)
class RoutingTable:
    """Built only by ``build_routing_table``: every check of meaning has passed."""

    agents: tuple
    rules: tuple
    precedence: tuple = ()
    lineage_relations: tuple = ()

    def agent(self, agent_id: str) -> Optional[AgentRecord]:
        for item in self.agents:
            if item.id == agent_id:
                return item
        return None


class RoutingRecordError(ValueError):
    """A record that cannot be accepted.  ``code`` is one of RECORD_ERRORS; ``basis`` says which record."""

    def __init__(self, code: str, message: str, basis: Optional[Basis] = None):
        if code not in RECORD_ERRORS:
            raise ValueError(f"unknown record error code {code!r}")
        self.code = code
        self.message = message
        self.basis = basis
        super().__init__(f"{code}: {message}")


def _bad(code: str, message: str, basis: Optional[Basis] = None) -> RoutingRecordError:
    return RoutingRecordError(code, message, basis)


# ---------------------------------------------------------------------------------------------
# the record layer: every check of meaning
# ---------------------------------------------------------------------------------------------
def _check_agent(item: AgentRecord) -> None:
    where = item.basis
    if not _human_name(item.id):
        raise _bad("BAD_VALUE", f"agent id {item.id!r} must be a non-empty name with no surrounding space or control "
                   "character", where)
    if item.adapter not in ADAPTERS:
        raise _bad("UNKNOWN_ADAPTER", f"agent {item.id}: adapter {item.adapter!r} is not one of {', '.join(ADAPTERS)}", where)
    for label, value, check in (("model", item.model, validate_model), ("effort", item.effort, validate_effort)):
        if value is None:          # the human did not say; it stays unknown (the conductor refuses to guess)
            continue
        try:
            check(value)
        except ValueError as exc:
            raise _bad("BAD_VALUE", f"agent {item.id}: {label}: {exc}", where) from exc
    if item.roles is not None:      # said: checked.  Not said (None): the human set no limit on the role
        if not item.roles:
            raise _bad("BAD_VALUE", f"agent {item.id}: roles, when declared, is not empty", where)
        for role in item.roles:
            if role not in ROLES:
                raise _bad("UNKNOWN_ROLE", f"agent {item.id}: role {role!r} is not one of {', '.join(ROLES)}", where)
    if item.kinds is not None:      # said: checked.  Not said (None): the human set no limit on the kind of job
        if not item.kinds:
            raise _bad("BAD_VALUE", f"agent {item.id}: kinds, when declared, is not empty", where)
        for kind in item.kinds:
            if kind not in TASK_KINDS:
                raise _bad("UNKNOWN_KIND", f"agent {item.id}: kind {kind!r} is not one of {', '.join(TASK_KINDS)}", where)
    if item.lineage is not None and not _human_name(item.lineage):
        raise _bad("BAD_VALUE", f"agent {item.id}: lineage {item.lineage!r}, when given, is a non-empty name with no "
                   "surrounding space or control character", where)
    if item.concurrency is not None and (type(item.concurrency) is not int or item.concurrency < 1):
        raise _bad("BAD_VALUE", f"agent {item.id}: concurrency must be a whole number of at least 1", where)
    if item.note is not None and (not isinstance(item.note, str) or not _NAME.fullmatch(item.note)):
        raise _bad("BAD_VALUE", f"agent {item.id}: note must be a short identifier, not prose", where)
    if not isinstance(item.basis, Basis):
        raise _bad("BAD_VALUE", f"agent {item.id}: a record needs a basis", None)


def _check_rule(rule: RoutingRule, agents: Mapping[str, AgentRecord]) -> None:
    where = rule.basis
    if not isinstance(rule.id, str) or not _ID.fullmatch(rule.id):
        raise _bad("BAD_VALUE", f"rule id {rule.id!r} must be letters, digits, '_' or '-', starting with a letter", where)
    seen: set[str] = set()
    for item in rule.conditions:
        if not isinstance(item, Condition) or item.field not in CONDITION_FIELDS:
            raise _bad("BAD_CONDITION", f"rule {rule.id}: a condition is one of {', '.join(CONDITION_FIELDS)}", where)
        if item.field in seen:
            raise _bad("BAD_CONDITION", f"rule {rule.id}: condition {item.field} is written twice", where)
        seen.add(item.field)
    if "role" not in seen and rule.fallback is True:    # a rule with no role= is legal; a fallback names its role
        raise _bad("MISSING_ROLE_CONDITION", f"rule {rule.id}: a fallback rule needs exactly one role=<role> "
                   "condition", where)
    for item in rule.conditions:
        if item.field == "role" and item.value not in ROLES:
            raise _bad("UNKNOWN_ROLE", f"rule {rule.id}: role {item.value!r} is not one of {', '.join(ROLES)}", where)
        if item.field == "kind" and item.value not in TASK_KINDS:
            raise _bad("UNKNOWN_KIND", f"rule {rule.id}: kind {item.value!r} is not one of {', '.join(TASK_KINDS)}", where)
        if item.field == "size" and item.value not in SIZES:
            raise _bad("UNKNOWN_SIZE", f"rule {rule.id}: size {item.value!r} is not one of {', '.join(SIZES)}", where)
        if item.field == "independent_of" and item.value != NO_INDEPENDENCE and item.value not in ROLES:
            raise _bad("UNKNOWN_ROLE", f"rule {rule.id}: independent_of {item.value!r} is not a role or "
                       f"'{NO_INDEPENDENCE}'", where)
    if rule.role is None and rule.independent_of is not None:
        raise _bad("BAD_CONDITION", f"rule {rule.id}: a rule with no role= matches a request of any role, so "
                   "independent_of would make it depend on itself; write role=<role> to say whose independence", where)
    if rule.independent_of == NO_INDEPENDENCE and rule.role != "verify":
        raise _bad("BAD_CONDITION", f"rule {rule.id}: independent_of={NO_INDEPENDENCE} is only for role=verify", where)
    if type(rule.fallback) is not bool:
        raise _bad("BAD_VALUE", f"rule {rule.id}: fallback is true or false", where)
    if rule.fallback and (rule.kind is not None or rule.size is not None or
                          rule.independent_of not in (None, NO_INDEPENDENCE)):
        raise _bad("BAD_CONDITION", f"rule {rule.id}: a fallback rule has role=<role> only "
                   f"(and independent_of={NO_INDEPENDENCE} for verify)", where)
    if not rule.preference:
        raise _bad("BAD_VALUE", f"rule {rule.id}: the preference list is empty", where)
    if len(set(rule.preference)) != len(rule.preference):
        raise _bad("BAD_VALUE", f"rule {rule.id}: an agent is listed twice in the preference list", where)
    if rule.reason is not None and (not isinstance(rule.reason, str) or not rule.reason.strip()):
        raise _bad("BAD_VALUE", f"rule {rule.id}: a reason, when given, is not blank", where)
    for agent_id in rule.preference:
        agent = agents.get(agent_id)
        if agent is None:
            raise _bad("UNKNOWN_AGENT_REF", f"rule {rule.id}: agent {agent_id!r} is not in the agent table", where)
        if rule.role is not None and agent.roles is not None and rule.role not in agent.roles:
            raise _bad("RULE_AGENT_MISMATCH", f"rule {rule.id}: agent {agent_id} does not declare role {rule.role}", where)
        if rule.kind is not None and agent.kinds is not None and rule.kind not in agent.kinds:
            raise _bad("RULE_AGENT_MISMATCH", f"rule {rule.id}: agent {agent_id} does not declare kind {rule.kind}", where)


def _find_cycle(edges: Mapping[str, Iterable[str]]) -> Optional[str]:
    """A node on a cycle of a directed graph (a self-loop is a cycle), or None."""
    state: dict[str, int] = {}

    def visit(node: str) -> Optional[str]:
        state[node] = 1
        for child in edges.get(node, ()):
            if state.get(child) == 1:
                return child
            if child not in state:
                found = visit(child)
                if found is not None:
                    return found
        state[node] = 2
        return None

    for start in edges:
        if start not in state:
            found = visit(start)
            if found is not None:
                return found
    return None


class _Lineages:
    """The classes of agents that are one lineage, from the labels and the ``same`` relations.

    A class is a connected component of "has the same label" and "a ``same`` relation joins them", so it
    does not depend on the order of the input.  ``label`` is the one label a class carries (or None);
    ``conflicts`` lists, as text, what cannot hold together.
    """

    def __init__(self, agents: Iterable[AgentRecord], relations: Iterable[LineageRelation]):
        agents, relations = tuple(agents), tuple(relations)
        parent: dict[str, str] = {item.id: item.id for item in agents}

        def find(node: str) -> str:
            while parent[node] != node:
                parent[node] = parent[parent[node]]
                node = parent[node]
            return node

        def join(first: str, second: str) -> None:
            parent[find(first)] = find(second)

        first_with: dict[str, str] = {}
        for item in agents:
            if item.lineage is not None:
                join(item.id, first_with.setdefault(item.lineage, item.id))
        self.same = tuple(rel for rel in relations if rel.relation == "same")
        self.distinct = tuple(rel for rel in relations if rel.relation == "distinct")
        for rel in self.same:
            join(rel.a, rel.b)
        members: dict[str, set[str]] = {}
        for item in agents:
            members.setdefault(find(item.id), set()).add(item.id)
        self.class_of: dict[str, frozenset] = {}
        for group in members.values():
            frozen = frozenset(group)
            for name in group:
                self.class_of[name] = frozen
        by_id = {item.id: item for item in agents}
        self.labels: dict[frozenset, tuple] = {
            group: tuple(_display({by_id[name].lineage for name in group if by_id[name].lineage is not None}))
            for group in set(self.class_of.values())}
        self.conflicts: list[tuple[str, Optional[Basis]]] = []      # (what is wrong, the record to point at)
        for group, labels in self.labels.items():
            if len(labels) > 1:
                names = _display(group)
                self.conflicts.append((f"agents {', '.join(names)} are one lineage (same label or a 'same' relation) "
                                       f"but carry the different labels {', '.join(labels)}", by_id[names[0]].basis))
        for rel in self.distinct:
            if self.class_of.get(rel.a) is not None and self.class_of.get(rel.a) == self.class_of.get(rel.b):
                self.conflicts.append((f"'distinct' between {rel.a} and {rel.b}, who are one lineage (same label "
                                       "or joined by 'same' relations)", rel.basis))

    def label(self, group: frozenset) -> Optional[str]:
        labels = self.labels.get(group, ())
        return labels[0] if len(labels) == 1 else None


def _check_lineage_relations(by_id: Mapping[str, AgentRecord], agents: tuple,
                             relations: tuple) -> None:
    for rel in relations:
        if not isinstance(rel, LineageRelation):
            raise TypeError("lineage_relations must be LineageRelation objects")
        where = rel.basis if isinstance(rel.basis, Basis) else None
        if not isinstance(rel.basis, Basis):
            raise _bad("BAD_VALUE", f"lineage relation {rel.a!r}/{rel.b!r}: a record needs a basis", None)
        if rel.relation not in LINEAGE_RELATIONS:
            raise _bad("BAD_VALUE", f"lineage relation {rel.a!r}/{rel.b!r}: relation {rel.relation!r} is not one of "
                       f"{', '.join(LINEAGE_RELATIONS)}", where)
        if not _human_name(rel.a) or not _human_name(rel.b):
            raise _bad("BAD_VALUE", f"lineage relation {rel.a!r}/{rel.b!r}: both ends are agent ids", where)
        if rel.a == rel.b:
            raise _bad("BAD_VALUE", f"lineage relation: {rel.a!r} is related to itself", where)
        for name in (rel.a, rel.b):
            if name not in by_id:
                raise _bad("UNKNOWN_AGENT_REF", f"lineage relation {rel.a}/{rel.b}: agent {name!r} is not in the "
                           "agent table", where)
    kinds_of_pair: dict[frozenset, set[str]] = {}
    for rel in relations:
        kinds_of_pair.setdefault(rel.pair(), set()).add(rel.relation)
    for rel in relations:
        if len(kinds_of_pair[rel.pair()]) > 1:
            raise _bad("LINEAGE_CONFLICT", f"agents {rel.a} and {rel.b} are said to be both the same lineage and "
                       "different lineages", rel.basis)
    seen: set[tuple[frozenset, str]] = set()
    for rel in relations:
        key = (rel.pair(), rel.relation)
        if key in seen:
            raise _bad("DUPLICATE_LINEAGE_RELATION", f"agents {rel.a} and {rel.b}: the relation {rel.relation} is "
                       "declared twice", rel.basis)
        seen.add(key)
    closure = _Lineages(agents, relations)
    if closure.conflicts:
        messages = _display(message for message, _basis in closure.conflicts)   # all of them, in a stable listing
        only = closure.conflicts[0][1] if len(closure.conflicts) == 1 else None
        raise _bad("LINEAGE_CONFLICT", "; ".join(messages), only)


def build_routing_table(agents: Iterable[AgentRecord], rules: Iterable[RoutingRule],
                        precedence: Iterable[RoutingPrecedence] = (),
                        lineage_relations: Iterable[LineageRelation] = ()) -> RoutingTable:
    """The one place the meaning of agent / rule / precedence / lineage-relation records is checked.

    Raises ``RoutingRecordError`` whose ``code`` says what is wrong.  A table that comes out has
    a default row for every role it uses, no unknown references, no cycles, and lineage labels and
    relations that do not contradict each other.
    """
    agents, rules, precedence = tuple(agents), tuple(rules), tuple(precedence)
    lineage_relations = tuple(lineage_relations)
    if not agents or not rules:
        raise _bad("EMPTY_TABLE", "both the agent table and the routing rules need at least one entry")
    by_id: dict[str, AgentRecord] = {}
    for item in agents:
        if not isinstance(item, AgentRecord):
            raise TypeError("agents must be AgentRecord objects")
        _check_agent(item)
        if item.id in by_id:
            raise _bad("DUPLICATE_AGENT_ID", f"agent id {item.id!r} is declared twice", item.basis)
        by_id[item.id] = item
    seen_ids: set[str] = set()
    fallback_roles: set[str] = set()
    for rule in rules:
        if not isinstance(rule, RoutingRule):
            raise TypeError("rules must be RoutingRule objects")
        _check_rule(rule, by_id)
        if rule.fallback:
            if rule.role in fallback_roles:
                raise _bad("DUPLICATE_FALLBACK", f"role {rule.role} has two fallback rules", rule.basis)
            fallback_roles.add(rule.role)
        else:
            if rule.id in seen_ids:
                raise _bad("DUPLICATE_RULE_ID", f"rule id {rule.id!r} is declared twice", rule.basis)
            seen_ids.add(rule.id)
    for rule in rules:     # a fallback may not take the name of a rule: a precedence entry names rules
        if rule.fallback and rule.id in seen_ids:
            raise _bad("DUPLICATE_RULE_ID", f"the fallback rule {rule.id!r} has the name of another rule", rule.basis)
    needed: dict[str, Basis] = {}
    for item in agents:
        for role in (item.roles or ()):
            needed.setdefault(role, item.basis)
    for rule in rules:
        if rule.role is not None:
            needed.setdefault(rule.role, rule.basis)
    for role in sorted(needed):  # sorted only so that the first message is the same for every input order
        if role not in fallback_roles:
            raise _bad("MISSING_ROLE_DEFAULT", f"role {role} is used but has no fallback rule (the human's "
                       f"'otherwise' for role {role})", needed[role])
    edges: dict[str, set[str]] = {}
    for rule in rules:
        if rule.role is None:     # it can match a request for verify, which is independent of implement
            edges.setdefault("verify", set()).add("implement")
        else:
            for other in rule.independent_roles_for(rule.role):
                edges.setdefault(rule.role, set()).add(other)
    cycle = _find_cycle(edges)
    if cycle is not None:
        raise _bad("INDEPENDENCE_CYCLE", f"independent_of makes role {cycle} depend on itself "
                   "(a verify rule is independent of implement unless it says independent_of=none)")
    rule_ids = set(seen_ids)
    fallback_ids = {rule.id for rule in rules if rule.fallback}
    ids_seen: set[str] = set()
    pairs_seen: set[tuple[str, str]] = set()
    graph: dict[str, set[str]] = {}
    for item in precedence:
        if not isinstance(item, RoutingPrecedence):
            raise TypeError("precedence must be RoutingPrecedence objects")
        if not isinstance(item.id, str) or not _ID.fullmatch(item.id):
            raise _bad("BAD_VALUE", f"precedence id {item.id!r} must be letters, digits, '_' or '-'", item.basis)
        if item.reason is not None and (not isinstance(item.reason, str) or not item.reason.strip()):
            raise _bad("BAD_VALUE", f"precedence {item.id}: a reason, when given, is not blank", item.basis)
        if item.id in ids_seen or (item.higher, item.lower) in pairs_seen:
            raise _bad("DUPLICATE_PRECEDENCE", f"precedence {item.id}: declared twice", item.basis)
        ids_seen.add(item.id)
        pairs_seen.add((item.higher, item.lower))
        for name in (item.higher, item.lower):
            if name in fallback_ids:
                raise _bad("PRECEDENCE_ON_DEFAULT", f"precedence {item.id}: {name!r} is a fallback rule, "
                           "which takes no precedence", item.basis)
            if name not in rule_ids:
                raise _bad("UNKNOWN_RULE_REF", f"precedence {item.id}: no rule {name!r}", item.basis)
        if item.higher == item.lower:
            raise _bad("PRECEDENCE_CYCLE", f"precedence {item.id}: a rule cannot outrank itself", item.basis)
        graph.setdefault(item.higher, set()).add(item.lower)
    cycle = _find_cycle(graph)
    if cycle is not None:
        raise _bad("PRECEDENCE_CYCLE", f"routing precedence has a cycle through rule {cycle}")
    _check_lineage_relations(by_id, agents, lineage_relations)
    return RoutingTable(agents, rules, precedence, lineage_relations)


# ---------------------------------------------------------------------------------------------
# size
# ---------------------------------------------------------------------------------------------
def _band(count: int, name: str) -> str:
    limits = SIZE_THRESHOLDS[name]
    if count <= limits["small_max"]:
        return "small"
    return "medium" if count <= limits["medium_max"] else "large"


def size_of(allowlist_count: int, criteria_count: int) -> tuple[str, dict[str, Any]]:
    """The size of a job: the larger of the band of its write paths and the band of its criteria.

    The thresholds are design values (SIZE_THRESHOLDS), not measurements.  The second value says how
    the size was reached so it can be written beside the decision.
    """
    for label, value in (("allowlist_count", allowlist_count), ("criteria_count", criteria_count)):
        if type(value) is not int or value < 0:
            raise ValueError(f"{label} must be a whole number of at least 0")
    first, second = _band(allowlist_count, "allowlist_paths"), _band(criteria_count, "criteria")
    size = SIZES[max(SIZES.index(first), SIZES.index(second))]
    return size, {"allowlist_paths": allowlist_count, "allowlist_band": first,
                  "criteria": criteria_count, "criteria_band": second,
                  "rule": "the larger band", "thresholds": "design values, not measured"}


# ---------------------------------------------------------------------------------------------
# lineage of two agents
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class LineageVerdict:
    """What the records say about whether two agents are one lineage.

    ``verdict``: ``same`` (one class: same label, or joined by ``same`` relations), ``distinct`` (the two
    classes carry different labels, or a ``distinct`` relation lies between them; both grounds are listed when
    both hold) or ``undeclared`` (neither).  ``labels``: (the first agent's label, the second's), or None when
    either has none.  ``relations``: every ``distinct`` relation between the two classes; ``joined_by``: every
    ``same`` relation inside the two classes.  Their listing order is for display only.
    """

    verdict: str
    labels: Optional[tuple] = None
    relations: tuple = ()
    joined_by: tuple = ()

    def __post_init__(self) -> None:
        if self.verdict not in LINEAGE_VERDICTS:
            raise ValueError(f"verdict must be one of {', '.join(LINEAGE_VERDICTS)}")

    def as_dict(self) -> dict[str, Any]:
        return {"verdict": self.verdict, "labels": list(self.labels) if self.labels is not None else None,
                "relations": [item.as_dict() for item in self.relations],
                "joined_by": [item.as_dict() for item in self.joined_by]}


def _by_listing(items: Iterable[LineageRelation]) -> tuple:
    return tuple(sorted(items, key=lambda rel: (tuple(_display(rel.pair())), rel.relation)))   # display only


def _verdict(lin: "_Lineages", first: str, second: str) -> LineageVerdict:
    group_a, group_b = lin.class_of[first], lin.class_of[second]
    label_a, label_b = lin.label(group_a), lin.label(group_b)
    labels = (label_a, label_b) if label_a is not None and label_b is not None else None
    if group_a == group_b:
        inside = _by_listing(rel for rel in lin.same if rel.a in group_a)
        return LineageVerdict("same", labels, (), inside)
    between = _by_listing(rel for rel in lin.distinct
                          if (rel.a in group_a and rel.b in group_b) or (rel.a in group_b and rel.b in group_a))
    joined = _by_listing(rel for rel in lin.same if rel.a in group_a or rel.a in group_b)
    if (labels is not None and label_a != label_b) or between:
        return LineageVerdict("distinct", labels, between, joined)
    return LineageVerdict("undeclared", labels, (), joined)


def lineage_relation(table: RoutingTable, a: str, b: str) -> LineageVerdict:
    """Whether agents ``a`` and ``b`` are one lineage, from the table's labels and relations.

    ``a == b`` is the same lineage.  An agent that is not in the table is a caller's mistake (``ValueError``).
    """
    if not isinstance(table, RoutingTable):
        raise TypeError("lineage_relation takes a RoutingTable")
    lin = _Lineages(table.agents, table.lineage_relations)
    for name in (a, b):
        if name not in lin.class_of:
            raise ValueError(f"agent {name!r} is not in the routing table")
    return _verdict(lin, a, b)


# ---------------------------------------------------------------------------------------------
# the router
# ---------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class RoutingRequest:
    job_id: str
    role: str
    kind: str
    size: str
    used_lineages: Mapping = field(default_factory=dict)
    in_use: Mapping = field(default_factory=dict)
    size_basis: Mapping = field(default_factory=dict)
    used_agents: Mapping = field(default_factory=dict)
    # ``used_lineages``: role -> the lineages of the agents already used for that role in this job.  A role
    # with no entry (or an empty one) has not been used yet.  An element ``None`` means "an agent was used
    # for that role but its lineage is not known": that is not the same as not used, and not the same as
    # a lineage that differs.
    # ``used_agents``: role -> the ids of the agents already used for that role.  The router judges the
    # candidate's independence of those agents from the table's labels and relations (``lineage_relation``).
    # A role is given in one of the two, not both: the router does not choose which to believe.

    def __post_init__(self) -> None:
        if not isinstance(self.job_id, str) or not self.job_id:
            raise ValueError("a request needs a job id")
        if self.role not in ROLES:
            raise ValueError(f"role must be one of {', '.join(ROLES)}")
        if self.kind not in TASK_KINDS:
            raise ValueError(f"kind must be one of {', '.join(TASK_KINDS)}")
        if self.size not in SIZES:
            raise ValueError(f"size must be one of {', '.join(SIZES)}")
        used = {str(role): tuple(lineages) for role, lineages in dict(self.used_lineages).items()}
        for role, lineages in used.items():
            if any(item is not None and not _human_name(item) for item in lineages):
                raise ValueError(f"used_lineages[{role!r}]: a lineage is a name, or None when it is not known")
        object.__setattr__(self, "used_lineages", used)
        agents_used = {str(role): tuple(ids) for role, ids in dict(self.used_agents).items()}
        for role, ids in agents_used.items():
            if any(not _human_name(item) for item in ids):
                raise ValueError(f"used_agents[{role!r}]: an agent is named by its id")
        both = _display(set(agents_used) & set(used))
        if both:
            raise ValueError(f"role {', '.join(both)} is given in both used_agents and used_lineages; give it in one")
        object.__setattr__(self, "used_agents", agents_used)
        object.__setattr__(self, "in_use", dict(self.in_use))
        object.__setattr__(self, "size_basis", dict(self.size_basis))


@dataclass(frozen=True)
class Exclusion:
    agent_id: str
    rule_id: str
    reason: str
    detail: str = ""
    rule_content: Optional[tuple] = field(default=None, compare=False, repr=False)   # for ``essence`` only

    def as_dict(self) -> dict[str, str]:
        return {"agent_id": self.agent_id, "rule_id": self.rule_id, "reason": self.reason, "detail": self.detail}


@dataclass(frozen=True)
class RoutingDecision:
    job_id: str
    role: str
    kind: str
    size: str
    agent_id: Optional[str]
    stage: str
    decided_by: str
    matched_rules: tuple = ()
    candidates: tuple = ()
    excluded: tuple = ()
    kind_fit: Mapping = field(default_factory=dict)
    precedence_used: tuple = ()
    testimony: Optional[Mapping] = None
    independence: Mapping = field(default_factory=dict)
    independence_basis: Mapping = field(default_factory=dict)
    role_fit: Mapping = field(default_factory=dict)
    undecided_reason: Optional[str] = None
    agent_basis: Optional[Basis] = None
    size_basis: Mapping = field(default_factory=dict)
    matched_contents: tuple = field(default=(), compare=False, repr=False)   # for ``essence`` only

    def __post_init__(self) -> None:
        if self.stage not in STAGES:
            raise ValueError(f"stage must be one of {', '.join(STAGES)}")
        if (self.agent_id is None) != (self.stage == "NONE"):
            raise ValueError("a decision names an agent exactly when its stage is not NONE")
        if self.undecided_reason is not None and self.undecided_reason not in UNDECIDED_REASONS:
            raise ValueError("unknown undecided reason")

    @property
    def decided(self) -> bool:
        return self.agent_id is not None

    def essence(self) -> tuple:
        """What two producers of the same description must agree on.

        Rules are compared by what they say (``RoutingRule.content``), not by the name a producer gave them:
        a reader of prose invents its own rule names.  Agent ids are the human's own words for the agents
        and are compared as they are.  It leaves out the basis (where the words came from), reasons, time,
        testimony ids and the printing order.
        """
        return (self.role, self.kind, self.size, self.agent_id, self.stage, frozenset(self.matched_contents),
                frozenset((e.agent_id, e.rule_content, e.reason) for e in self.excluded))

    def ledger_fields(self) -> dict[str, Any]:
        """One ledger row's worth of declared values (never a measured one).

        The job's kind is written ``task_kind``: ``kind`` is the name of the ledger row's own type.
        """
        return {
            "values": "declared", "job_id": self.job_id, "role": self.role, "task_kind": self.kind, "size": self.size,
            "size_basis": dict(self.size_basis), "agent_id": self.agent_id, "stage": self.stage,
            "decided_by": self.decided_by, "matched_rules": list(self.matched_rules),
            "candidates": list(self.candidates), "excluded": [e.as_dict() for e in self.excluded],
            "kind_fit": dict(self.kind_fit), "role_fit": dict(self.role_fit),
            "precedence_used": list(self.precedence_used),
            "testimony": dict(self.testimony) if self.testimony is not None else None,
            "independence": dict(self.independence),
            "independence_basis": {role: list(items) for role, items in self.independence_basis.items()},
            "undecided_reason": self.undecided_reason,
            "agent_basis": self.agent_basis.as_dict() if self.agent_basis is not None else None}


def measured_fields(job_id: str, outcome: str, rounds: int, elapsed_seconds: float) -> dict[str, Any]:
    """One ledger row's worth of measured values.  Stored; the router never reads them."""
    if not isinstance(job_id, str) or not job_id or not isinstance(outcome, str) or not outcome:
        raise ValueError("a measurement names its job and its outcome")
    if type(rounds) is not int or rounds < 0:
        raise ValueError("rounds must be a whole number of at least 0")
    if isinstance(elapsed_seconds, bool) or not isinstance(elapsed_seconds, (int, float)) or elapsed_seconds < 0:
        raise ValueError("elapsed_seconds must be a number of at least 0")
    return {"values": "measured", "job_id": job_id, "outcome": outcome, "rounds": rounds,
            "elapsed_seconds": float(elapsed_seconds)}


def _display(items: Iterable[str]) -> tuple:
    return tuple(sorted(set(items)))  # a stable listing for people; never used to choose


@dataclass
class _Evaluation:
    rule: RoutingRule
    head: Optional[str]
    exclusions: list
    evidence: dict = field(default_factory=dict)    # role -> why the head counts as independent of it


def _evaluate(rule: RoutingRule, request: RoutingRequest, agents: Mapping[str, AgentRecord],
              lineages: "_Lineages") -> _Evaluation:
    """Walk one rule's preference list from the front; the first agent nothing excludes is its head."""
    found: list[Exclusion] = []
    for agent_id in rule.preference:
        agent = agents.get(agent_id)
        if agent is None:
            found.append(Exclusion(agent_id, rule.id, "ROLE_NOT_DECLARED", "no such agent in the table",
                                   rule.content()))
            continue
        problems: list[Exclusion] = []
        if agent.roles is not None and request.role not in agent.roles:
            problems.append(Exclusion(agent_id, rule.id, "ROLE_NOT_DECLARED", f"does not declare role {request.role}",
                                      rule.content()))
        if agent.kinds is not None and request.kind not in agent.kinds:
            problems.append(Exclusion(agent_id, rule.id, "KIND_NOT_DECLARED", f"does not declare kind {request.kind}",
                                      rule.content()))
        busy = int(request.in_use.get(agent_id, 0))
        if agent.concurrency is None:
            # The human gave no limit.  Nothing running: the first run needs no limit.  Something running:
            # whether there is room is unknown, and the router does not guess.
            if busy > 0:
                problems.append(Exclusion(agent_id, rule.id, "CONCURRENCY_UNDECLARED",
                                          f"in_use={busy} and the agent declares no concurrency", rule.content()))
        elif busy >= agent.concurrency:
            problems.append(Exclusion(agent_id, rule.id, "CONCURRENCY_FULL",
                                      f"in_use={busy} concurrency={agent.concurrency}", rule.content()))
        evidence: dict[str, list] = {}
        for other in rule.independent_roles_for(request.role):
            before = len(problems)
            used_agents = request.used_agents.get(other, ())
            used = request.used_lineages.get(other, ())
            if used_agents:
                verdicts = [(name, _verdict(lineages, agent_id, name)) for name in used_agents]
                same = [(name, item) for name, item in verdicts if item.verdict == "same"]
                unknown = [name for name, item in verdicts if item.verdict == "undeclared"]
                if same:     # every agent that is one lineage with the candidate is named; none is picked
                    parts = []
                    for name, item in same:
                        ground = []
                        if agent.lineage is not None and agent.lineage == agents[name].lineage:
                            ground.append(f"the same label {agent.lineage}")
                        if item.joined_by:
                            ground.append("'same' relation " + "; ".join(f"{rel.a}/{rel.b}" for rel in item.joined_by))
                        if name == agent_id:
                            ground.append("it is the same agent")
                        parts.append(f"{name} ({'; '.join(ground) or 'one lineage'})")
                    problems.append(Exclusion(agent_id, rule.id, "SAME_LINEAGE",
                                              f"the same lineage as {', '.join(parts)}, already used for role {other}",
                                              rule.content()))
                elif unknown:
                    problems.append(Exclusion(agent_id, rule.id, "LINEAGE_UNDECLARED",
                                              f"no label or relation says whether it differs from {', '.join(unknown)}, "
                                              f"already used for role {other}, so independence cannot be judged",
                                              rule.content()))
                else:
                    evidence[other] = [{"used_agent": name, **item.as_dict()} for name, item in verdicts]
            elif not used:
                problems.append(Exclusion(agent_id, rule.id, "PRIOR_ROLE_UNUSED",
                                          f"no agent has been used for role {other} in this job yet", rule.content()))
            elif agent.lineage is not None and agent.lineage in used:
                problems.append(Exclusion(agent_id, rule.id, "SAME_LINEAGE",
                                          f"lineage {agent.lineage} was already used for role {other}", rule.content()))
            elif agent.lineage is None:
                problems.append(Exclusion(agent_id, rule.id, "LINEAGE_UNDECLARED",
                                          f"the agent declares no lineage, so its independence of role {other} "
                                          "cannot be judged", rule.content()))
            elif None in used:
                problems.append(Exclusion(agent_id, rule.id, "LINEAGE_UNDECLARED",
                                          f"an agent was used for role {other} whose lineage is not declared, so "
                                          "independence of it cannot be judged", rule.content()))
            if len(problems) == before and other not in evidence:
                evidence[other] = [{"used_lineages": list(used), "candidate_lineage": agent.lineage}]
        if problems:
            found.extend(problems)
            continue
        return _Evaluation(rule, agent_id, found, evidence)
    return _Evaluation(rule, None, found)


def _reach(edges: Mapping[str, set], start: str) -> set:
    seen: set[str] = set()
    stack = [start]
    while stack:
        for child in edges.get(stack.pop(), ()):
            if child not in seen:
                seen.add(child)
                stack.append(child)
    return seen


def _ask_testimony(chooser: Any, request: RoutingRequest, table: RoutingTable, evaluations: list,
                   heads: tuple) -> tuple[Optional[str], dict[str, Any], Optional[str]]:
    """Put the closed question to the LLM chooser.  -> (agent id or None, testimony view, undecided reason)."""
    agents = {item.id: item for item in table.agents}
    candidates = []
    for agent_id in heads:  # the listing order is not an input: the chooser shuffles what it shows
        agent = agents[agent_id]
        reasons = [e.rule.reason for e in evaluations if e.head == agent_id and e.rule.reason]
        kinds = ",".join(sorted(agent.kinds)) if agent.kinds is not None else "undeclared"
        roles = ",".join(sorted(agent.roles)) if agent.roles is not None else "undeclared"
        summary = (f"roles={roles} kinds={kinds} "
                   f"lineage={agent.lineage or 'undeclared'} model={agent.model or 'undeclared'}")
        candidates.append(ChoiceCandidate(agent_id, (summary, *reasons)))
    word = f"job role={request.role} kind={request.kind} size={request.size}"
    try:
        decision = chooser.choose(word, candidates, "この仕事に最も合うエージェントはどれか")
    except Exception as exc:  # a chooser that raises is a failure of the testimony, not a decision
        return None, {"status": "FAILED", "detail": type(exc).__name__}, "TESTIMONY_FAILED"
    view = {"status": decision.status, "decision_id": decision.decision_id, "cached": decision.cached,
            "ask_ids": list(decision.ask_ids), "choice": decision.choice, "reason": decision.reason,
            "reuse_decision_id": decision.reuse_decision_id, "word": word, "asked": list(heads)}
    if decision.status == "ADOPTED":
        if decision.choice in heads:
            return decision.choice, view, None
        return None, view, "TESTIMONY_OUT_OF_SET"
    return None, view, {"ABSTAINED": "TESTIMONY_ABSTAINED", "FAILED": "TESTIMONY_FAILED"}.get(
        decision.status, "TESTIMONY_REFUSED")


def routable(table: RoutingTable, request: RoutingRequest) -> bool:
    """Whether the table has anything to say about this request's role: a rule written ``role=<this role>``
    (the role's fallback included), or a rule with no ``role=`` that matches the request's kind and size.
    The one place this is decided; ``route`` and the conductor both ask it."""
    return any(rule.role == request.role or (rule.role is None and rule.matches(request)) for rule in table.rules)


def route(table: RoutingTable, request: RoutingRequest, *,
          chooser_factory: Optional[Callable[[], Any]] = None) -> RoutingDecision:
    """Decide which agent does one job.  The order below is the pre-registered one and is written once:

    1. the matching rules (a rule with no ``role=`` matches a request of any role), each walked along its own preference list (concurrency, independence, declared
       roles and kinds exclude; every exclusion is recorded); a rule with no survivor falls away, and the
       role's fallback rule is used only when no other rule has a head;
    2. when the heads disagree, the human's routing precedence (transitive) resolves them;
    3. when that does not decide, the closed LLM choice (two asks must agree) among the remaining heads;
    4. otherwise a typed NONE.  Nothing is chosen by position.

    The fallback rule of the role (``RoutingRule.fallback``) is the human's "otherwise": it is used only when
    no other matching rule has a head.
    """
    if not isinstance(table, RoutingTable) or not isinstance(request, RoutingRequest):
        raise TypeError("route takes a RoutingTable and a RoutingRequest")
    agents = {item.id: item for item in table.agents}
    for ids in request.used_agents.values():
        for name in ids:
            if name not in agents:
                raise ValueError(f"used_agents names {name!r}, which is not in the routing table")
    lineages = _Lineages(table.agents, table.lineage_relations)
    common = dict(job_id=request.job_id, role=request.role, kind=request.kind, size=request.size,
                  size_basis=request.size_basis)

    def none(reason: str, **extra: Any) -> RoutingDecision:
        return RoutingDecision(agent_id=None, stage="NONE", decided_by="NONE", undecided_reason=reason,
                               **common, **extra)

    if not routable(table, request):
        return none("ROLE_NOT_ROUTABLE")
    evaluations = [_evaluate(rule, request, agents, lineages)
                   for rule in table.rules if not rule.fallback and rule.matches(request)]
    if not any(item.head for item in evaluations):
        evaluations += [_evaluate(rule, request, agents, lineages)
                        for rule in table.rules if rule.fallback and rule.role == request.role]
    matched = _display(item.rule.id for item in evaluations)
    excluded = tuple(sorted((e for item in evaluations for e in item.exclusions),
                            key=lambda e: (e.rule_id, e.agent_id, e.reason)))  # display order only
    headed = [item for item in evaluations if item.head is not None]
    if not headed:
        return none("NO_VIABLE_CANDIDATE", matched_rules=matched, excluded=excluded,
                    matched_contents=tuple(item.rule.content() for item in evaluations))
    heads = _display(item.head for item in headed)
    kind_fit = {agent_id: ("declared" if agents[agent_id].kinds is not None else "undeclared") for agent_id in heads}
    role_fit = {agent_id: ("declared" if agents[agent_id].roles is not None else "undeclared") for agent_id in heads}
    found = dict(matched_rules=matched, candidates=heads, excluded=excluded, kind_fit=kind_fit, role_fit=role_fit,
                 matched_contents=tuple(item.rule.content() for item in evaluations))

    def decided(agent_id: str, stage: str, decided_by: str, **extra: Any) -> RoutingDecision:
        won = [item for item in headed if item.head == agent_id]
        winners = [item.rule for item in won]
        independence: dict[str, str] = {}
        basis: dict[str, list] = {}
        for item in won:
            for other in item.rule.independent_roles_for(request.role):
                independence[other] = "distinct_lineage"
                for entry in item.evidence.get(other, ()):
                    if entry not in basis.setdefault(other, []):
                        basis[other].append(entry)
        for rule in winners:
            if rule.waives_independence and "implement" not in independence:
                independence["implement"] = f"waived_by:rule:{rule.id}"
        return RoutingDecision(agent_id=agent_id, stage=stage, decided_by=decided_by, independence=independence,
                               independence_basis=basis, agent_basis=agents[agent_id].basis,
                               **{**found, **extra}, **common)

    if len(heads) == 1:
        return decided(heads[0], "rule", "rule:" + ",".join(_display(item.rule.id for item in headed)))

    # the human's precedence between rules, read transitively
    edges: dict[str, set] = {}
    for entry in table.precedence:
        edges.setdefault(entry.higher, set()).add(entry.lower)
    names = {entry.higher for entry in table.precedence} | {entry.lower for entry in table.precedence}
    reach = {name: _reach(edges, name) for name in names}

    def outranks(upper: str, lower: str) -> bool:
        return lower in reach.get(upper, ())

    def on_a_path(entry: RoutingPrecedence, upper: str, lower: str) -> bool:
        return ((entry.higher == upper or outranks(upper, entry.higher)) and
                (entry.lower == lower or outranks(entry.lower, lower)))

    standing = []     # headed rules that no headed rule with a different head outranks
    used: set[str] = set()
    for item in headed:
        above = [other for other in headed if other.head != item.head and outranks(other.rule.id, item.rule.id)]
        if not above:
            standing.append(item)
        for other in above:
            used.update(entry.id for entry in table.precedence if on_a_path(entry, other.rule.id, item.rule.id))
    survivors = _display(item.head for item in standing)
    narrowed = dict(precedence_used=_display(used))   # candidates stay the heads that were in contention
    if len(survivors) == 1:
        return decided(survivors[0], "precedence", "precedence", **narrowed)

    chooser = chooser_factory() if chooser_factory is not None else None
    if chooser is None:
        return none("TESTIMONY_UNAVAILABLE", **{**found, **narrowed})
    chosen, view, problem = _ask_testimony(chooser, request, table, [item for item in headed if item.head in survivors],
                                           survivors)
    if chosen is None:
        return none(problem or "TESTIMONY_FAILED", **{**found, **narrowed}, testimony=view)
    return decided(chosen, "llm_testimony", f"llm_testimony:{view['decision_id']}", testimony=view, **narrowed)


def _sentences(entry: Mapping[str, Any]) -> Any:
    """The sentences a dictionary record was read from: ``witnesses`` (a list) or ``witness`` (one sentence)."""
    many = entry.get("witnesses")
    return many if many is not None else entry.get("witness")


def table_from_dicts(agents: Iterable[Mapping[str, Any]], rules: Iterable[Mapping[str, Any]],
                     precedence: Iterable[Mapping[str, Any]] = (), *, source: str = "dict",
                     lineage_relations: Iterable[Mapping[str, Any]] = ()) -> RoutingTable:
    """A producer that is not the DSL: plain dictionaries, each with the sentence(s) it was read from.

    ``agents``: id, adapter, witnesses (or witness); roles, kinds, lineage, model, effort, concurrency and note
    only when the human said them (an id and a lineage are the human's own words, e.g. 'Sonnet 5.5', 'Claude系').
    A lineage label is a decision of the producer: the same label is one lineage, two labels are two.  When the
    producer cannot tell whether two names are one lineage it gives no label and says what the human said in
    ``lineage_relations``: a, b (agent ids), relation ('same' or 'distinct'), witnesses (or witness).
    ``rules``: id, when (a mapping of condition name to value), prefer (a list of agent ids), witnesses (or
    witness); reason only when given; fallback (true for the role's "otherwise").
    ``precedence``: id, higher, lower, witnesses (or witness); reason only when given.
    A field that was not said stays absent (``None``): nothing is made up.  A missing field that every record
    needs is reported with the same record error codes as any other producer.
    """
    made_agents, made_rules, made_precedence = [], [], []
    for entry in agents:
        made_agents.append(AgentRecord(
            id=entry.get("id"), adapter=entry.get("adapter"), roles=entry.get("roles"),
            kinds=entry.get("kinds"), lineage=entry.get("lineage"),
            basis=Basis.text(source, _sentences(entry)), model=entry.get("model"), effort=entry.get("effort"),
            concurrency=entry.get("concurrency"), note=entry.get("note")))
    for entry in rules:
        made_rules.append(RoutingRule(
            entry.get("id"), tuple(Condition(str(k), str(v)) for k, v in dict(entry.get("when", {})).items()),
            tuple(entry.get("prefer", ())), entry.get("reason"), Basis.text(source, _sentences(entry)),
            entry.get("fallback", False)))
    for entry in precedence:
        made_precedence.append(RoutingPrecedence(entry.get("id"), entry.get("higher"), entry.get("lower"),
                                                 entry.get("reason"), Basis.text(source, _sentences(entry))))
    made_relations = [LineageRelation(entry.get("a"), entry.get("b"), entry.get("relation"),
                                      Basis.text(source, _sentences(entry))) for entry in lineage_relations]
    return build_routing_table(made_agents, made_rules, made_precedence, made_relations)


__all__ = [
    "ADAPTERS", "AgentRecord", "BASIS_KINDS", "Basis", "CONDITION_FIELDS", "Condition", "DECLARED_KEYS",
    "DSL_ERRORS", "EXCLUSION_REASONS", "Exclusion", "JOIN_KEYS", "KIND_FIT_VALUES", "LINEAGE_RELATIONS",
    "LINEAGE_VERDICTS", "LineageRelation", "LineageVerdict", "MEASURED_KEYS", "NO_INDEPENDENCE", "RECORD_ERRORS",
    "ROLES", "RoutingDecision", "RoutingPrecedence", "RoutingRecordError", "RoutingRequest", "RoutingRule",
    "RoutingTable", "SIZES", "SIZE_THRESHOLDS", "STAGES", "TASK_KINDS", "UNDECIDED_REASONS", "build_routing_table",
    "lineage_relation", "measured_fields", "routable", "route", "size_of", "table_from_dicts",
]
