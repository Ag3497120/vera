"""Drive a bounded project through typed memory and an ``AgentAdapter``.

This module is orchestration only. Agent output is an untrusted event stream;
questions go to :class:`ProjectFrame`, and claims are checked against the
frame's acceptance witnesses. No agent text is turned into Vera evidence.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from . import (agent_adapter, conductor_escalate, memory_brief, memory_lessons,
               memory_merge, memory_revalidate, verifier_agents)
from .agent_adapter import AgentAdapter
from .conductor import AgentQuestion, ProjectFrame, Reply
from .verifier_agents import VerifierAgent


JOURNAL_SCHEMA = "conductor-run-v1"
MAX_RUN_SECONDS = 30.0
MAX_RUN_EVENTS = 100
MAX_BRIEF_CHARS = agent_adapter.MAX_BRIEF_CHARS


class JournalError(ValueError):
    """The durable driver log cannot be replayed without guessing."""


@dataclass(frozen=True)
class RunResult:
    complete: bool
    completed: tuple[str, ...]
    pending: tuple[str, ...]
    blocking_item: Mapping[str, Any] | None
    outcomes: tuple[Mapping[str, Any], ...] = ()
    handoffs: tuple[Mapping[str, Any], ...] = ()
    interrupted: bool = False
    resumed: bool = False


class _Journal:
    """Small append-only event log; incomplete records are never replayed."""

    def __init__(self, path: Path):
        self.path = path
        self.rows: list[dict[str, Any]] = []
        self.run_id = ""
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = self.path.read_bytes()
        except OSError as exc:
            raise JournalError("driver log cannot be read") from exc
        if raw and not raw.endswith(b"\n"):
            raise JournalError("driver log ends with an incomplete event")
        rows: list[dict[str, Any]] = []
        try:
            for line in raw.splitlines():
                value = json.loads(line)
                if not isinstance(value, dict) or value.get("schema") != JOURNAL_SCHEMA:
                    raise JournalError("driver log has an unsupported event")
                if type(value.get("seq")) is not int or value["seq"] != len(rows):
                    raise JournalError("driver log event sequence is incomplete")
                if (not isinstance(value.get("type"), str) or not value["type"] or
                        not isinstance(value.get("run_id"), str) or not value["run_id"]):
                    raise JournalError("driver log event fields are malformed")
                if rows and value["run_id"] != rows[0]["run_id"]:
                    raise JournalError("driver log contains multiple runs")
                rows.append(value)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            raise JournalError("driver log contains malformed JSON") from exc
        self.rows = rows
        self.run_id = rows[0]["run_id"] if rows else ""

    def append(self, kind: str, **fields: Any) -> dict[str, Any]:
        if not self.run_id:
            self.run_id = uuid.uuid4().hex
        row = {"schema": JOURNAL_SCHEMA, "run_id": self.run_id,
               "seq": len(self.rows), "type": kind, **fields}
        try:
            line = json.dumps(row, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":"), allow_nan=False) + "\n"
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(line)
                stream.flush()
                os.fsync(stream.fileno())
        except (OSError, TypeError, ValueError, RecursionError) as exc:
            raise JournalError("driver log event could not be made durable") from exc
        self.rows.append(row)
        return row

    def events(self, kind: str) -> list[dict[str, Any]]:
        return [row for row in self.rows if row.get("type") == kind]

    def has(self, kind: str, task_id: str) -> bool:
        return any(row.get("type") == kind and row.get("task_id") == task_id
                   for row in self.rows)


def _goal_tasks(frame: ProjectFrame) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for record in frame._active():
        if record.get("kind") != "GOAL":
            continue
        task_id = str(record.get("slots", {}).get("subject", "")).strip()
        key = task_id.casefold()
        if task_id and key not in seen:
            result.append(task_id)
            seen.add(key)
    return tuple(result)


def _revalidated_statuses(frame: ProjectFrame) -> dict[str, str]:
    """Re-check active record witnesses through the read-only memory wrapper."""
    checked = memory_revalidate.RevalidatingMemory(
        frame.memory, cache_ttl=0, cache_size=0,
    ).ask("driver witness status probe", require_fresh=False)
    statuses = checked.get("witness_status", {})
    return statuses if isinstance(statuses, dict) else {}


def _task_key(task_id: str) -> str:
    return task_id.strip().casefold()


def _load_order_graph(frame: ProjectFrame, task_ids: Sequence[str]) -> tuple[
        dict[str, tuple[str, ...]], tuple[str, ...], dict[str, tuple[str, ...]]]:
    """Load the active ORDER graph, refuse stale authority and cycles, and rank tasks."""
    records = frame.memory.active(require_fresh=False)
    statuses = _revalidated_statuses(frame)
    by_id = {str(record.get("id", "")): record for record in records}
    edges: list[tuple[str, str, dict[str, Any]]] = []
    graph: dict[str, set[str]] = {}
    for record in records:
        if record.get("kind") != "ORDER":
            continue
        slots = record.get("slots", {})
        before = str(slots.get("subject", "")).strip()
        after = str(slots.get("target", "")).strip()
        if not before or not after:
            raise ValueError("ORDER record has a missing phase identity")
        if statuses.get(str(record.get("id", ""))) == "STALE":
            raise ValueError("ORDER witness is STALE and must be re-verified")
        witness = record.get("witness", {})
        reason_id = witness.get("reason_record_id") if isinstance(witness, Mapping) else None
        reason = by_id.get(str(reason_id or ""))
        if (reason is None or reason.get("kind") not in {"DECISION", "INVARIANT"} or
                statuses.get(str(reason.get("id", ""))) == "STALE"):
            raise ValueError("ORDER authority witness is stale or inactive and must be re-verified")
        authority_slot = "choice" if reason.get("kind") == "DECISION" else "rule"
        authority_subject = _task_key(str(reason.get("slots", {}).get("subject", "")))
        authority_values = {
            _task_key(str(peer.get("slots", {}).get(authority_slot, "")))
            for peer in records
            if (peer.get("kind") == reason.get("kind") and
                _task_key(str(peer.get("slots", {}).get("subject", ""))) == authority_subject and
                statuses.get(str(peer.get("id", ""))) != "STALE")
        }
        if len(authority_values) != 1:
            raise ValueError("ORDER authority is conflicted and cannot determine a phase")
        graph.setdefault(_task_key(before), set()).add(_task_key(after))
        graph.setdefault(_task_key(after), set())
        edges.append((_task_key(before), _task_key(after), record))

    indegree = {node: 0 for node in graph}
    for children in graph.values():
        for child in children:
            indegree[child] = indegree.get(child, 0) + 1
    ready = sorted(node for node, degree in indegree.items() if degree == 0)
    visited = 0
    while ready:
        node = ready.pop(0)
        visited += 1
        for child in sorted(graph.get(node, ())):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
                ready.sort()
    if visited != len(indegree):
        raise ValueError("active ORDER graph contains a cycle")

    task_by_key = {_task_key(task_id): task_id for task_id in task_ids}
    predecessors: dict[str, set[str]] = {key: set() for key in task_by_key}
    edge_ids: dict[str, list[str]] = {key: [] for key in task_by_key}
    for before, after, record in edges:
        if after in predecessors:
            predecessors[after].add(before)
            edge_ids[after].append(str(record.get("id", "")))

    remaining = list(task_ids)
    ordered: list[str] = []
    ordered_keys: set[str] = set()
    while remaining:
        candidate = next((task for task in remaining
                          if all(pred not in task_by_key or pred in ordered_keys
                                 for pred in predecessors[_task_key(task)])), None)
        if candidate is None:
            # Out-of-frame predecessors are retained as an order gate at run time.
            candidate = remaining[0]
        remaining.remove(candidate)
        ordered.append(candidate)
        ordered_keys.add(_task_key(candidate))
    return ({key: tuple(sorted(values)) for key, values in predecessors.items()},
            tuple(ordered), {key: tuple(sorted(ids)) for key, ids in edge_ids.items()})


def _active_record_ids(frame: ProjectFrame) -> set[str]:
    statuses = _revalidated_statuses(frame)
    return {str(record.get("id", "")) for record in frame.memory.active(require_fresh=False)
            if statuses.get(str(record.get("id", ""))) != "STALE"}


def _reply_with_fresh_citations(frame: ProjectFrame, reply: Reply) -> Reply:
    """Require an ANSWER to cite current, non-stale frame records."""
    if reply.kind != "ANSWER":
        return reply
    citations = tuple(dict.fromkeys(str(rid) for rid in reply.record_ids if rid))
    current = _active_record_ids(frame)
    statuses = _revalidated_statuses(frame)
    if not citations:
        return Reply("ESCALATE", why="frame answer had no record citation",
                     reason="frame answer had no record citation", missing="cited frame record",
                     question_kind=reply.question_kind)
    if any(rid not in current or statuses.get(rid) == "STALE" for rid in citations):
        return Reply("ESCALATE", record_ids=tuple(rid for rid in citations if rid in current),
                     why="a cited memory witness is stale or no longer active",
                     reason="a cited memory witness is stale or no longer active",
                     missing="fresh frame record", question_kind=reply.question_kind)
    return Reply(reply.kind, reply.answer, citations, reply.why, reply.reason, reply.missing,
                 reply.question_kind, reply.template_id, reply.target, reply.spec)


def _serialize_reply(reply: Reply) -> str:
    return json.dumps(reply.as_dict(), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def _as_reply(value: Any) -> Reply:
    if isinstance(value, Reply):
        return value
    if isinstance(value, Mapping):
        kind = value.get("kind")
        if kind in {"ANSWER", "ESCALATE", "ASK_VERIFIER"}:
            return Reply(kind, value.get("answer"), tuple(value.get("record_ids", ())),
                         str(value.get("why", "")), str(value.get("reason", "")),
                         value.get("missing"), value.get("question_kind"),
                         value.get("template_id"), value.get("target"), value.get("spec"))
    return Reply("ESCALATE", why="verification returned an invalid result",
                 reason="verification returned an invalid result", missing="typed verifier result",
                 question_kind="STATUS")


def _normalise_event(event: Any) -> dict[str, Any]:
    """Pass arbitrary adapters through the same closed schema as the CLI adapter."""
    try:
        payload = json.dumps(event, ensure_ascii=False, allow_nan=False,
                             separators=(",", ":"))
        parsed = agent_adapter.parse_agent_output(payload)
    except (TypeError, ValueError, RecursionError):
        return {"type": "ERROR", "message": "adapter returned a non-JSON event"}
    if len(parsed) != 1:
        return {"type": "ERROR", "message": "adapter returned an invalid event batch"}
    return parsed[0]


def _claimant(task_id: str, requested: str) -> str:
    return requested.strip() if requested.strip() else "agent:" + task_id


def _verify(frame: ProjectFrame, task_id: str, claimant_id: str,
            adapter: AgentAdapter, verifiers: Sequence[VerifierAgent],
            claimant_session_id: str, max_polls: int, timeout_seconds: float,
            clock: Callable[[], float]) -> Reply:
    reply = _as_reply(frame.verify_claim(task_id, {"claimant_id": claimant_id}))
    if reply.kind != "ASK_VERIFIER":
        return _reply_with_fresh_citations(frame, reply)
    if not verifiers:
        return Reply("ESCALATE", record_ids=reply.record_ids,
                     why="an independent verifier is required but none is configured",
                     reason="an independent verifier is required but none is configured",
                     missing="independent verifier", question_kind="STATUS",
                     template_id=reply.template_id, target=reply.target, spec=reply.spec)
    result = verifier_agents.run_verifiers(
        frame, task_id, reply, verifiers, claimant_id=claimant_id,
        claimant_session_id=claimant_session_id, claimant_adapter=adapter,
        max_polls=max_polls, timeout_seconds=min(timeout_seconds, 30.0), clock=clock,
    )
    final = _as_reply(result)
    if final.kind == "ANSWER":
        return _reply_with_fresh_citations(frame, final)
    return final


def _lesson(frame: ProjectFrame, task_id: str, event_type: str,
            journal: _Journal, reason: str) -> str | None:
    """Store a failure trigger and repair cue as typed LESSON testimony."""
    suffix = f"{len(journal.rows):04d}"
    try:
        record = frame.memory.write(
            "LESSON", f"conductor_run_{journal.run_id}_{suffix}",
            witness={"kind": "testimony", "by": "conductor_run", "source": "driver outcome"},
            situation=f"{task_id}検証失敗",
            fix=f"{event_type}結果確認",
        )
        return str(record.get("id", "")) or None
    except Exception as exc:
        journal.append("LESSON_WRITE_REJECTED", task_id=task_id, event_type=event_type,
                       reason=str(reason)[:512], error=type(exc).__name__)
        return None


def _store_handoff(frame: ProjectFrame, question: AgentQuestion, reply: Reply,
                   journal: _Journal, task_id: str) -> dict[str, Any]:
    try:
        handoff = conductor_escalate.enrich(reply, frame, question)
        value = handoff.as_dict()
    except Exception as exc:
        value = {
            "question": {"id": question.id, "text": question.text,
                         "options": question.options, "claimed_state": question.claimed_state},
            "reply": reply.as_dict(),
            "missing": {"kind": "record_kind", "value": reply.missing or "typed human handoff"},
            "resolver": "human", "cause": type(exc).__name__, "scope": "agent_refusal",
        }
    journal.append("ESCALATION", task_id=task_id, handoff=value)
    return value


def _write_task_done(frame: ProjectFrame, task_id: str, reply: Reply,
                     journal: _Journal) -> dict[str, Any]:
    current = [record for record in frame.memory.active(require_fresh=True)
               if record.get("kind") == "TASK" and
               str(record.get("slots", {}).get("subject", "")).casefold() == task_id.casefold()]
    supersedes = current[-1].get("id") if current else None
    author = f"conductor_run_{journal.run_id}_{len(journal.rows):04d}"
    return frame.memory.write(
        "TASK", author,
        witness={"kind": "testimony", "by": "conductor_run",
                 "acceptance_record_ids": list(reply.record_ids), "task_id": task_id},
        supersedes=supersedes, subject=task_id, state="完了",
    )


def _task_done_record(frame: ProjectFrame, task_id: str) -> bool:
    statuses = _revalidated_statuses(frame)
    return any(record.get("kind") == "TASK" and
               _task_key(str(record.get("slots", {}).get("subject", ""))) == _task_key(task_id) and
               str(record.get("slots", {}).get("state", "")) == "完了" and
               statuses.get(str(record.get("id", ""))) != "STALE" and
               isinstance(record.get("witness"), Mapping) and
               record["witness"].get("by") == "conductor_run" and
               record["witness"].get("task_id") == task_id and
               isinstance(record["witness"].get("acceptance_record_ids"), list) and
               bool(record["witness"].get("acceptance_record_ids"))
               for record in frame.memory.active(require_fresh=False))


def _task_done_matches(frame: ProjectFrame, task_id: str, reply: Reply) -> bool:
    """Require the saved DONE witness to cover today's GOAL and ACCEPTANCE rows."""
    current_acceptance_ids = {
        str(record.get("id", "")) for record in frame._active()
        if ((record.get("kind") == "GOAL" and
             _task_key(str(record.get("slots", {}).get("subject", ""))) == _task_key(task_id)) or
            (record.get("kind") == "ACCEPTANCE" and
             _task_key(str(record.get("witness", {}).get("acceptance", {}).get("task_id", ""))) ==
             _task_key(task_id)))
    }
    cited_now = set(reply.record_ids)
    if not current_acceptance_ids or not current_acceptance_ids.issubset(cited_now):
        return False
    for record in frame.memory.active(require_fresh=False):
        witness = record.get("witness", {})
        if (record.get("kind") == "TASK" and
                _task_key(str(record.get("slots", {}).get("subject", ""))) == _task_key(task_id) and
                str(record.get("slots", {}).get("state", "")) == "完了" and
                _task_key(str(witness.get("task_id", ""))) == _task_key(task_id) and
                current_acceptance_ids.issubset(set(witness.get("acceptance_record_ids", ())))):
            return True
    return False


