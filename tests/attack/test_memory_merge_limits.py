from concurrent.futures import ThreadPoolExecutor
import gc
import tracemalloc

import pytest

from verantyx.memory_merge import (
    active_records,
    conflicts,
    merge_files,
    merge_logs,
)


def _write(rid, **fields):
    return {"op": "write", "record": {"id": rid, **fields}}


def test_empty_inputs_and_empty_log_are_stable():
    one = _write("one", value="kept")

    assert merge_logs([], []) == []
    assert merge_logs([], [one]) == [{"op": "write", "record": {"id": "one", "value": "kept"}}]
    assert merge_logs([], []) == []


def test_merge_is_commutative_and_canonical_for_mixed_events():
    left = [
        _write("z"),
        {"op": "alias", "name": "second", "target": "z"},
        {"op": "supersede", "id": "old", "by": "z", "at": 7},
    ]
    right = [
        _write("a"),
        {"op": "alias", "name": "first", "target": "a"},
        {"op": "note", "text": "kept"},
    ]

    assert merge_logs(left, right) == merge_logs(right, left)


def test_exact_duplicates_are_removed_idempotently():
    event = _write("same", value={"x": 1})
    alias = {"op": "alias", "name": "n", "target": "same"}

    assert merge_logs([event, event, alias], [event, alias]) == [event, alias]


def test_staged_merge_with_pending_supersession_is_associative():
    link = [{"op": "supersede", "id": "old", "by": "new"}]
    old = [_write("old", value="before")]
    new = [_write("new", value="after")]

    direct = merge_logs(link, merge_logs(old, new))
    staged = merge_logs(merge_logs(link, old), new)
    assert staged == direct


def test_different_records_with_same_id_are_rejected():
    with pytest.raises(ValueError, match="record id collision"):
        merge_logs([_write("same", value="left")], [_write("same", value="right")])


def test_partial_supersession_cycle_is_rejected():
    cycle = [
        {"op": "supersede", "id": "a", "by": "b"},
        {"op": "supersede", "id": "b", "by": "a"},
    ]

    with pytest.raises(ValueError, match="supersession cycle"):
        merge_logs(cycle, [])


def test_active_records_reject_dangling_supersession_reference():
    partial = [_write("new", value="after"), {"op": "supersede", "id": "missing", "by": "new"}]

    with pytest.raises(ValueError, match="dangling supersession reference: missing"):
        active_records(partial)


def test_conflicts_preserve_all_active_evidence_in_id_order():
    records = [
        _write("r3", slots={"subject": "router", "attribute": "mode", "value": "safe"}),
        _write("r1", slots={"subject": "router", "attribute": "mode", "value": "fast"}),
        _write("r2", slots={"subject": "router", "attribute": "mode", "value": "safe"}),
    ]

    result = conflicts(records)
    assert len(result) == 1
    assert result[0].kind == "CONFLICT"
    assert result[0].subject == "router"
    assert result[0].attribute == "mode"
    assert result[0].record_ids == ("r1", "r2", "r3")
    assert result[0].values == ("fast", "safe", "safe")


def test_large_duplicate_input_returns_one_sorted_record_per_id():
    records = [_write(f"r{i:05d}", value=i) for i in range(4000)]

    merged = merge_logs(iter(records), iter(reversed(records)))
    ids = [event["record"]["id"] for event in merged]
    assert len(merged) == 4000
    assert ids == sorted(ids)
    assert ids[0] == "r00000"
    assert ids[-1] == "r03999"


def test_two_concurrent_readers_return_identical_results():
    events = tuple(_write(f"r{i:04d}", value=i) for i in range(500))
    expected = merge_logs(events[:250], events[250:])

    def read_twenty_times():
        return [merge_logs(events[:250], events[250:]) for _ in range(20)]

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: read_twenty_times(), range(2)))

    assert all(result == expected for reader in results for result in reader)
    assert len(events) == 500


def test_repeated_merges_do_not_retain_unbounded_temporary_state():
    events = [_write(f"r{i:04d}", value=i) for i in range(300)]
    merge_logs(events, [])
    gc.collect()
    tracemalloc.start()
    try:
        baseline, _ = tracemalloc.get_traced_memory()
        for _ in range(30):
            merge_logs(events, [])
        gc.collect()
        retained, _ = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert retained - baseline < 512 * 1024


def test_merge_files_round_trips_and_rejects_overwriting_input(tmp_path):
    left = tmp_path / "left.jsonl"
    right = tmp_path / "right.jsonl"
    output = tmp_path / "merged.jsonl"
    left.write_text('{"op":"write","record":{"id":"b"}}\n', encoding="utf-8")
    right.write_text('{"op":"write","record":{"id":"a"}}\n', encoding="utf-8")

    merged = merge_files(left, right, output)
    assert [record["id"] for record in active_records(output)] == ["a", "b"]
    assert merged == merge_logs(left, right)
    with pytest.raises(ValueError, match="output must be separate"):
        merge_files(left, right, left)

