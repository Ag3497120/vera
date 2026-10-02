"""Strict human-owned project frames compiled into typed conductor records.

The file format is intentionally small and closed.  Each section appears once;
unknown fields, duplicate sections, ambiguous list entries, and implicit empty
sections are errors with source line numbers.  List sections can be explicitly
empty with the sole line ``none: none``.

Sections, in any order, are ``[goal]``, ``[philosophy_invariants]``,
``[completion_criteria]``, ``[phases]``, ``[phase_order]``, ``[decisions]``,
``[vocabulary_aliases]``, ``[escalation_conditions]``, and
``[protected_actions]``.  See ``docs/frames/vera_project_frame.md`` for the
canonical example and entry grammar.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

from . import conductor, memory_frame
from .memory_frame import Memory, WriteRejected


SECTIONS = (
    "goal",
    "philosophy_invariants",
    "completion_criteria",
    "phases",
    "phase_order",
    "decisions",
    "vocabulary_aliases",
    "escalation_conditions",
    "protected_actions",
)
_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
_HEADER = re.compile(r"^\[([a-z_]+)\]$")
_HASH = re.compile(r"^[0-9a-fA-F]{64}$")
_COMMIT = re.compile(r"^[0-9a-fA-F]{40,64}$")
_POLICY_KINDS = frozenset(("CHOICE", "CONFIRM", "SCOPE"))
_QUESTION_KINDS = frozenset(conductor.QUESTION_KINDS)


class FrameError(ValueError):
    """A frame error that always identifies the source and line."""

    def __init__(self, source: str, line: int, message: str):
        self.source = source
        self.line = line
        self.message = message
        super().__init__(f"{source}:{line}: {message}")


class FrameParseError(FrameError):
    """Invalid or incomplete human frame syntax."""


class FrameCompileError(FrameError):
    """A valid frame entry could not be encoded as a typed record."""


@dataclass(frozen=True)
class Invariant:
    id: str
    text: str
    line: int


@dataclass(frozen=True)
class Criterion:
    id: str
    text: str
    line: int
    human_judged: bool
    witness: Optional[dict[str, Any]]


@dataclass(frozen=True)
class Phase:
    id: str
    name: str
    line: int


@dataclass(frozen=True)
class PhaseOrder:
    before: str
    after: str
    reason: str
    line: int


@dataclass(frozen=True)
class Decision:
    id: str
    subject: str
    choice: str
    line: int
    question_kind: Optional[str] = None
    condition: Optional[str] = None


@dataclass(frozen=True)
class Alias:
    alias: str
    canonical: str
    line: int


@dataclass(frozen=True)
class Escalation:
    id: str
    condition: str
    reason: str
    missing: str
    question_kind: Optional[str]
    line: int


@dataclass(frozen=True)
class ProtectedAction:
    action: str
    reason: str
    missing: str
    line: int


@dataclass(frozen=True)
class ProjectFrameSpec:
    project: str
    goal: str
    goal_line: int
    source: str
    invariants: tuple[Invariant, ...]
    criteria: tuple[Criterion, ...]
    phases: tuple[Phase, ...]
    phase_order: tuple[PhaseOrder, ...]
    decisions: tuple[Decision, ...]
    aliases: tuple[Alias, ...]
    escalations: tuple[Escalation, ...]
    protected_actions: tuple[ProtectedAction, ...]


@dataclass
class Compilation:
    """Compiled active records and the conductor that answers from them."""

    spec: ProjectFrameSpec
    memory: Memory
    conductor: conductor.ProjectFrame
    records: list[dict[str, Any]]


def _fail(source: str, line: int, message: str) -> None:
    raise FrameParseError(source, line, message)


def _required_text(value: str, source: str, line: int, field: str) -> str:
    value = value.strip()
    if not value:
        _fail(source, line, f"{field} must not be empty")
    if "\n" in value or "\r" in value:
        _fail(source, line, f"{field} must occupy one line")
    return value


def _entry_id(value: str, source: str, line: int, field: str = "entry id") -> str:
    value = value.strip()
    if not _ID.fullmatch(value):
        _fail(source, line, f"invalid {field} {value!r}; use a letter followed by letters, digits, _ or -")
    return value


def _split_once(value: str, marker: str, source: str, line: int, field: str) -> tuple[str, str]:
    if value.count(marker) != 1:
        _fail(source, line, f"{field} must contain exactly one {marker!r}")
    left, right = value.split(marker, 1)
    return (_required_text(left, source, line, field), _required_text(right, source, line, field))


def _strict_json_object(raw: str, source: str, line: int) -> dict[str, Any]:
    def pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in pairs:
            if key in out:
                raise ValueError(f"duplicate JSON field {key!r}")
            out[key] = value
        return out

    try:
        value = json.loads(raw, object_pairs_hook=pairs)
    except (json.JSONDecodeError, ValueError) as exc:
        _fail(source, line, f"invalid witness JSON: {exc}")
    if not isinstance(value, dict):
        _fail(source, line, "machine witness must be a JSON object")
    return value


def _validate_witness(raw: str, source: str, line: int) -> dict[str, Any]:
    witness = _strict_json_object(raw, source, line)
    kind = witness.get("kind")
    fields = {
        "file_sha256": {"kind", "path", "sha256"},
        "text_in_file": {"kind", "path", "needle"},
        "git_commit": {"kind", "repo", "commit"},
        "command_exit": {"kind", "command", "expected_exit"},
    }
    if not isinstance(kind, str) or kind not in fields:
        _fail(source, line, "machine witness kind must be file_sha256, text_in_file, git_commit, or command_exit")
    if set(witness) != fields[kind]:
        _fail(source, line, f"{kind} witness fields must be exactly {sorted(fields[kind])}")
    if kind == "file_sha256":
        if not isinstance(witness["path"], str) or not witness["path"] or not isinstance(witness["sha256"], str) or not _HASH.fullmatch(witness["sha256"]):
            _fail(source, line, "file_sha256 needs a nonempty path and 64 hexadecimal sha256 digits")
        witness["sha256"] = witness["sha256"].lower()
    elif kind == "text_in_file":
        if not isinstance(witness["path"], str) or not witness["path"] or not isinstance(witness["needle"], str) or not witness["needle"]:
            _fail(source, line, "text_in_file needs nonempty path and needle strings")
    elif kind == "git_commit":
        if not isinstance(witness["repo"], str) or not witness["repo"] or not isinstance(witness["commit"], str) or not _COMMIT.fullmatch(witness["commit"]):
            _fail(source, line, "git_commit needs a nonempty repo and a full hexadecimal commit id")
        witness["commit"] = witness["commit"].lower()
    else:
        command = witness["command"]
        if (not isinstance(command, str) and not isinstance(command, list)) or not command:
            _fail(source, line, "command_exit needs a nonempty command string or list of strings")
        if isinstance(command, str) and not command.strip():
            _fail(source, line, "command_exit command must not be whitespace")
        if isinstance(command, list) and not all(isinstance(part, str) and part for part in command):
            _fail(source, line, "command_exit command list must contain only nonempty strings")
        if isinstance(witness["expected_exit"], bool) or not isinstance(witness["expected_exit"], int):
            _fail(source, line, "command_exit expected_exit must be an integer")
    return witness


def _rows(section: str, sections: Mapping[str, list[tuple[int, str]]], source: str, eof: int) -> list[tuple[int, str]]:
    rows = sections[section]
    if not rows:
        _fail(source, eof, f"[{section}] is empty; write 'none: none' to state that explicitly")
    if any(text == "none: none" for _, text in rows):
        if len(rows) != 1 or rows[0][1] != "none: none":
            line = next(line for line, text in rows if text == "none: none")
            _fail(source, line, "'none: none' must be the only entry in its section")
        return []
    return rows


def _unique_ids(items: list[Any], source: str, label: str) -> None:
    seen: set[str] = set()
    for item in items:
        if item.id in seen:
            _fail(source, item.line, f"duplicate {label} id {item.id!r}")
        seen.add(item.id)


def _check_order_graph(phases: tuple[Phase, ...], orders: tuple[PhaseOrder, ...], source: str, eof: int) -> None:
    known = {phase.id for phase in phases}
    edges: dict[str, list[str]] = {phase.id: [] for phase in phases}
    seen: set[tuple[str, str]] = set()
    for order in orders:
        if order.before not in known:
            _fail(source, order.line, f"phase order references unknown phase {order.before!r}")
        if order.after not in known:
            _fail(source, order.line, f"phase order references unknown phase {order.after!r}")
        if order.before == order.after:
            _fail(source, order.line, "a phase cannot precede itself")
        edge = (order.before, order.after)
        if edge in seen:
            _fail(source, order.line, f"duplicate phase order {order.before} -> {order.after}")
        seen.add(edge)
        edges[order.before].append(order.after)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> Optional[str]:
        if node in visiting:
            return node
        if node in visited:
            return None
        visiting.add(node)
        for child in edges[node]:
            cycle = visit(child)
            if cycle:
                return cycle
        visiting.remove(node)
        visited.add(node)
        return None

    for phase in phases:
        cycle = visit(phase.id)
        if cycle:
            line = next((item.line for item in orders if item.before == cycle), eof)
            _fail(source, line, f"phase ordering contains a cycle through {cycle!r}")


def parse_frame(text: str, *, source: str = "<frame>") -> ProjectFrameSpec:
    """Parse the closed human frame format, reporting every error with a line."""
    if not isinstance(text, str):
        raise TypeError("frame text must be a string")
    lines = text.splitlines()
    eof = len(lines) + 1
    sections: dict[str, list[tuple[int, str]]] = {name: [] for name in SECTIONS}
    seen_sections: set[str] = set()
    current: Optional[str] = None
    for line_no, original in enumerate(lines, 1):
        row = original.strip()
        if not row or row.startswith("#"):
            continue
        if row.startswith("[") or row.endswith("]"):
            match = _HEADER.fullmatch(row)
            if not match:
                _fail(source, line_no, "section header must be an exact lowercase [section_name]")
            name = match.group(1)
            if name not in sections:
                _fail(source, line_no, f"unknown section [{name}]")
            if name in seen_sections:
                _fail(source, line_no, f"duplicate section [{name}]")
            seen_sections.add(name)
            current = name
            continue
        if current is None:
            _fail(source, line_no, "content must appear inside a declared section")
        sections[current].append((line_no, row))

    missing_sections = [name for name in SECTIONS if name not in seen_sections]
    if missing_sections:
        _fail(source, eof, f"missing required section(s): {', '.join('[' + x + ']' for x in missing_sections)}")

    goal_values: dict[str, tuple[int, str]] = {}
    for line_no, row in sections["goal"]:
        if ":" not in row:
            _fail(source, line_no, "[goal] entries use 'project: ...' or 'statement: ...'")
        key, value = row.split(":", 1)
        key = key.strip()
        if key not in {"project", "statement"}:
            _fail(source, line_no, f"unknown [goal] field {key!r}")
        if key in goal_values:
            _fail(source, line_no, f"duplicate [goal] field {key!r}")
        goal_values[key] = (line_no, _required_text(value, source, line_no, key))
    for required in ("project", "statement"):
        if required not in goal_values:
            _fail(source, eof, f"[goal] requires {required!r}")
    _, project = goal_values["project"]
    goal_line, goal = goal_values["statement"]

    invariants: list[Invariant] = []
    for line_no, row in _rows("philosophy_invariants", sections, source, eof):
        if ":" not in row:
            _fail(source, line_no, "invariants use 'ID: invariant text'")
        key, value = row.split(":", 1)
        invariants.append(Invariant(_entry_id(key, source, line_no), _required_text(value, source, line_no, "invariant"), line_no))
    _unique_ids(invariants, source, "invariant")

    criteria: list[Criterion] = []
    for line_no, row in _rows("completion_criteria", sections, source, eof):
        if row.count("|") != 1:
            _fail(source, line_no, "criteria use 'ID: criterion text | human-judged' or a JSON machine witness")
        head, witness_text = row.split("|", 1)
        if ":" not in head:
            _fail(source, line_no, "criterion needs an ID followed by ':'")
        key, value = head.split(":", 1)
        criterion_text = _required_text(value, source, line_no, "criterion")
        witness_text = _required_text(witness_text, source, line_no, "criterion witness")
        if witness_text == "human-judged":
            human_judged, witness = True, None
        else:
            human_judged = False
            witness = _validate_witness(witness_text, source, line_no)
        criteria.append(Criterion(_entry_id(key, source, line_no), criterion_text, line_no, human_judged, witness))
    _unique_ids(criteria, source, "criterion")

    phases: list[Phase] = []
    for line_no, row in _rows("phases", sections, source, eof):
        if ":" not in row:
            _fail(source, line_no, "phases use 'ID: phase name'")
        key, value = row.split(":", 1)
        phases.append(Phase(_entry_id(key, source, line_no), _required_text(value, source, line_no, "phase name"), line_no))
    _unique_ids(phases, source, "phase")

    phase_order: list[PhaseOrder] = []
    for line_no, row in _rows("phase_order", sections, source, eof):
        if ":" not in row:
            _fail(source, line_no, "phase order uses 'BEFORE -> AFTER: reason'")
        relation, reason = row.split(":", 1)
        if relation.count("->") != 1:
            _fail(source, line_no, "phase order needs exactly one '->'")
        before, after = (piece.strip() for piece in relation.split("->", 1))
        phase_order.append(PhaseOrder(_entry_id(before, source, line_no, "phase id"),
                                      _entry_id(after, source, line_no, "phase id"),
                                      _required_text(reason, source, line_no, "phase-order reason"), line_no))

    decisions: list[Decision] = []
    for line_no, row in _rows("decisions", sections, source, eof):
        if ":" not in row:
            _fail(source, line_no, "decisions start with 'ID:'")
        key, body = row.split(":", 1)
        key = _entry_id(key, source, line_no, "decision id")
        body = _required_text(body, source, line_no, "decision")
        if "|" in body:
            if body.count("|") != 2:
                _fail(source, line_no, "policy decision uses 'ID: CHOICE|CONFIRM|SCOPE | condition | answer'")
            kind, condition, answer = (part.strip() for part in body.split("|"))
            if kind not in _POLICY_KINDS:
                _fail(source, line_no, f"policy decision kind must be one of {', '.join(sorted(_POLICY_KINDS))}")
            decisions.append(Decision(key, condition, _required_text(answer, source, line_no, "policy answer"),
                                      line_no, kind, condition))
        else:
            subject, choice = _split_once(body, "=>", source, line_no, "decision")
            decisions.append(Decision(key, subject, choice, line_no))
    _unique_ids(decisions, source, "decision")

    aliases: list[Alias] = []
    for line_no, row in _rows("vocabulary_aliases", sections, source, eof):
        alias, canonical = _split_once(row, "=>", source, line_no, "vocabulary alias")
        if alias.casefold() == canonical.casefold():
            _fail(source, line_no, "an alias must differ from its canonical term")
        aliases.append(Alias(alias, canonical, line_no))
    alias_keys = [item.alias.casefold() for item in aliases]
    if len(alias_keys) != len(set(alias_keys)):
        duplicate = next(item for item in aliases if alias_keys.count(item.alias.casefold()) > 1)
        _fail(source, duplicate.line, f"duplicate vocabulary alias {duplicate.alias!r}")
    for item in aliases:
        if item.canonical.casefold() in alias_keys:
            _fail(source, item.line, f"canonical term {item.canonical!r} is itself declared as an alias")

    escalations: list[Escalation] = []
    for line_no, row in _rows("escalation_conditions", sections, source, eof):
        if ":" not in row:
            _fail(source, line_no, "escalation uses 'ID: condition => reason => missing => scope'")
        key, body = row.split(":", 1)
        key = _entry_id(key, source, line_no, "escalation id")
        if body.count("=>") != 3:
            _fail(source, line_no, "escalation needs condition, reason, missing record, and scope separated by three '=>'")
        condition, reason, missing, scope = (part.strip() for part in body.split("=>"))
        condition = _required_text(condition, source, line_no, "escalation condition")
        reason = _required_text(reason, source, line_no, "escalation reason")
        missing = _required_text(missing, source, line_no, "missing record")
        scope = _required_text(scope, source, line_no, "escalation scope")
        if scope != "ANY" and scope not in _QUESTION_KINDS:
            _fail(source, line_no, f"escalation scope must be ANY or a conductor question kind: {', '.join(sorted(_QUESTION_KINDS))}")
        escalations.append(Escalation(key, condition, reason, missing, None if scope == "ANY" else scope, line_no))
    _unique_ids(escalations, source, "escalation")

    protected_actions: list[ProtectedAction] = []
    for line_no, row in _rows("protected_actions", sections, source, eof):
        if row.count("=>") != 2:
            _fail(source, line_no, "protected action uses 'action => reason => missing record'")
        action, reason, missing = (part.strip() for part in row.split("=>"))
        protected_actions.append(ProtectedAction(_required_text(action, source, line_no, "protected action"),
                                                 _required_text(reason, source, line_no, "protected-action reason"),
                                                 _required_text(missing, source, line_no, "missing record"), line_no))
    protected_keys = [item.action.casefold() for item in protected_actions]
    if len(protected_keys) != len(set(protected_keys)):
        duplicate = next(item for item in protected_actions if protected_keys.count(item.action.casefold()) > 1)
        _fail(source, duplicate.line, f"duplicate protected action {duplicate.action!r}")

    spec = ProjectFrameSpec(project, goal, goal_line, source, tuple(invariants), tuple(criteria), tuple(phases),
                            tuple(phase_order), tuple(decisions), tuple(aliases), tuple(escalations),
                            tuple(protected_actions))
    _check_order_graph(spec.phases, spec.phase_order, source, eof)
    return spec


def load_frame(path: str | Path) -> ProjectFrameSpec:
    """Read and parse a UTF-8 frame file."""
    frame_path = Path(path)
    try:
        text = frame_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FrameParseError(str(frame_path), 1, f"cannot read frame: {exc}") from exc
    return parse_frame(text, source=str(frame_path))


def _source_witness(spec: ProjectFrameSpec, section: str, line: int, entry: str, **extra: Any) -> dict[str, Any]:
    return {"kind": "testimony", "by": "frame author", "source": spec.source,
            "line": line, "section": section, "entry": entry, **extra}


def _write(memory: Memory, kind: str, slots: dict[str, str], witness: dict[str, Any],
           spec: ProjectFrameSpec, line: int) -> dict[str, Any]:
    try:
        return memory.write(kind, "frame author", witness=witness, **slots)
    except (WriteRejected, KeyError, ValueError) as exc:
        detail = getattr(exc, "reason", str(exc))
        raise FrameCompileError(spec.source, line, f"cannot compile {kind} record: {detail}") from exc


def compile_frame(spec: ProjectFrameSpec, memory: Memory | str | Path) -> Compilation:
    """Compile a parsed frame into a fresh memory log and conductor records.

    ``memory`` must be an empty ``Memory`` or a path to a new/empty memory log.
    Existing records are never silently mixed into a frame compilation.
    """
    if not isinstance(spec, ProjectFrameSpec):
        raise TypeError("compile_frame expects the ProjectFrameSpec returned by parse_frame/load_frame")
    if isinstance(memory, Memory):
        store = memory
    else:
        store = Memory(str(memory))
    if store.records:
        raise FrameCompileError(spec.source, spec.goal_line, "compilation requires an empty memory log")
    frame = conductor.ProjectFrame(store)
    records: list[dict[str, Any]] = []
    source_text = f"{spec.project}: {spec.goal}"

    goal_decision = _write(store, "DECISION", {"subject": f"{spec.project} goal", "choice": spec.goal},
                           _source_witness(spec, "goal", spec.goal_line, source_text), spec, spec.goal_line)
    records.append(goal_decision)

    for item in spec.invariants:
        record = _write(store, "INVARIANT", {"subject": f"invariant {item.id}", "rule": item.text},
                        _source_witness(spec, "philosophy_invariants", item.line, item.text), spec, item.line)
        records.append(record)

    for item in spec.criteria:
        witness_spec: dict[str, Any]
        if item.human_judged:
            check = "human judged"
            acceptance_witness: dict[str, Any] = {"kind": "human-judged"}
        else:
            assert item.witness is not None
            check_names = {"file_sha256": "file sha256", "text_in_file": "text in file",
                           "git_commit": "git commit", "command_exit": "command exit"}
            check = check_names[item.witness["kind"]]
            acceptance_witness = dict(item.witness)
        acceptance = {
            "task_id": spec.project,
            "item": item.text,
            "witness": acceptance_witness,
            "human_judged": item.human_judged,
            "independent": False,
        }
        criterion_record = _write(
            store, "ACCEPTANCE", {"subject": item.text, "check": check},
            _source_witness(spec, "completion_criteria", item.line, item.text, acceptance=acceptance), spec, item.line)
        records.append(criterion_record)
        goal_record = _write(
            store, "GOAL", {"subject": spec.project, "value": item.text},
            _source_witness(spec, "goal", spec.goal_line, source_text,
                            completion_criterion_id=item.id, acceptance_record_id=criterion_record["id"]),
            spec, spec.goal_line)
        records.append(goal_record)

    for item in spec.decisions:
        decision = _write(store, "DECISION", {"subject": item.subject, "choice": item.choice},
                          _source_witness(spec, "decisions", item.line, f"{item.subject} => {item.choice}",
                                          decision_id=item.id), spec, item.line)
        records.append(decision)
        if item.question_kind:
            policy = _write(
                store, "POLICY", {"subject": item.condition or item.subject, "answer": item.choice},
                _source_witness(spec, "decisions", item.line, f"{item.question_kind} | {item.condition} | {item.choice}",
                                question_kind=item.question_kind, condition=item.condition,
                                authority_record_id=decision["id"]), spec, item.line)
            records.append(policy)

    for item in spec.phases:
        phase_record = _write(
            store, "DECISION", {"subject": f"phase {item.id}", "choice": item.name},
            _source_witness(spec, "phases", item.line, item.name, phase_id=item.id), spec, item.line)
        records.append(phase_record)

    for item in spec.phase_order:
        order_reason = f"phase order {item.before} to {item.after}"
        reason_record = _write(
            store, "DECISION", {"subject": order_reason, "choice": item.reason},
            _source_witness(spec, "phase_order", item.line, f"{item.before} -> {item.after}: {item.reason}"),
            spec, item.line)
        records.append(reason_record)
        order_record = _write(
            store, "ORDER", {"subject": item.before, "target": item.after},
            _source_witness(spec, "phase_order", item.line, f"{item.before} -> {item.after}: {item.reason}",
                            reason_record_id=reason_record["id"]), spec, item.line)
        records.append(order_record)

    for item in spec.aliases:
        alias_record = _write(store, "ALIAS", {"subject": item.alias, "value": item.canonical},
                              _source_witness(spec, "vocabulary_aliases", item.line,
                                              f"{item.alias} => {item.canonical}", scope="frame-vocabulary",
                                              word=item.alias), spec, item.line)
        records.append(alias_record)

    for item in spec.escalations:
        escalation = _write(
            store, "ESCALATE", {"subject": item.condition, "target": "human"},
            _source_witness(spec, "escalation_conditions", item.line, item.condition,
                            condition=item.condition, reason=item.reason, missing=item.missing,
                            question_kind=item.question_kind), spec, item.line)
        records.append(escalation)

    for index, item in enumerate(spec.protected_actions, 1):
        code = f"PA{index}"
        invariant_text = f"Human approval is required before {item.action}"
        boundary = _write(
            store, "INVARIANT", {"subject": f"protected action {code}", "rule": invariant_text},
            _source_witness(spec, "protected_actions", item.line, item.action,
                            authority_boundary=True, protected_action=item.action), spec, item.line)
        records.append(boundary)
        escalation = _write(
            store, "ESCALATE", {"subject": item.action, "target": "human"},
            _source_witness(spec, "protected_actions", item.line, item.action,
                            condition=item.action, reason=item.reason, missing=item.missing,
                            protected_action=True, question_kind=None), spec, item.line)
        records.append(escalation)

    return Compilation(spec, store, frame, records)


__all__ = [
    "Alias", "Compilation", "Criterion", "Decision", "Escalation", "FrameCompileError",
    "FrameError", "FrameParseError", "Invariant", "Phase", "PhaseOrder", "ProjectFrameSpec",
    "ProtectedAction", "SECTIONS", "compile_frame", "load_frame", "parse_frame",
]