def _memory_events(frame: ProjectFrame) -> list[dict[str, Any]]:
    """Snapshot the frame's in-memory event state without reopening its path."""
    memory = frame.memory
    events = [{"op": "write", "record": record} for record in memory.records.values()]
    events.extend({"op": "supersede", "id": old, "by": new}
                  for old, new in memory.superseded.items())
    events.extend(dict(event) for event in memory.aliases.values())
    return events


class ConductorRun:
    """Resume-safe driver for a typed project frame and one work adapter.

    An adapter may optionally implement ``recover(run_id, task_id, cursor)``.
    An unfinished start without that recovery hook is left for a human instead
    of launching a potentially duplicated side effect.
    """

    def __init__(
        self,
        frame: ProjectFrame,
        adapter: AgentAdapter,
        *,
        log_path: str | os.PathLike[str] | None = None,
        claimant_id: str = "agent",
        claimant_session_id: str | None = None,
        verifiers: Sequence[VerifierAgent] = (),
        task_ids: Sequence[str] | None = None,
        agent_memory_logs: Sequence[Sequence[Mapping[str, Any]]] = (),
        max_events: int = MAX_RUN_EVENTS,
        timeout_seconds: float = MAX_RUN_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ):
        if not isinstance(frame, ProjectFrame):
            raise TypeError("frame must be a ProjectFrame")
        if not all(callable(getattr(adapter, method, None))
                   for method in ("start", "poll", "send", "stop")):
            raise TypeError("adapter must implement start, poll, send and stop")
        if isinstance(max_events, bool) or not isinstance(max_events, int) or not 1 <= max_events <= MAX_RUN_EVENTS:
            raise ValueError(f"max_events must be between 1 and {MAX_RUN_EVENTS}")
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)):
            raise ValueError("timeout_seconds must be finite and positive")
        if not 0 < float(timeout_seconds) <= MAX_RUN_SECONDS:
            raise ValueError(f"timeout_seconds must be between 0 and {MAX_RUN_SECONDS}")
        self.frame = frame
        self.adapter = adapter
        memory_path = Path(frame.memory.path)
        self.log_path = Path(log_path) if log_path is not None else Path(str(memory_path) + ".driver.jsonl")
        self.claimant_id = claimant_id
        self.claimant_session_id = claimant_session_id
        self.verifiers = tuple(verifiers)
        self.task_ids = tuple(task_ids) if task_ids is not None else _goal_tasks(frame)
        if any(not isinstance(task_id, str) or not task_id.strip() for task_id in self.task_ids):
            raise ValueError("task_ids must contain nonempty strings")
        if len({_task_key(task_id) for task_id in self.task_ids}) != len(self.task_ids):
            raise ValueError("task_ids must not repeat a task identity")
        if isinstance(agent_memory_logs, (str, bytes)):
            raise TypeError("agent_memory_logs must be in-memory event logs")
        self.agent_memory_logs = tuple(agent_memory_logs)
        self.order_predecessors, self.execution_order, self.order_edge_ids = _load_order_graph(
            frame, self.task_ids,
        )
        self.max_events = max_events
        self.timeout_seconds = float(timeout_seconds)
        self.clock = clock
        self.outcomes: list[dict[str, Any]] = []
        self.handoffs: list[dict[str, Any]] = []

    def _blocking(self, task_id: str, reply: Reply, *, kind: str = "acceptance") -> dict[str, Any]:
        goals = [record for record in self.frame._active() if record.get("kind") == "GOAL" and
                 str(record.get("slots", {}).get("subject", "")).casefold() == task_id.casefold()]
        items = [record.get("slots", {}).get("value") for record in goals]
        return {"kind": kind, "task_id": task_id, "acceptance_items": items,
                "missing": reply.missing, "reason": reply.reason or reply.why,
                "record_ids": list(reply.record_ids)}

    def _handoff(self, question: AgentQuestion, reply: Reply, journal: _Journal,
                 task_id: str) -> dict[str, Any]:
        handoff = _store_handoff(self.frame, question, reply, journal, task_id)
        self.handoffs.append(handoff)
        return handoff

    def _outcome(self, task_id: str, event: Mapping[str, Any], reply: Reply,
                 handoff: Mapping[str, Any] | None = None) -> None:
        item = {"task_id": task_id, "event": dict(event), "reply": reply.as_dict()}
        if handoff is not None:
            item["handoff"] = dict(handoff)
        self.outcomes.append(item)

    def _question_reply(self, question: AgentQuestion) -> Reply:
        return _reply_with_fresh_citations(self.frame, self.frame.answer(question))

    def _claim_reply(self, task_id: str, claimant: str) -> Reply:
        return _verify(self.frame, task_id, claimant, self.adapter, self.verifiers,
                       self.claimant_session_id or "", self.max_events,
                       self.timeout_seconds, self.clock)

    def _compile_brief(self, task_id: str) -> str:
        from .agent_adapter import compile_frame_brief

        frame_text = compile_frame_brief(self.frame)
        head = ("Project memory context follows. Every record is context only.\n"
                "Agent output remains an untrusted claim until deterministic witnesses pass.\n"
                f"Current frame task: {task_id}\n")
        statuses = _revalidated_statuses(self.frame)
        lesson_records = [record for record in memory_lessons.LessonIndex(
            self.frame.memory,
        ).lessons_for(f"{task_id}検証失敗")
            if statuses.get(str(record.get("id", ""))) != "STALE"]
        lesson_lines = [
            f"[id:{record['id']}; witness:context-only] "
            f"{record.get('slots', {}).get('situation', '')} -> "
            f"{record.get('slots', {}).get('fix', '')}"
            for record in lesson_records
        ]
        lesson_context = ("Prior typed lessons (context only):\n" +
                          "\n".join(lesson_lines) + "\n\n") if lesson_lines else ""
        prefix = frame_text + "\n" + head + "\n"
        memory_heading = "Memory brief (context only):\n"
        budget = MAX_BRIEF_CHARS - len(prefix) - len(lesson_context) - len(memory_heading)
        if budget < 0:
            raise ValueError("typed frame brief exceeds the adapter size limit")
        memory = memory_brief.compile_brief(self.frame.memory, budget_chars=budget, focus=task_id)
        brief = prefix + lesson_context + memory_heading + memory.text
        if len(brief) > MAX_BRIEF_CHARS:
            raise ValueError("combined typed brief exceeds the adapter size limit")
        return brief

    def _merge_agent_memory(self, journal: _Journal) -> dict[str, Any] | None:
        """Merge writer event logs and stop on typed active-value conflicts."""
        if not self.agent_memory_logs:
            return None
        try:
            merged: Any = _memory_events(self.frame)
            for log in self.agent_memory_logs:
                if isinstance(log, (str, bytes)) or not isinstance(log, Sequence):
                    raise ValueError("each agent memory log must be an event sequence")
                merged = memory_merge.merge_logs(merged, log)
            active = memory_merge.active_records(merged)
            conflicts = memory_merge.conflicts(merged)
        except Exception as exc:
            reason = f"agent memory logs could not be merged: {type(exc).__name__}"
            reply = Reply("ESCALATE", why=reason, reason=reason,
                          missing="valid merged agent memory", question_kind="OTHER")
            question = AgentQuestion("memory-merge-invalid", "How should invalid agent memory logs be handled?")
            handoff = self._handoff(question, reply, journal, "project")
            return {"kind": "memory_merge", "missing": reply.missing,
                    "reason": reason, "handoff": handoff}

        typed_conflicts = [
            {"kind": conflict.kind, "subject": conflict.subject,
             "attribute": conflict.attribute, "record_ids": list(conflict.record_ids),
             "values": list(conflict.values)}
            for conflict in conflicts
        ]
        journal.append("MEMORY_MERGE", merged_active_records=len(active),
                       conflict_count=len(typed_conflicts), conflicts=typed_conflicts)
        if not typed_conflicts:
            return None
        record_ids = tuple(dict.fromkeys(
            record_id for conflict in typed_conflicts
            for record_id in conflict["record_ids"]
        ))
        reason = "agent memory merge found conflicting active typed values"
        reply = Reply("ESCALATE", record_ids=record_ids, why=reason, reason=reason,
                      missing="typed CONFLICT resolution", question_kind="OTHER")
        question = AgentQuestion(
            "memory-conflict",
            "How should the conflicting typed agent memory records be resolved?",
        )
        handoff = self._handoff(question, reply, journal, "project")
        return {"kind": "memory_conflict", "missing": reply.missing,
                "reason": reason, "record_ids": list(record_ids),
                "conflicts": typed_conflicts, "handoff": handoff}

    def _order_gate(self, task_id: str,
                    claimant_by_task: Mapping[str, str]) -> Reply | None:
        key = _task_key(task_id)
        for predecessor in self.order_predecessors.get(key, ()):
            predecessor_task = next((item for item in self.task_ids
                                     if _task_key(item) == predecessor), None)
            edge_ids = self.order_edge_ids.get(key, ())
            if predecessor_task is None:
                reason = "ORDER predecessor is outside the active GOAL frame"
                return Reply("ESCALATE", record_ids=edge_ids, why=reason, reason=reason,
                             missing="predecessor GOAL and witnessed DONE", question_kind="ORDER")
            if not _task_done_record(self.frame, predecessor_task):
                reason = f"ORDER predecessor {predecessor_task} has no witnessed DONE record"
                return Reply("ESCALATE", record_ids=edge_ids, why=reason, reason=reason,
                             missing="predecessor witnessed DONE", question_kind="ORDER")
            verified = self._claim_reply(predecessor_task, claimant_by_task[predecessor_task])
            if (verified.kind != "ANSWER" or verified.answer != "done" or
                    not _task_done_matches(self.frame, predecessor_task, verified)):
                reason = f"ORDER predecessor {predecessor_task} must be re-verified"
                return Reply("ESCALATE",
                             record_ids=tuple(dict.fromkeys((*edge_ids, *verified.record_ids))),
                             why=reason, reason=reason, missing="fresh predecessor acceptance witnesses",
                             question_kind="ORDER")
        return None

    def run(self) -> RunResult:
        resumed = self.log_path.exists()
        try:
            journal = _Journal(self.log_path)
            if not journal.run_id:
                journal.append("RUN_CREATED", tasks=list(self.task_ids))
            elif not journal.events("RUN_CREATED"):
                raise JournalError("driver log is missing its run header")
        except JournalError as exc:
            return RunResult(False, (), self.task_ids,
                             {"kind": "driver_log", "missing": str(exc)}, resumed=resumed)

        memory_block = self._merge_agent_memory(journal)
        if memory_block is not None:
            return RunResult(False, (), self.task_ids, memory_block,
                             tuple(self.outcomes), tuple(self.handoffs), resumed=resumed)

        if not self.task_ids:
            return RunResult(False, (), (),
                             {"kind": "completion_frame", "missing": "active GOAL acceptance items",
                              "reason": "the frame contains no project task to run"}, resumed=resumed)

        completed: list[str] = []
        pending: list[str] = []
        blocking: Mapping[str, Any] | None = None
        interrupted = False
        if not self.claimant_session_id:
            self.claimant_session_id = "run:" + journal.run_id
        claimant_by_task = {task_id: _claimant(task_id, self.claimant_id)
                            for task_id in self.task_ids}
        deadline = self.clock() + self.timeout_seconds

        for task_id in self.execution_order:
            order_reply = self._order_gate(task_id, claimant_by_task)
            if order_reply is not None:
                blocking = self._blocking(task_id, order_reply, kind="order_predecessor")
                question = AgentQuestion(
                    "order-gate:" + task_id,
                    f"What must be verified before the ORDER phase {task_id} can start?",
                )
                self._handoff(question, order_reply, journal, task_id)
                pending.extend(item for item in self.task_ids if item not in completed)
                break

            claimant = claimant_by_task[task_id]
            previous_start = [row for row in journal.events("AGENT_STARTED")
                              if row.get("task_id") == task_id]
            latest_start = max((row["seq"] for row in previous_start), default=-1)
            has_confirmed_stop = any(row.get("task_id") == task_id and row["seq"] > latest_start
                                     for row in journal.events("AGENT_STOPPED"))
            if _task_done_record(self.frame, task_id):
                checked = self._claim_reply(task_id, claimant)
                if (checked.kind == "ANSWER" and checked.answer == "done" and
                        _task_done_matches(self.frame, task_id, checked)):
                    completed.append(task_id)
                    journal.append("TASK_REUSED", task_id=task_id,
                                   record_ids=list(checked.record_ids))
                    continue
                # A prior DONE whose criterion went stale is not trusted.
                journal.append("PRIOR_DONE_STALE", task_id=task_id,
                               reason=(checked.reason or checked.why or
                                       "saved DONE witness does not cover current acceptance records"),
                               record_ids=list(checked.record_ids))

            if previous_start and not has_confirmed_stop:
                recover = getattr(self.adapter, "recover", None)
                if not callable(recover):
                    blocking = {"kind": "uncertain_agent_session", "task_id": task_id,
                                "missing": "adapter recovery identity",
                                "reason": "an unfinished agent session cannot safely be restarted"}
                    reply = Reply("ESCALATE", why=blocking["reason"], reason=blocking["reason"],
                                  missing=blocking["missing"], question_kind="STATUS")
                    question = AgentQuestion("resume:" + task_id,
                                             f"How should the uncertain session for {task_id} be resumed?")
                    self._handoff(question, reply, journal, task_id)
                    pending.extend(item for item in self.task_ids if item not in completed)
                    interrupted = True
                    break
                last_cursor = max((int(row.get("cursor", 0)) for row in journal.events("AGENT_EVENT")
                                   if row.get("task_id") == task_id), default=0)
                try:
                    handle = recover(journal.run_id, task_id, last_cursor)
                    journal.append("AGENT_RECOVERED", task_id=task_id, cursor=last_cursor)
                except Exception as exc:
                    blocking = {"kind": "uncertain_agent_session", "task_id": task_id,
                                "missing": "adapter recovery identity", "reason": type(exc).__name__}
                    reply = Reply("ESCALATE", why=blocking["reason"], reason=blocking["reason"],
                                  missing=blocking["missing"], question_kind="STATUS")
                    question = AgentQuestion("resume:" + task_id,
                                             f"How should the uncertain session for {task_id} be resumed?")
                    self._handoff(question, reply, journal, task_id)
                    pending.extend(item for item in self.task_ids if item not in completed)
                    interrupted = True
                    break
            else:
                try:
                    brief = self._compile_brief(task_id)
                    if self.clock() >= deadline:
                        raise TimeoutError("driver deadline reached before agent start")
                    brief_hash = hashlib.sha256(brief.encode("utf-8")).hexdigest()
                    journal.append("AGENT_STARTED", task_id=task_id, cursor=0,
                                   brief_sha256=brief_hash)
                    handle = self.adapter.start(brief)
                except Exception as exc:
                    journal.append("INTERRUPTED", task_id=task_id,
                                   reason=f"agent start failed: {type(exc).__name__}")
                    blocking = {"kind": "agent_start", "task_id": task_id,
                                "missing": "agent session", "reason": str(exc)[:512]}
                    reply = Reply("ESCALATE", why=blocking["reason"], reason=blocking["reason"],
                                  missing=blocking["missing"], question_kind="STATUS")
                    question = AgentQuestion("start:" + task_id,
                                             f"How should the failed session start for {task_id} be handled?")
                    self._handoff(question, reply, journal, task_id)
                    pending.extend(item for item in self.task_ids if item not in completed)
                    interrupted = True
                    break

            terminal = False
            task_verified = False
            event_count = 0
            try:
                while not terminal and event_count < self.max_events:
                    if self.clock() >= deadline:
                        raise TimeoutError("driver run deadline reached")
                    raw_events = self.adapter.poll(handle)
                    if not raw_events:
                        break
                    if not isinstance(raw_events, list):
                        raw_events = [raw_events]
                    for raw_event in raw_events:
                        event = _normalise_event(raw_event)
                        event_count += 1
                        journal.append("AGENT_EVENT", task_id=task_id,
                                       cursor=event_count, event=event)
                        event_type = event.get("type")
                        reply: Reply
                        handoff = None
                        if event_type == "QUESTION" or event_type == "OTHER":
                            question = agent_adapter.to_conductor_question(event)
                            reply = self._question_reply(question)
                            if reply.kind == "ESCALATE":
                                handoff = self._handoff(question, reply, journal, task_id)
                            self._outcome(task_id, event, reply, handoff)
                            journal.append("QUESTION_RESULT", task_id=task_id,
                                           question_id=question.id, reply=reply.as_dict())
                        elif event_type == "CLAIM":
                            claimed_task = str(event.get("task", ""))
                            if claimed_task not in self.task_ids:
                                reply = Reply("ESCALATE", why="claim names a task outside the frame",
                                              reason="claim names a task outside the frame",
                                              missing="active GOAL task", question_kind="STATUS")
                            elif claimed_task != task_id:
                                reply = Reply(
                                    "ESCALATE",
                                    record_ids=self.order_edge_ids.get(_task_key(claimed_task), ()),
                                    why="claim does not match the currently scheduled ORDER phase",
                                    reason="claim does not match the currently scheduled ORDER phase",
                                    missing="currently scheduled task", question_kind="ORDER",
                                )
                            else:
                                reply = self._claim_reply(claimed_task, claimant_by_task[claimed_task])
                            if reply.kind != "ANSWER" or reply.answer != "done":
                                lesson_id = _lesson(self.frame, task_id, "CLAIM", journal,
                                                    reply.reason or reply.why)
                                if reply.kind == "ESCALATE":
                                    question = AgentQuestion("claim:" + str(event_count),
                                                            f"Can claim for {claimed_task or task_id} be accepted?")
                                    handoff = self._handoff(question, reply, journal, task_id)
                            self._outcome(task_id, event, reply, handoff)
                            journal.append("CLAIM_RESULT", task_id=task_id,
                                           claimed_task=claimed_task, reply=reply.as_dict(),
                                           lesson_record_id=lesson_id if reply.kind != "ANSWER" else None)
                        elif event_type == "DONE":
                            reply = self._claim_reply(task_id, claimant)
                            if reply.kind == "ANSWER" and reply.answer == "done":
                                task_record = _write_task_done(self.frame, task_id, reply, journal)
                                completed.append(task_id)
                                task_verified = True
                                self._outcome(task_id, event, reply)
                                journal.append("TASK_DONE", task_id=task_id,
                                               task_record_id=task_record["id"],
                                               acceptance_record_ids=list(reply.record_ids))
                                terminal = True
                            else:
                                _lesson(self.frame, task_id, "DONE", journal,
                                        reply.reason or reply.why)
                                question = AgentQuestion("done:" + str(event_count),
                                                        f"Can completion of {task_id} be verified?")
                                if reply.kind == "ESCALATE":
                                    handoff = self._handoff(question, reply, journal, task_id)
                                self._outcome(task_id, event, reply, handoff)
                                journal.append("DONE_REJECTED", task_id=task_id,
                                               reply=reply.as_dict())
                        else:
                            message = str(event.get("message", "agent protocol error"))
                            reply = Reply("ESCALATE", why="agent event protocol failed",
                                          reason="agent event protocol failed: " + message[:256],
                                          missing="valid agent event", question_kind="OTHER")
                            _lesson(self.frame, task_id, "ERROR", journal, reply.reason)
                            question = AgentQuestion("protocol:" + str(event_count),
                                                    "How should an invalid agent event be handled?")
                            handoff = self._handoff(question, reply, journal, task_id)
                            self._outcome(task_id, event, reply, handoff)
                            self.adapter.send(handle, _serialize_reply(reply))
                            blocking = self._blocking(task_id, reply, kind="agent_protocol")
                            terminal = True
                            break

                        self.adapter.send(handle, _serialize_reply(reply))
                        if terminal:
                            break
                        if event_count >= self.max_events:
                            break
                if not task_verified and blocking is None:
                    verify = self._claim_reply(task_id, claimant)
                    if verify.kind == "ANSWER" and verify.answer == "done":
                        # A witnessed DONE event is required before task state changes.
                        refusal = Reply("ESCALATE", record_ids=verify.record_ids,
                                        why="acceptance passed but the agent did not send DONE",
                                        reason="acceptance passed but the agent did not send DONE",
                                        missing="agent DONE event", question_kind="STATUS")
                        question = AgentQuestion("done-missing:" + task_id,
                                                 f"What blocks the required DONE event for {task_id}?")
                        self._handoff(question, refusal, journal, task_id)
                        blocking = {"kind": "agent_terminal_event", "task_id": task_id,
                                    "missing": "agent DONE event",
                                    "reason": "acceptance is witnessed but the agent did not send DONE"}
                    elif verify.kind == "ESCALATE":
                        question = AgentQuestion("completion:" + task_id,
                                                 f"What blocks completion of {task_id}?")
                        handoff = self._handoff(question, verify, journal, task_id)
                        blocking = self._blocking(task_id, verify)
                    else:
                        blocking = {"kind": "agent_terminal_event", "task_id": task_id,
                                    "missing": "agent DONE event",
                                    "reason": "agent ended without a witnessed completion event"}
            except Exception as exc:
                journal.append("INTERRUPTED", task_id=task_id,
                               reason=f"agent session interrupted: {type(exc).__name__}",
                               completed=task_verified)
                blocking = {"kind": "agent_interruption", "task_id": task_id,
                            "missing": "recoverable agent session",
                            "reason": str(exc)[:512] or type(exc).__name__}
                if not task_verified:
                    reply = Reply("ESCALATE", why=blocking["reason"], reason=blocking["reason"],
                                  missing=blocking["missing"], question_kind="STATUS")
                    question = AgentQuestion("interrupted:" + task_id,
                                             f"How should the interrupted session for {task_id} be recovered?")
                    self._handoff(question, reply, journal, task_id)
                interrupted = True
            finally:
                try:
                    self.adapter.stop(handle)
                    journal.append("AGENT_STOPPED", task_id=task_id,
                                   completed=task_verified)
                except Exception as exc:
                    journal.append("INTERRUPTED", task_id=task_id,
                                   reason=f"agent stop failed: {type(exc).__name__}",
                                   completed=task_verified)
                    if blocking is None:
                        blocking = {"kind": "agent_interruption", "task_id": task_id,
                                    "missing": "agent stop confirmation",
                                    "reason": type(exc).__name__}
                    interrupted = True

            if task_id in completed and task_verified:
                if interrupted:
                    break
                continue
            if task_id not in completed:
                pending.extend(item for item in self.task_ids
                               if item not in completed and item not in pending)
                break

        # A task is complete only while its current acceptance witnesses remain valid.
        valid_completed: list[str] = []
        for task_id in self.task_ids:
            if not _task_done_record(self.frame, task_id):
                continue
            reply = self._claim_reply(task_id, claimant_by_task[task_id])
            if (reply.kind == "ANSWER" and reply.answer == "done" and
                    _task_done_matches(self.frame, task_id, reply)):
                valid_completed.append(task_id)
            elif blocking is None:
                blocking = self._blocking(task_id, reply)
        pending = [task_id for task_id in self.task_ids if task_id not in valid_completed]
        project_complete = bool(self.task_ids) and not pending and set(valid_completed) == set(self.task_ids)
        if not project_complete and blocking is None and pending:
            task_id = pending[0]
            verify = self._claim_reply(task_id, claimant_by_task[task_id])
            blocking = self._blocking(task_id, verify)
        return RunResult(project_complete, tuple(valid_completed), tuple(pending), blocking,
                         tuple(self.outcomes), tuple(self.handoffs), interrupted, resumed)


