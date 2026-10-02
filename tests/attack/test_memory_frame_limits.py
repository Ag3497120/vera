import concurrent.futures
import itertools
import json
import re
import tempfile
from pathlib import Path

import pytest

from verantyx.memory_frame import Memory, Resolver, WriteRejected


@pytest.fixture
def memory_path():
    with tempfile.TemporaryDirectory(prefix=".memory-frame-", dir=Path.cwd()) as directory:
        yield Path(directory) / "memory.jsonl"


def _clock():
    ticks = itertools.count()
    return lambda: f"2025-01-01T00:00:{next(ticks):02d}"


def _write_fact(memory, value="50件", witness=None, **kwargs):
    return memory.write(
        "FACT",
        "attacker",
        witness=witness or {"kind": "testimony"},
        subject="ルーター",
        attribute="未読上限",
        value=value,
        **kwargs,
    )


def test_empty_memory_returns_unknown_without_mutating_log(memory_path):
    memory = Memory(str(memory_path))

    first = memory.ask("ルーターの未読上限は？")
    second = memory.ask("ルーターの未読上限は？")

    assert first == {"verdict": "UNKNOWN_NO_EVIDENCE", "values": [], "records": []}
    assert second == first
    assert not memory_path.exists()


def test_missing_required_slot_is_a_typed_rejection_without_a_log(memory_path):
    memory = Memory(str(memory_path))

    with pytest.raises(WriteRejected):
        memory.write("FACT", "attacker", witness={"kind": "testimony"}, subject="ルーター")

    assert not memory_path.exists()


def test_very_large_unknown_kind_is_rejected_without_resolver_or_crash(memory_path):
    memory = Memory(str(memory_path))

    with pytest.raises(WriteRejected):
        memory.write("x" * 100_000, "attacker", subject="ルーター", attribute="上限", value="50件")

    assert not memory_path.exists()


def test_stale_file_witness_is_visible_but_excluded_when_freshness_is_required(memory_path):
    memory = Memory(str(memory_path), now=_clock())
    missing = memory_path.parent / "missing-witness.txt"
    _write_fact(memory, witness={"kind": "file_sha256", "path": str(missing), "sha256": "0" * 64})

    assert len(memory.active(require_fresh=False)) == 1
    assert memory.active(require_fresh=True) == []
    assert list(memory.verify().values()) == ["STALE"]


def test_write_survives_reopen_and_repeated_reads_do_not_change_the_log(memory_path):
    memory = Memory(str(memory_path), now=_clock())
    record = _write_fact(memory)
    before = memory_path.read_bytes()

    reopened = Memory(str(memory_path))
    for _ in range(10):
        assert reopened.active()[0]["id"] == record["id"]
        assert reopened.verify()[record["id"]] == "TESTIMONY"

    assert memory_path.read_bytes() == before


def test_closed_choice_resolution_is_independent_of_option_order_and_repeated_calls():
    def choose_completion(prompt):
        for index, option in re.findall(r"^(\d+): (.+)$", prompt, re.MULTILINE):
            if option == "完了":
                return json.dumps({"choice": int(index)})
        return '{"choice": null}'

    resolver = Resolver(choose_completion, seed=11)
    left = resolver.resolve("終わった", ["未着手", "進行中", "完了"])
    right = resolver.resolve("終わった", ["完了", "進行中", "未着手"])

    assert left["status"] == "ADOPT" and left["choice"] == "完了"
    assert right["status"] == "ADOPT" and right["choice"] == "完了"
    assert len(left["asks"]) == len(right["asks"]) == 2


def test_resolver_treats_empty_choice_and_invalid_replies_as_closed_outcomes():
    none = Resolver(lambda _prompt: '{"choice": null}').resolve("未知語", [])
    replies = iter(("not json", '{"choice": 3}'))
    invalid = Resolver(lambda _prompt: next(replies)).resolve("未知語", ["a", "b"])

    assert none["status"] == "NONE"
    assert invalid["status"] == "UNRESOLVED"
    assert invalid["choice"] is None


def test_large_closed_choice_list_with_null_answers_finishes_as_none():
    options = [f"候補{i}" for i in range(750)]
    result = Resolver(lambda _prompt: '{"choice": null}').resolve("候補外", options)

    assert result["status"] == "NONE"
    assert result["choice"] is None
    assert len(result["asks"]) == 2


def test_two_independent_readers_return_the_same_snapshot_concurrently(memory_path):
    writer = Memory(str(memory_path), now=_clock())
    _write_fact(writer)
    readers = (Memory(str(memory_path)), Memory(str(memory_path)))

    def snapshot(memory):
        return tuple(r["id"] for r in memory.active()), tuple(sorted(memory.verify().items()))

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(snapshot, reader) for reader in readers]
        snapshots = [future.result(timeout=5) for future in futures]

    assert snapshots[0] == snapshots[1]


def test_valid_supersession_keeps_only_the_new_record_active(memory_path):
    memory = Memory(str(memory_path), now=_clock())
    old = _write_fact(memory, value="50件")
    new = _write_fact(memory, value="60件", supersedes=old["id"])

    assert [record["id"] for record in memory.active()] == [new["id"]]
    assert old["id"] in memory.superseded


@pytest.mark.xfail(strict=False, reason="DEFECT: malformed witness fields can escape the write gate and crash verification")
def test_incomplete_file_witness_is_reported_as_unverifiable_instead_of_crashing(memory_path):
    memory = Memory(str(memory_path), now=_clock())

    record = _write_fact(memory, witness={"kind": "file_sha256"})

    assert memory.verify()[record["id"]] == "UNVERIFIABLE"


@pytest.mark.xfail(strict=False, reason="DEFECT: missing supersession target is checked after the new record is appended")
def test_missing_supersession_target_does_not_partially_append(memory_path):
    memory = Memory(str(memory_path), now=_clock())
    original = _write_fact(memory)
    before = memory_path.read_bytes()

    with pytest.raises(WriteRejected):
        _write_fact(memory, value="60件", supersedes="missing-record")

    assert memory_path.read_bytes() == before
    assert [record["id"] for record in memory.active()] == [original["id"]]


@pytest.mark.xfail(strict=False, reason="DEFECT: identical same-timestamp writes append duplicate JSONL events")
def test_identical_write_is_idempotent_and_does_not_grow_the_log(memory_path):
    memory = Memory(str(memory_path), now=lambda: "2025-01-01T00:00:00")
    _write_fact(memory)
    once = memory_path.read_bytes()

    _write_fact(memory)

    assert memory_path.read_bytes() == once
