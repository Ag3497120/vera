import hashlib
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from verantyx.memory_revalidate import Memory, RevalidatingMemory


class _Memory:
    def __init__(self, records):
        self.records = records

    def active(self, require_fresh=False):
        assert require_fresh is False
        return self.records


def _reader(records=(), **kwargs):
    return RevalidatingMemory(_Memory(list(records)), **kwargs)


def _git(commit="abc"):
    return {"kind": "git_commit", "repo": "/repo", "commit": commit}


def test_empty_and_non_mapping_witnesses_are_unverifiable():
    reader = _reader()
    assert reader._check(None) == "UNVERIFIABLE"
    assert reader._check("") == "UNVERIFIABLE"
    assert reader._check([]) == "UNVERIFIABLE"


def test_testimony_and_unknown_kinds_are_unverifiable_without_runner():
    def fail_runner(*args, **kwargs):
        raise AssertionError("runner must not be called")

    reader = _reader(runner=fail_runner)
    assert reader._check({"kind": "testimony"}) == "UNVERIFIABLE"
    assert reader._check({"kind": "unknown"}) == "UNVERIFIABLE"


def test_file_witnesses_compare_digest_and_text(monkeypatch):
    monkeypatch.setattr("pathlib.Path.read_bytes", lambda self: b"known content")
    monkeypatch.setattr("pathlib.Path.read_text", lambda self: "known content")
    digest = hashlib.sha256(b"known content").hexdigest()
    reader = _reader()

    assert reader._check({"kind": "file_sha256", "path": "/not-read", "sha256": digest}) == "FRESH"
    assert reader._check({"kind": "file_sha256", "path": "/not-read", "sha256": "0" * 64}) == "STALE"
    assert reader._check({"kind": "text_in_file", "path": "/not-read", "needle": "known"}) == "FRESH"
    assert reader._check({"kind": "text_in_file", "path": "/not-read", "needle": "absent"}) == "STALE"


def test_git_check_uses_timeout_and_maps_runner_results():
    calls = []

    def runner(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0 if args[5] == "present^{commit}" else 1)

    reader = _reader(runner=runner)
    assert reader._check(_git("present")) == "FRESH"
    assert reader._check(_git("missing")) == "STALE"
    assert all(call[1]["timeout"] == 5 for call in calls)
    assert all(call[1]["stdin"] == subprocess.DEVNULL for call in calls)


def test_runner_timeout_is_unverifiable():
    def runner(*args, **kwargs):
        assert kwargs["timeout"] == 5
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    assert _reader(runner=runner)._check(_git()) == "UNVERIFIABLE"


def test_cache_reuses_status_until_ttl_expires():
    now = [10.0]
    calls = []

    def runner(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0)

    reader = _reader(runner=runner, cache_ttl=1.0, clock=lambda: now[0])
    witness = _git()
    assert reader._status(witness) == "FRESH"
    assert reader._status(witness) == "FRESH"
    assert len(calls) == 1

    now[0] = 11.0
    assert reader._status(witness) == "FRESH"
    assert len(calls) == 2


@pytest.mark.parametrize("options", [{"cache_size": 0}, {"cache_ttl": 0}])
def test_zero_cache_limits_disable_reuse(options):
    calls = []

    def runner(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0)

    reader = _reader(runner=runner, **options)
    assert reader._status(_git()) == "FRESH"
    assert reader._status(_git()) == "FRESH"
    assert len(calls) == 2
    assert len(reader._cache) == 0


def test_cache_evicts_oldest_entry_and_keeps_bound():
    calls = []

    def runner(args, **kwargs):
        calls.append(args[5])
        return SimpleNamespace(returncode=0)

    reader = _reader(runner=runner, cache_size=2)
    assert reader._status(_git("one")) == "FRESH"
    assert reader._status(_git("two")) == "FRESH"
    assert reader._status(_git("three")) == "FRESH"
    assert len(reader._cache) == 2
    assert reader._status(_git("two")) == "FRESH"
    assert len(calls) == 3
    assert reader._status(_git("one")) == "FRESH"
    assert len(calls) == 4
    assert len(reader._cache) == 2


def test_witness_key_is_independent_of_mapping_order():
    calls = []

    def runner(*args, **kwargs):
        calls.append(args)
        return SimpleNamespace(returncode=0)

    reader = _reader(runner=runner)
    left = {"kind": "git_commit", "repo": "/repo", "commit": "abc"}
    right = {"commit": "abc", "repo": "/repo", "kind": "git_commit"}
    assert reader._status(left) == reader._status(right) == "FRESH"
    assert len(calls) == 1


def test_large_unknown_witness_is_unverifiable_and_cache_entry_count_is_bounded():
    reader = _reader(cache_size=1)
    large = {"kind": "unknown", "payload": "x" * 100_000}
    assert reader._status(large) == "UNVERIFIABLE"
    assert len(reader._cache) == 1
    assert reader._status({"kind": "another-unknown"}) == "UNVERIFIABLE"
    assert len(reader._cache) == 1


def test_ask_filters_stale_records_and_labels_all_statuses(monkeypatch):
    records = [
        {"id": "fresh", "witness": _git("fresh")},
        {"id": "stale", "witness": _git("stale")},
        {"id": "unknown", "witness": {"kind": "testimony"}},
    ]

    def runner(args, **kwargs):
        return SimpleNamespace(returncode=0 if args[5] == "fresh^{commit}" else 1)

    def ask(view, question, require_fresh=False):
        return {"visible_ids": list(view.records)}

    monkeypatch.setattr(Memory, "ask", staticmethod(ask))
    result = _reader(records, runner=runner).ask("question")

    assert result["visible_ids"] == ["fresh", "unknown"]
    assert result["witness_status"] == {
        "fresh": "FRESH",
        "stale": "STALE",
        "unknown": "UNVERIFIABLE",
    }
    assert result["stale"] == ["stale"]


def test_two_concurrent_asks_share_one_cached_validation(monkeypatch):
    calls = []
    calls_lock = threading.Lock()

    def runner(*args, **kwargs):
        with calls_lock:
            calls.append(args)
        time.sleep(0.02)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(
        Memory,
        "ask",
        staticmethod(lambda view, question, require_fresh=False: {"visible_ids": list(view.records)}),
    )
    reader = _reader([{"id": "one", "witness": _git()}], runner=runner)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reader.ask, ["first", "second"]))

    assert [result["visible_ids"] for result in results] == [["one"], ["one"]]
    assert all(result["witness_status"] == {"one": "FRESH"} for result in results)
    assert len(calls) == 1


@pytest.mark.xfail(
    strict=False,
    reason="DEFECT: sorting a witness with mixed key types crashes before returning UNVERIFIABLE",
)
def test_mixed_key_witness_is_unverifiable_instead_of_crashing():
    reader = _reader()
    assert reader._status({0: "bad-key", "kind": "testimony"}) == "UNVERIFIABLE"