def run_project(frame: ProjectFrame, adapter: AgentAdapter, **kwargs: Any) -> RunResult:
    """Run or resume all GOAL tasks in ``frame`` using the supplied adapter."""
    return ConductorRun(frame, adapter, **kwargs).run()


__all__ = ["ConductorRun", "RunResult", "JournalError", "run_project"]


# ---------------------------------------------------------------------------
# Conduct entry: one frame file in, an agent start (or a typed refusal) out.
# Everything below was added after ConductorRun / run_project and does not
# change them.  CLI: ``python -m verantyx.cli conduct``; guide: docs/CONDUCT_ENTRY.md.
# ---------------------------------------------------------------------------
import fcntl as _fcntl
import re as _re
import subprocess as _subprocess

from . import agent_runtime as _agent_runtime
from . import memory_frame as _memory_frame
from . import project_frame as _project_frame
from .project_frame import FrameRefusal

LEDGER_SCHEMA = "conduct-ledger-v1"
ADAPTER_NAMES = ("codex", "claude", "fake")
_TASK_IN_BRIEF = _re.compile(r"^Current frame task:\s*(.*?)\s*$", _re.M)


class LedgerError(ValueError):
    """The conduct ledger cannot be extended without losing or inventing rows."""


class ConductLedger:
    """Append-only JSONL ledger of what the conduct entry read, refused and launched.

    Every row carries ``schema``, a ledger-wide consecutive ``seq``, ``run_id`` and
    ``type``.  A ledger whose ``seq`` jumps, or whose last line is cut off, is not
    extended (the same discipline as the driver journal).
    """

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)
        self.rows: list[dict[str, Any]] = self._read()

    def _read(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            raw = self.path.read_bytes()
        except OSError as exc:
            raise LedgerError("ledger cannot be read") from exc
        if raw and not raw.endswith(b"\n"):
            raise LedgerError("ledger ends with an incomplete row")
        rows: list[dict[str, Any]] = []
        try:
            for line in raw.splitlines():
                value = json.loads(line)
                if (not isinstance(value, dict) or value.get("schema") != LEDGER_SCHEMA or
                        type(value.get("seq")) is not int or value["seq"] != len(rows) or
                        not isinstance(value.get("type"), str) or not isinstance(value.get("run_id"), str)):
                    raise LedgerError("ledger has a malformed or out-of-sequence row")
                rows.append(value)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LedgerError("ledger contains malformed JSON") from exc
        return rows

    def append(self, run_id: str, kind: str, **fields: Any) -> dict[str, Any]:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        except OSError as exc:
            raise LedgerError("ledger cannot be opened for append") from exc
        try:
            _fcntl.flock(fd, _fcntl.LOCK_EX)
            self.rows = self._read()  # another writer may have appended since we last looked
            row = {"schema": LEDGER_SCHEMA, "seq": len(self.rows), "run_id": run_id, "type": kind,
                   "time": time.time(), **fields}
            data = (json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                               allow_nan=False) + "\n").encode("utf-8")
            view = memoryview(data)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        except (OSError, TypeError, ValueError, RecursionError) as exc:
            if isinstance(exc, LedgerError):
                raise
            raise LedgerError("ledger row could not be made durable") from exc
        finally:
            os.close(fd)
        self.rows.append(row)
        return row

    def events(self, kind: str) -> list[dict[str, Any]]:
        return [row for row in self.rows if row.get("type") == kind]


