"""Differential checks for deterministic typed-memory log merging."""

from collections.abc import Mapping
import json
import random

import pytest

from verantyx.memory_merge import active_records, conflicts, merge_files, merge_logs


def _wire(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _reference_ids(value):
    if value is None or value == "":
        return ()
    supplied = value if isinstance(value, (list, tuple, set)) else (value,)
    if any(not isinstance(item, str) or not item for item in supplied):
        raise ValueError("bad supersession reference")
    return tuple(sorted(set(supplied)))


def _reference_merge(left, right):
    """Small, deliberately direct implementation of the documented union."""
    records = {}
    edges = set()
    aliases = set()
    supplied_supersedes = set()
    explicit_pairs = set()
    other = set()

    for event in [dict(item) for item in left] + [dict(item) for item in right]:
        operation = event.get("op")
        if operation == "write":
            record = event.get("record")
            if not isinstance(record, Mapping):
                raise ValueError("bad write")
            record = dict(record)
            record_id = record.get("id")
            if not isinstance(record_id, str) or not record_id:
                raise ValueError("bad record id")
            previous = records.get(record_id)
            if previous is not None and _wire(previous) != _wire(record):
                raise ValueError("record id collision")
            records[record_id] = record
            edges.update((old, record_id) for old in _reference_ids(record.get("supersedes")))
        elif operation == "supersede":
            old, new = event.get("id"), event.get("by")
            if not isinstance(old, str) or not old or not isinstance(new, str) or not new:
                raise ValueError("bad supersede event")
            edges.add((old, new))
            explicit_pairs.add((old, new))
            supplied_supersedes.add(_wire(event))
        elif operation == "alias":
            aliases.add(_wire(event))
        else:
            other.add(_wire(event))

    children = {}
    for old, new in edges:
        children.setdefault(old, set()).add(new)
    visiting, visited = set(), set()

    def visit(node):
        if node in visiting:
            raise ValueError("supersession cycle")
        if node in visited:
            return
        visiting.add(node)
        for child in children.get(node, ()):
            visit(child)
        visiting.remove(node)
        visited.add(node)

    for node in set(children).union(*(set(values) for values in children.values())):
        visit(node)

    for old, new in edges - explicit_pairs:
        supplied_supersedes.add(_wire({"op": "supersede", "id": old, "by": new}))
    return (
        [{"op": "write", "record": records[key]} for key in sorted(records)]
        + [json.loads(item) for item in sorted(aliases)]
        + [json.loads(item) for item in sorted(supplied_supersedes)]
        + [json.loads(item) for item in sorted(other)]
    )


def _reference_active(events):
    merged = _reference_merge(events, [])
    records = {event["record"]["id"]: event["record"] for event in merged if event.get("op") == "write"}
    edges = {
        (event["id"], event["by"])
        for event in merged
        if event.get("op") == "supersede"
    }
    for old, new in edges:
        if old not in records or new not in records:
            raise ValueError("dangling supersession reference")
    retired = {old for old, _ in edges}
    return [records[key] for key in sorted(records) if key not in retired]


def _reference_property(record):
    slots = record.get("slots")
    slots = slots if isinstance(slots, Mapping) else {}
    subject = slots.get("subject", record.get("subject"))
    attribute = slots.get("attribute", record.get("attribute"))
    value = slots.get("value", record.get("value"))
    if value is None:
        mapped = {
            "DECISION": ("決定", "choice"),
            "INVARIANT": ("規則", "rule"),
            "TASK": ("状態", "state"),
            "QUESTION": ("未解決", "question"),
        }.get(record.get("kind"))
        if mapped:
            attribute = attribute or mapped[0]
            value = slots.get(mapped[1], record.get(mapped[1]))
    return None if subject is None or attribute is None or value is None else (subject, attribute, value)


def _reference_conflicts(events):
    groups = {}
    for record in _reference_active(events):
        prop = _reference_property(record)
        if prop is None:
            continue
        subject, attribute, value = prop
        groups.setdefault(_wire([subject, attribute]), []).append((record["id"], subject, attribute, value))
    result = []
    for key in sorted(groups):
        entries = sorted(groups[key], key=lambda item: item[0])
        if len({_wire(item[3]) for item in entries}) > 1:
            result.append((entries[0][1], entries[0][2], tuple(item[0] for item in entries), tuple(item[3] for item in entries)))
    return result


def _record(record_id, subject="p", attribute="color", value="blue", **extra):
    return {"id": record_id, "subject": subject, "attribute": attribute, "value": value, **extra}


def test_generated_unions_match_independent_reference():
    rng = random.Random(20261002)
    for case in range(64):
        events = []
        for index in range(rng.randint(1, 7)):
            record = _record(
                f"r{case}-{index}",
                subject=f"s{rng.randrange(3)}",
                attribute=f"a{rng.randrange(2)}",
                value=rng.choice(["red", "blue", 0, False]),
            )
            events.append({"op": "write", "record": record})
            if rng.randrange(3) == 0:
                events.append({"op": "write", "record": dict(record)})
        events.extend([
            {"op": "alias", "name": f"alias-{case % 4}", "target": f"r{case}-0"},
            {"op": "note", "text": f"case-{case}"},
        ])
        cut = rng.randrange(len(events) + 1)
        left, right = events[:cut], events[cut:]
        assert merge_logs(left, right) == _reference_merge(left, right)


def test_merge_is_commutative_idempotent_and_associative_with_pending_links():
    first = [{"op": "write", "record": _record("new", supersedes=["old"])}]
    second = [{"op": "write", "record": _record("old", value="green")}]
    third = [{"op": "alias", "name": "n", "target": "new"}]
    assert merge_logs(first, second) == merge_logs(second, first)
    assert merge_logs(first, first) == merge_logs(first, [])
    assert merge_logs(merge_logs(first, second), third) == merge_logs(first, merge_logs(second, third))


def test_canonical_order_and_exact_duplicate_removal():
    events = [
        {"op": "note", "z": 1},
        {"op": "alias", "target": "b", "name": "z"},
        {"op": "write", "record": _record("z")},
        {"op": "supersede", "id": "a", "by": "z", "at": 5},
        {"op": "write", "record": _record("a")},
        {"op": "alias", "name": "z", "target": "b"},
        {"op": "note", "z": 1},
    ]
    assert merge_logs(events, []) == [
        {"op": "write", "record": _record("a")},
        {"op": "write", "record": _record("z")},
        {"op": "alias", "name": "z", "target": "b"},
        {"op": "supersede", "id": "a", "by": "z", "at": 5},
        {"op": "note", "z": 1},
    ]


def test_record_supersedes_are_materialized_and_pending_until_complete():
    partial = [{"op": "write", "record": _record("new", supersedes="old")}]
    assert merge_logs(partial, []) == partial + [{"op": "supersede", "id": "old", "by": "new"}]
    with pytest.raises(ValueError, match="dangling supersession"):
        active_records(partial)
    complete = merge_logs(partial, [{"op": "write", "record": _record("old")}])
    assert [record["id"] for record in active_records(complete)] == ["new"]


def test_duplicate_record_ids_require_identical_record_data():
    same_a = {"op": "write", "record": {"id": "x", "value": "v", "subject": "p"}}
    same_b = {"op": "write", "record": {"subject": "p", "id": "x", "value": "v"}}
    assert merge_logs([same_a], [same_b]) == [same_a]
    changed = {"op": "write", "record": _record("x", value="different")}
    with pytest.raises(ValueError, match="record id collision"):
        merge_logs([same_a], [changed])


def test_explicit_and_inferred_cycles_are_rejected():
    explicit = [
        {"op": "supersede", "id": "a", "by": "b"},
        {"op": "supersede", "id": "b", "by": "a"},
    ]
    inferred = [
        {"op": "write", "record": _record("a", supersedes="b")},
        {"op": "write", "record": _record("b", supersedes="a")},
    ]
    for events in (explicit, inferred):
        with pytest.raises(ValueError, match="supersession cycle"):
            merge_logs(events, [])


def test_conflicts_match_reference_and_include_every_supporting_active_record():
    events = [
        {"op": "write", "record": _record("r1", value="red")},
        {"op": "write", "record": _record("r2", value="blue")},
        {"op": "write", "record": _record("r3", value="blue")},
        {"op": "write", "record": {"id": "r4", "kind": "DECISION", "subject": "p", "attribute": "color", "choice": "blue"}},
        {"op": "write", "record": _record("r5", subject="q", value="red")},
        {"op": "write", "record": _record("r6", subject="q", value="red")},
        {"op": "supersede", "id": "r5", "by": "r6"},
    ]
    expected = _reference_conflicts(events)
    observed = [(item.subject, item.attribute, item.record_ids, item.values) for item in conflicts(events)]
    assert observed == expected
    assert observed == [("p", "color", ("r1", "r2", "r3", "r4"), ("red", "blue", "blue", "blue"))]


def test_generated_conflict_sets_match_naive_active_record_scan():
    rng = random.Random(88421)
    for case in range(48):
        events = []
        count = rng.randint(2, 8)
        for index in range(count):
            events.append({
                "op": "write",
                "record": _record(
                    f"c{case}-{index}",
                    subject=f"subject-{rng.randrange(3)}",
                    attribute=f"attribute-{rng.randrange(2)}",
                    value=rng.choice(["x", "y", "z"]),
                ),
            })
        assert [(item.subject, item.attribute, item.record_ids, item.values) for item in conflicts(events)] == _reference_conflicts(events)


def test_bad_event_and_bad_supersession_references_are_rejected():
    with pytest.raises(ValueError, match="each memory event"):
        merge_logs(["not a mapping"], [])
    with pytest.raises(ValueError, match="non-empty string id"):
        merge_logs([{"op": "write", "record": {"id": ""}}], [])
    with pytest.raises(ValueError, match="supersedes references"):
        merge_logs([{"op": "write", "record": _record("x", supersedes=[""])}], [])


def test_jsonl_file_merge_writes_the_same_canonical_union(tmp_path):
    left = tmp_path / "left.jsonl"
    right = tmp_path / "right.jsonl"
    output = tmp_path / "merged.jsonl"
    left.write_text('{"op":"write","record":{"id":"b","value":"2"}}\n', encoding="utf-8")
    right.write_text('{"op":"write","record":{"id":"a","value":"1"}}\n', encoding="utf-8")
    expected = _reference_merge(
        [{"op": "write", "record": {"id": "b", "value": "2"}}],
        [{"op": "write", "record": {"id": "a", "value": "1"}}],
    )
    assert merge_files(left, right, output) == expected
    assert [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()] == expected
