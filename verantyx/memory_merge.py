"""Deterministic union and conflict inspection for typed-memory event logs.

Logs contain ``write`` records and ``supersede`` links as emitted by
``memory_frame.Memory``.  A merge is a canonical, duplicate-free union; it
never chooses between active values.  Supersession references may be pending
while partial logs are being combined, but active-state inspection requires
all referenced records to be present.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def _read_events(source: Any) -> list[dict]:
    if isinstance(source, (str, Path)):
        path = Path(source)
        events = []
        for line in path.read_text(encoding='utf-8').splitlines():
            if line.strip():
                event = json.loads(line)
                if not isinstance(event, dict):
                    raise ValueError('each memory event must be a JSON object')
                events.append(event)
        return events
    events = list(source)
    if any(not isinstance(event, Mapping) for event in events):
        raise ValueError('each memory event must be a mapping')
    return [dict(event) for event in events]


def _superseded_ids(value: Any) -> tuple[str, ...]:
    if value is None or value == '':
        return ()
    ids = value if isinstance(value, (list, tuple, set)) else (value,)
    if any(not isinstance(rid, str) or not rid for rid in ids):
        raise ValueError('supersedes references must be non-empty record ids')
    return tuple(sorted(set(ids)))


def _state(events: Iterable[Mapping[str, Any]]):
    """Return records, supersession edges, and canonical input events."""
    records: dict[str, dict] = {}
    aliases: set[str] = set()
    links: set[tuple[str, str]] = set()
    other: set[str] = set()

    for raw in events:
        event = dict(raw)
        op = event.get('op')
        if op == 'write':
            record = event.get('record')
            if not isinstance(record, Mapping):
                raise ValueError('write events must contain a record mapping')
            record = dict(record)
            rid = record.get('id')
            if not isinstance(rid, str) or not rid:
                raise ValueError('written records must have a non-empty string id')
            previous = records.get(rid)
            if previous is not None and _dump(previous) != _dump(record):
                raise ValueError(f'record id collision: {rid}')
            records[rid] = record
            for parent in _superseded_ids(record.get('supersedes')):
                links.add((parent, rid))
        elif op == 'supersede':
            old, new = event.get('id'), event.get('by')
            if not isinstance(old, str) or not old or not isinstance(new, str) or not new:
                raise ValueError('supersede events must name non-empty id and by values')
            links.add((old, new))
        elif op == 'alias':
            aliases.add(_dump(event))
        else:
            other.add(_dump(event))

    # Include supersede operations inferred from record pointers.  Retain
    # original event payloads (including timestamps) when supplied.
    explicit_links = {
        (event.get('id'), event.get('by'))
        for event in events
        if event.get('op') == 'supersede'
    }
    supersede_events = {
        _dump(dict(event))
        for event in events
        if event.get('op') == 'supersede'
    }
    for old, new in sorted(links - explicit_links):
        supersede_events.add(_dump({'op': 'supersede', 'id': old, 'by': new}))

    # A cycle is invalid even if one of its ids has not arrived in this part
    # of a distributed log yet.
    graph: dict[str, set[str]] = {}
    for old, new in links:
        graph.setdefault(old, set()).add(new)
    nodes = set(graph)
    indegree: dict[str, int] = {}
    for old, children in graph.items():
        nodes.update(children)
        indegree.setdefault(old, 0)
        for child in children:
            indegree[child] = indegree.get(child, 0) + 1
    ready = [node for node in nodes if indegree.get(node, 0) == 0]
    visited = 0
    while ready:
        node = ready.pop()
        visited += 1
        for child in graph.get(node, ()):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
    if visited != len(nodes):
        raise ValueError('supersession cycle')

    write_events = [
        {'op': 'write', 'record': records[rid]}
        for rid in sorted(records)
    ]
    canonical = write_events + [
        json.loads(event) for event in sorted(aliases)
    ] + [
        json.loads(event) for event in sorted(supersede_events)
    ] + [
        json.loads(event) for event in sorted(other)
    ]
    return records, links, canonical


def merge_logs(left: Any, right: Any) -> list[dict]:
    """Return a deterministic, commutative union of two JSONL event logs.

    Inputs may be event iterables or paths to JSONL logs. Exact duplicate
    writes and events are removed. A repeated id with different record data,
    or a supersession cycle, is rejected. Links to records in a third partial
    log are retained so that staged three-way merges remain associative.
    """
    _, _, merged = _state(_read_events(left) + _read_events(right))
    return merged


def merge_files(left: Any, right: Any, output: Any) -> list[dict]:
    """Merge two JSONL paths and write the canonical result to ``output``."""
    left_path, right_path, output_path = map(lambda p: Path(p).resolve(), (left, right, output))
    if output_path in (left_path, right_path):
        raise ValueError('output must be separate from both input logs')
    merged = merge_logs(left_path, right_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(''.join(_dump(event) + '\n' for event in merged), encoding='utf-8')
    return merged


def active_records(events: Any) -> list[dict]:
    """Return active records in id order, rejecting incomplete or cyclic links."""
    records, links, _ = _state(_read_events(events))
    for old, new in links:
        if old not in records or new not in records:
            missing = old if old not in records else new
            raise ValueError(f'dangling supersession reference: {missing}')
    retired = {old for old, _ in links}
    return [records[rid] for rid in sorted(records) if rid not in retired]


@dataclass(frozen=True)
class Conflict:
    """Typed disagreement among active values for one subject and attribute."""

    subject: Any
    attribute: Any
    record_ids: tuple[str, ...]
    values: tuple[Any, ...]
    kind: str = 'CONFLICT'

    @property
    def ids(self) -> tuple[str, ...]:
        """Short alias useful to render the evidence ids."""
        return self.record_ids


def _property(record: Mapping[str, Any]):
    slots = record.get('slots')
    slots = slots if isinstance(slots, Mapping) else {}
    subject = slots.get('subject', record.get('subject'))
    attribute = slots.get('attribute', record.get('attribute'))
    value = slots.get('value', record.get('value'))
    if value is None:
        kind_slots = {
            'DECISION': ('決定', 'choice'),
            'INVARIANT': ('規則', 'rule'),
            'TASK': ('状態', 'state'),
            'QUESTION': ('未解決', 'question'),
        }
        mapped = kind_slots.get(record.get('kind'))
        if mapped:
            attribute = attribute or mapped[0]
            value = slots.get(mapped[1], record.get(mapped[1]))
    if subject is None or attribute is None or value is None:
        return None
    return subject, attribute, value


def conflicts(events: Any) -> list[Conflict]:
    """Return typed conflicts for active subject/attribute pairs.

    Every active record supporting a conflicting value is listed by id. Equal
    values are not conflicts; no record is selected or rewritten.
    """
    grouped: dict[str, list[tuple[str, Any, Any, Any]]] = {}
    for record in active_records(events):
        prop = _property(record)
        if prop is None:
            continue
        subject, attribute, value = prop
        key = _dump([subject, attribute])
        grouped.setdefault(key, []).append((record['id'], subject, attribute, value))

    out = []
    for key in sorted(grouped):
        entries = sorted(grouped[key], key=lambda item: item[0])
        distinct = {_dump(item[3]) for item in entries}
        if len(distinct) > 1:
            out.append(Conflict(
                subject=entries[0][1],
                attribute=entries[0][2],
                record_ids=tuple(item[0] for item in entries),
                values=tuple(item[3] for item in entries),
            ))
    return out


__all__ = ['Conflict', 'active_records', 'conflicts', 'merge_files', 'merge_logs']