@dataclass(frozen=True)
class ConductOutcome:
    """The single result of a conduct call.  ``exit_code``: 0 ok, 1 incomplete, 2 refused, 3 internal."""

    verdict: str
    exit_code: int
    refusal: Mapping[str, Any] | None
    ledger: str | None
    run_id: str
    blocking: Mapping[str, Any] | None = None
    result: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"verdict": self.verdict, "refusal": dict(self.refusal) if self.refusal else None,
                "ledger": self.ledger, "run_id": self.run_id,
                "blocking": dict(self.blocking) if self.blocking else None,
                "result": dict(self.result) if self.result else None}


class _LedgerAdapter:
    """Wrap an adapter so the ledger shows that, and with what, ``start`` was reached."""

    def __init__(self, inner: AgentAdapter, ledger: ConductLedger, run_id: str, name: str):
        self._inner = inner
        self._ledger = ledger
        self._run_id = run_id
        self._name = name

    def start(self, brief: str) -> Any:
        digest = hashlib.sha256(brief.encode("utf-8")).hexdigest() if isinstance(brief, str) else None
        match = _TASK_IN_BRIEF.search(brief) if isinstance(brief, str) else None
        self._ledger.append(self._run_id, "AGENT_START_CALLED", adapter=self._name, brief_sha256=digest,
                            brief_chars=len(brief) if isinstance(brief, str) else None,
                            task_id=match.group(1) if match else None)
        try:
            handle = self._inner.start(brief)
        except Exception as exc:
            self._ledger.append(self._run_id, "AGENT_START_FAILED", adapter=self._name,
                                error=type(exc).__name__, message=str(exc)[:256])
            raise
        self._ledger.append(self._run_id, "AGENT_START_RETURNED", adapter=self._name,
                            handle_type=type(handle).__name__, brief_sha256=digest)
        return handle

    def poll(self, handle: Any) -> Any:
        return self._inner.poll(handle)

    def send(self, handle: Any, text: str) -> None:
        self._inner.send(handle, text)

    def stop(self, handle: Any) -> None:
        self._inner.stop(handle)

    def __getattr__(self, name: str) -> Any:
        # ConductorRun resumes only adapters that expose ``recover``; keep that honest.
        if name == "recover":
            inner = getattr(self._inner, "recover", None)
            if callable(inner):
                return inner
        raise AttributeError(name)


