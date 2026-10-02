import hashlib
import subprocess
from pathlib import Path
from types import SimpleNamespace

from verantyx.memory_revalidate import Memory, RevalidatingMemory


def _never_run(*args, **kwargs):
    raise AssertionError("unexpected git witness check")


def _checker(*, runner=_never_run, cache_ttl=0, cache_size=0, clock=lambda: 0.0):
    return RevalidatingMemory(
        memory=None, runner=runner, cache_ttl=cache_ttl,
        cache_size=cache_size, clock=clock,
    )


def test_empty_and_non_mapping_witnesses_are_unverifiable():
    checker = _checker()

    assert checker._check(None) == "UNVERIFIABLE"
    assert checker._check({}) == "UNVERIFIABLE"
    assert checker._check([]) == "UNVERIFIABLE"


def test_testimony_witness_is_unverifiable_without_runner_call():
    checker = _checker()

    assert checker._check({"kind": "testimony", "speaker": "person"}) == "UNVERIFIABLE"


def test_unknown_witness_kind_is_unverifiable():
    checker = _checker()

    assert checker._check({"kind": "generated"}) == "UNVERIFIABLE"


def test_matching_file_sha256_witness_is_fresh():
    path = Path(__file__)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()

    assert _checker()._check({"kind": "file_sha256", "path": str(path), "sha256": digest}) == "FRESH"


def test_mismatching_file_sha256_witness_is_stale():
    path = Path(__file__)

    assert _checker()._check({
        "kind": "file_sha256", "path": str(path), "sha256": "not-the-file-digest",
    }) == "STALE"


def test_text_in_file_witness_matches_literal_source_text():
    path = Path(__file__)

    assert _checker()._check({
        "kind": "text_in_file", "path": str(path),
        "needle": "test_text_in_file_witness_matches_literal_source_text",
    }) == "FRESH"


def test_missing_file_witness_is_stale():
    missing = Path(__file__).with_name("no-such-memory-witness-file")

    assert _checker()._check({
        "kind": "text_in_file", "path": str(missing), "needle": "anything",
    }) == "STALE"


def test_git_commit_witness_uses_local_cat_file_and_reports_fresh():
    calls = []

    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0)

    checker = _checker(runner=runner)

    assert checker._check({"kind": "git_commit", "repo": "/repo", "commit": "abc123"}) == "FRESH"
    assert calls == [(
        ["git", "-C", "/repo", "cat-file", "-e", "abc123^{commit}"],
        {"capture_output": True, "text": True, "timeout": 5, "stdin": subprocess.DEVNULL},
    )]


def test_missing_git_commit_is_stale():
    checker = _checker(runner=lambda *args, **kwargs: SimpleNamespace(returncode=1))

    assert checker._check({"kind": "git_commit", "repo": "/repo", "commit": "missing"}) == "STALE"


def test_git_timeout_is_unverifiable():
    def runner(*args, **kwargs):
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    checker = _checker(runner=runner)

    assert checker._check({"kind": "git_commit", "repo": "/repo", "commit": "abc123"}) == "UNVERIFIABLE"


def test_status_cache_reuses_then_rechecks_after_ttl():
    now = [0.0]
    results = iter([SimpleNamespace(returncode=0), SimpleNamespace(returncode=1)])
    calls = []

    def runner(*args, **kwargs):
        calls.append(args[0])
        return next(results)

    checker = _checker(runner=runner, cache_ttl=1.0, cache_size=2, clock=lambda: now[0])
    witness = {"kind": "git_commit", "repo": "/repo", "commit": "abc123"}

    assert checker._status(witness) == "FRESH"
    now[0] = 0.5
    assert checker._status(witness) == "FRESH"
    assert len(calls) == 1
    now[0] = 1.5
    assert checker._status(witness) == "STALE"
    assert len(calls) == 2


def test_zero_ttl_disables_status_cache():
    results = iter([SimpleNamespace(returncode=0), SimpleNamespace(returncode=1)])
    calls = []

    def runner(*args, **kwargs):
        calls.append(args[0])
        return next(results)

    checker = _checker(runner=runner, cache_ttl=0, cache_size=2)
    witness = {"kind": "git_commit", "repo": "/repo", "commit": "abc123"}

    assert checker._status(witness) == "FRESH"
    assert checker._status(witness) == "STALE"
    assert len(calls) == 2


class _MemoryStub:
    def __init__(self, records):
        self.records = records

    def active(self, *, require_fresh):
        assert require_fresh is False
        return list(self.records)


def test_ask_omits_stale_records_and_labels_witness_status(monkeypatch):
    path = Path(__file__)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    memory = _MemoryStub([
        {"id": "fresh", "witness": {"kind": "file_sha256", "path": str(path), "sha256": digest}},
        {"id": "stale", "witness": {"kind": "file_sha256", "path": str(path), "sha256": "wrong"}},
        {"id": "testimony", "witness": {"kind": "testimony"}},
    ])
    observed = {}

    def ask(view, question, require_fresh=True):
        observed["ids"] = set(view.records)
        observed["question"] = question
        observed["require_fresh"] = require_fresh
        return {"answer": "stubbed"}

    monkeypatch.setattr(Memory, "ask", staticmethod(ask))
    answer = RevalidatingMemory(memory).ask("question", require_fresh=True)

    assert observed == {
        "ids": {"fresh", "testimony"}, "question": "question", "require_fresh": False,
    }
    assert answer == {
        "answer": "stubbed",
        "witness_status": {"fresh": "FRESH", "stale": "STALE", "testimony": "UNVERIFIABLE"},
        "stale": ["stale"],
    }


def test_ask_about_labels_testimony_as_unverifiable(monkeypatch):
    memory = _MemoryStub([{"id": "t1", "witness": {"kind": "testimony"}}])
    observed = {}

    def ask_about(view, subject, attribute=None, kind="FACT", require_fresh=True):
        observed["ids"] = set(view.records)
        observed["args"] = (subject, attribute, kind, require_fresh)
        return {"answer": "stubbed"}

    monkeypatch.setattr(Memory, "ask_about", staticmethod(ask_about))
    answer = RevalidatingMemory(memory).ask_about("subject", "name", kind="FACT")

    assert observed == {"ids": {"t1"}, "args": ("subject", "name", "FACT", False)}
    assert answer["witness_status"] == {"t1": "UNVERIFIABLE"}
    assert answer["stale"] == []


def test_circular_witness_should_be_unverifiable_on_repeated_checks():
    checker = _checker()
    witness = {}
    witness["self"] = witness
    errors = []

    for _ in range(2):
        try:
            status = checker._status(witness)
        except Exception as exc:
            errors.append(type(exc).__name__)
        else:
            assert status == "UNVERIFIABLE"

    assert errors == [], f"repeated status checks raised {errors}"