def _kind_counts(records: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        counts[str(record.get("kind"))] = counts.get(str(record.get("kind")), 0) + 1
    return dict(sorted(counts.items()))


def _resolve_setting(frame: _project_frame.ConductFrame, key: str, cli_value: Any) -> tuple[Any, str, Any]:
    """CLI beats the frame.  Returns (value, source, frame value overridden by the CLI)."""
    frame_values = frame.agent_settings.get(key, ())
    if len(frame_values) > 1:
        raise FrameRefusal("AGENT_SETTING_INVALID",
                           f"the frame states {len(frame_values)} different values for {key}; keep exactly one",
                           f"{key}: {', '.join(frame_values)}", source=frame.source)
    frame_value = frame_values[0] if frame_values else None
    if cli_value is not None:
        text = str(cli_value) if not isinstance(cli_value, bool) else "<bool>"
        problem = _project_frame.validate_agent_setting(key, text)
        if problem:
            raise FrameRefusal("AGENT_SETTING_INVALID", f"fix the command-line value for {key}: {problem}",
                               f"{key}={text!r}", source=frame.source)
        return text, "cli", frame_value
    if frame_value is not None:
        return frame_value, "frame", None
    return None, "unset", None


def _check_git_repo(repo: Path) -> None:
    try:
        _agent_runtime._git_root(repo)
        _agent_runtime._git(repo, "rev-parse", "HEAD")
    except (ValueError, OSError, _subprocess.SubprocessError) as exc:
        raise FrameRefusal("REPO_NOT_GIT",
                           "run 'git init' in the repository and make at least one commit "
                           "(the agent works in a git worktree created from HEAD)",
                           f"{type(exc).__name__}: {str(exc)[:200]}", source=os.fspath(repo)) from exc


def conduct_entry(
    frame_path: str | os.PathLike[str],
    repo: str | os.PathLike[str],
    adapter: str | AgentAdapter,
    *,
    dry_run: bool = False,
    state_dir: str | os.PathLike[str] | None = None,
    model: str | None = None,
    effort: str | None = None,
    max_concurrency: int | None = None,
    codex_bin: str = "codex",
    claude_bin: str = "claude",
    command_runner: Callable[[Mapping[str, Any]], Any] | None = None,
) -> ConductOutcome:
    """Read a frame, make typed records, and start (or, with ``dry_run``, plan) an agent.

    ``adapter`` is ``"codex"``, ``"claude"`` or ``"fake"``; a Python caller may instead
    pass an object implementing the ``AgentAdapter`` lifecycle (it is treated like
    ``fake``).  Nothing is raised for a bad input (only a caller error, an unknown ``adapter`` name, raises ``ValueError``): it comes back as a ``REFUSED``
    outcome with a typed reason and what is missing, and an unexpected exception
    comes back as ``INTERNAL_ERROR`` (exception type only).  ``command_runner`` is
    for Python callers; the CLI never supplies one, so a ``command_exit`` criterion
    stays unverified there.
    """
    if isinstance(adapter, str) and adapter not in ADAPTER_NAMES:
        raise ValueError(f"adapter must be one of {', '.join(ADAPTER_NAMES)} or an AgentAdapter object")
    run_id = uuid.uuid4().hex
    ledger: ConductLedger | None = None

    def put(kind: str, **fields: Any) -> None:
        if ledger is not None:
            ledger.append(run_id, kind, **fields)

    def refused(refusal: FrameRefusal, exit_code: int = 2) -> ConductOutcome:
        try:
            put("REFUSED", **refusal.as_dict())
        except Exception:
            pass
        return ConductOutcome("REFUSED", exit_code, refusal.as_dict(),
                              os.fspath(ledger.path) if ledger is not None else None, run_id)

    try:
        repo_path = Path(repo).expanduser()
        if state_dir is not None:
            state = Path(state_dir).expanduser()
        elif repo_path.is_dir():
            state = repo_path / ".verantyx-conduct"
        else:
            return refused(FrameRefusal(
                "REPO_NOT_FOUND", f"give --repo an existing directory ({os.fspath(repo_path)!r} is not one); "
                "no ledger is written because there is nowhere safe to put it (or pass --state-dir)",
                source=os.fspath(repo_path)))
        try:
            ledger = ConductLedger(state / "ledger.jsonl")
        except LedgerError as exc:
            return refused(FrameRefusal(
                "LEDGER_UNUSABLE", f"repair or move {os.fspath(state / 'ledger.jsonl')} (it is never overwritten) "
                "or pass another --state-dir", str(exc), source=os.fspath(state)))
        adapter_name = adapter if isinstance(adapter, str) else type(adapter).__name__
        put("CONDUCT_INVOKED", frame=os.fspath(frame_path), repo=os.fspath(repo_path), adapter=adapter_name,
            dry_run=bool(dry_run), state_dir=os.fspath(state),
            cli={"model": model, "effort": effort, "max_concurrency": max_concurrency})
        if not repo_path.is_dir():
            raise FrameRefusal("REPO_NOT_FOUND",
                               f"give --repo an existing directory ({os.fspath(repo_path)!r} is not one)",
                               source=os.fspath(repo_path))

        def on_read(info: Mapping[str, Any]) -> None:
            put("FRAME_READ", **info)

        frame = _project_frame.load_conduct_frame(frame_path, on_read=on_read)
        shortfall = _project_frame.check_conduct_ready(frame)
        if shortfall is not None:
            raise shortfall

        run_dir = state / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        memory_path = run_dir / "memory.jsonl"
        if frame.format == "markdown":
            assert frame.spec is not None
            try:
                compilation = _project_frame.compile_frame(frame.spec, memory_path)
            except _project_frame.FrameCompileError as exc:
                raise FrameRefusal("FRAME_COMPILE_ERROR", f"fix {exc.source}:{exc.line}: {exc.message}",
                                   exc.message, source=exc.source, line=exc.line) from exc
            conductor_frame = compilation.conductor
            compiled_records: Sequence[Mapping[str, Any]] = compilation.records
        else:
            # The input is copied: ConductorRun writes TASK and LESSON rows into its memory.
            memory_path.write_text(frame.text, encoding="utf-8")
            conductor_frame = ProjectFrame(_memory_frame.Memory(str(memory_path)))
            compiled_records = conductor_frame.memory.active(require_fresh=False)
        if command_runner is not None:
            conductor_frame.command_runner = command_runner
        put("FRAME_COMPILED", format=frame.format, record_count=len(compiled_records),
            kinds=_kind_counts(compiled_records), memory_path=os.fspath(memory_path),
            frame_sha256=frame.sha256, write_allowlist=list(frame.write_allowlist or ()),
            machine_criteria=frame.machine_criteria, human_criteria=frame.human_criteria)

        settings: dict[str, dict[str, Any]] = {}
        concurrency, concurrency_source, concurrency_frame = _resolve_setting(frame, "max_concurrency", max_concurrency)
        settings["max_concurrency"] = {"value": concurrency, "source": concurrency_source,
                                       "overridden_frame_value": concurrency_frame}
        real = adapter in ("codex", "claude")
        if real:
            missing = []
            for name, cli_value in (("model", model), ("effort", effort)):
                key = f"{adapter}_{name}"
                value, source, overridden = _resolve_setting(frame, key, cli_value)
                if value is None:
                    missing.append(f"--{name} <value> or '{key}: <value>' under [agent_settings]")
                settings[name] = {"value": value, "source": source, "overridden_frame_value": overridden}
            if missing:
                raise FrameRefusal("AGENT_SETTING_MISSING",
                                   "set " + " and ".join(missing) + "; the entry never picks a model or effort for you",
                                   f"{adapter} needs a model and an effort", source=frame.source)
            _check_git_repo(repo_path)

        planned: list[dict[str, Any]] = []
        runtime: _agent_runtime.AgentRuntime | None = None
        if real:
            def on_plan(plan: Mapping[str, Any]) -> None:
                planned.append(dict(plan))
                put("LAUNCH_PLANNED", adapter=adapter, backend=plan["backend"], argv=list(plan["argv"]),
                    cwd=plan["cwd"], cwd_created=not plan["dry_run"], stdin=dict(plan["stdin"]),
                    prompt=plan["prompt"], allowlist=list(plan["allowlist"]), output_path=plan["output_path"],
                    task_id=plan["task_id"], dry_run=plan["dry_run"], base_commit=plan["base_commit"],
                    model=settings["model"], effort=settings["effort"], max_concurrency=settings["max_concurrency"],
                    effective_concurrency=1)

            runtime = _agent_runtime.AgentRuntime(
                repo_path, frame.write_allowlist or (),
                backend="codex-exec" if adapter == "codex" else "claude-print",
                executable=codex_bin if adapter == "codex" else claude_bin,
                state_dir=run_dir / "runtime", model=settings["model"]["value"],
                effort=settings["effort"]["value"], dry_run=bool(dry_run), on_plan=on_plan)
            inner: AgentAdapter = runtime
        elif isinstance(adapter, str):
            inner = agent_adapter.FakeAdapter()
        else:
            inner = adapter
        wrapped = _LedgerAdapter(inner, ledger, run_id, adapter_name)
        try:
            run = ConductorRun(conductor_frame, wrapped, log_path=run_dir / "driver.jsonl",
                               claimant_id=f"conduct:{adapter_name}")
        except ValueError as exc:
            raise FrameRefusal("FRAME_COMPILE_ERROR",
                               "repair the frame so its ORDER records form a runnable graph with a witnessed authority",
                               str(exc)[:300], source=frame.source) from exc
        result = run.run()
        blocking = dict(result.blocking_item) if result.blocking_item else None
        result_view = {"complete": result.complete, "completed": list(result.completed),
                       "pending": list(result.pending), "interrupted": result.interrupted}
        put("RUN_FINISHED", complete=result.complete, completed=list(result.completed),
            pending=list(result.pending), blocking_kind=(blocking or {}).get("kind"),
            interrupted=result.interrupted, driver_log=os.fspath(run_dir / "driver.jsonl"),
            effective_concurrency=1)
        ledger_path = os.fspath(ledger.path)
        if real and dry_run:
            if not planned:
                raise FrameRefusal(
                    "NO_LAUNCH_PLANNED",
                    "no agent start was reached, so no command was planned; resolve the blocking item "
                    "(see 'blocking') in the frame",
                    f"blocking: {json.dumps(blocking, ensure_ascii=False, default=str)[:300]}", source=frame.source)
            return ConductOutcome("DRY_RUN_PLANNED", 0, None, ledger_path, run_id, blocking, result_view)
        if result.complete:
            return ConductOutcome("RUN_COMPLETE", 0, None, ledger_path, run_id, blocking, result_view)
        return ConductOutcome("RUN_INCOMPLETE", 1, None, ledger_path, run_id, blocking, result_view)
    except FrameRefusal as refusal:
        return refused(refusal)
    except LedgerError as exc:
        return refused(FrameRefusal(
            "LEDGER_UNUSABLE", "make the state directory writable (or pass another --state-dir); "
            "the ledger is the record of what was read and launched, so the run stops without it",
            str(exc), source=os.fspath(state_dir) if state_dir is not None else os.fspath(repo)))
    except Exception as exc:  # the entry never lets an exception escape
        return refused(FrameRefusal(
            "INTERNAL_ERROR", "this is a defect in the conduct entry, not in your frame; report it with the ledger",
            type(exc).__name__), exit_code=3)


__all__ += ["ADAPTER_NAMES", "ConductLedger", "ConductOutcome", "LEDGER_SCHEMA", "LedgerError",
            "conduct_entry"]
