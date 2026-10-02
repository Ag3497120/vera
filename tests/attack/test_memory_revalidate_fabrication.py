import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from verantyx import memory_revalidate


class MemoryDouble:
    def __init__(self, records):
        self.records = list(records)
        self.calls = []

    def active(self, require_fresh=True):
        self.calls.append(require_fresh)
        return list(self.records)


def record(rid, witness, claim="Rin did not sign the form"):
    return {"id": rid, "witness": witness, "claim": claim}


def install_ask(monkeypatch, seen):
    def ask(view, question, require_fresh=True):
        seen.append((question, require_fresh, dict(view.records)))
        return {
            "answer": [item["claim"] for item in view.records.values()],
            "record_ids": list(view.records),
        }

    monkeypatch.setattr(memory_revalidate.Memory, "ask", staticmethod(ask))


def install_ask_about(monkeypatch, seen):
    def ask_about(view, subject, attribute=None, kind="FACT", require_fresh=True):
        seen.append((subject, attribute, kind, require_fresh, dict(view.records)))
        return {
            "answer": [item["claim"] for item in view.records.values()],
            "record_ids": list(view.records),
        }

    monkeypatch.setattr(memory_revalidate.Memory, "ask_about", staticmethod(ask_about))


def test_matching_sha256_record_is_passed_without_claim_rewrite(monkeypatch):
    monkeypatch.setattr(Path, "read_bytes", lambda self: b"Rin did not sign the form")
    witness = {
        "kind": "file_sha256",
        "path": "unused-source",
        "sha256": hashlib.sha256(b"Rin did not sign the form").hexdigest(),
    }
    item = record("r1", witness)
    mem = MemoryDouble([item])
    seen = []
    install_ask(monkeypatch, seen)

    answer = memory_revalidate.RevalidatingMemory(mem).ask("What happened?")

    assert answer["answer"] == ["Rin did not sign the form"]
    assert answer["record_ids"] == ["r1"]
    assert answer["witness_status"] == {"r1": "FRESH"}
    assert seen[0][1] is False
    assert seen[0][2]["r1"] == item
    assert mem.calls == [False]


def test_sha256_mismatch_is_stale_and_cannot_reach_answer(monkeypatch):
    monkeypatch.setattr(Path, "read_bytes", lambda self: b"current source")
    mem = MemoryDouble([record("old", {
        "kind": "file_sha256", "path": "unused-source", "sha256": "wrong",
    })])
    seen = []
    install_ask(monkeypatch, seen)

    answer = memory_revalidate.RevalidatingMemory(mem).ask("What happened?")

    assert answer["answer"] == []
    assert answer["record_ids"] == []
    assert answer["witness_status"] == {"old": "STALE"}
    assert answer["stale"] == ["old"]
    assert seen[0][2] == {}


def test_text_in_file_substring_witness_is_fresh_and_record_is_preserved(monkeypatch):
    monkeypatch.setattr(Path, "read_text", lambda self, *args, **kwargs: "Rin did not sign the form.")
    item = record("text", {
        "kind": "text_in_file", "path": "unused-source", "needle": "did not sign",
    })
    mem = MemoryDouble([item])
    seen = []
    install_ask(monkeypatch, seen)

    answer = memory_revalidate.RevalidatingMemory(mem).ask("Did Rin sign?")

    assert answer["witness_status"] == {"text": "FRESH"}
    assert answer["answer"] == [item["claim"]]
    assert seen[0][2]["text"] == item


def test_unreadable_file_witness_is_stale_and_excluded(monkeypatch):
    def unreadable(self):
        raise OSError("gone")

    monkeypatch.setattr(Path, "read_text", unreadable)
    mem = MemoryDouble([record("gone", {
        "kind": "text_in_file", "path": "unused-source", "needle": "claim",
    })])
    seen = []
    install_ask(monkeypatch, seen)

    answer = memory_revalidate.RevalidatingMemory(mem).ask("Question")

    assert answer["witness_status"] == {"gone": "STALE"}
    assert answer["stale"] == ["gone"]
    assert answer["record_ids"] == []
    assert seen[0][2] == {}


def test_testimony_is_unverifiable_but_remains_answerable(monkeypatch):
    item = record("said", {"kind": "testimony"}, "Rin said the form was unsigned")
    mem = MemoryDouble([item])
    seen = []
    install_ask(monkeypatch, seen)

    answer = memory_revalidate.RevalidatingMemory(mem).ask("What was said?")

    assert answer["witness_status"] == {"said": "UNVERIFIABLE"}
    assert answer["stale"] == []
    assert answer["answer"] == ["Rin said the form was unsigned"]
    assert seen[0][2]["said"] == item


def test_unknown_and_malformed_witnesses_are_unverifiable(monkeypatch):
    items = [
        record("unknown", {"kind": "external_assertion", "id": "x"}),
        record("empty", None),
        record("non_mapping", "testimony"),
    ]
    mem = MemoryDouble(items)
    seen = []
    install_ask(monkeypatch, seen)

    answer = memory_revalidate.RevalidatingMemory(mem).ask("Question")

    assert answer["witness_status"] == {
        "unknown": "UNVERIFIABLE",
        "empty": "UNVERIFIABLE",
        "non_mapping": "UNVERIFIABLE",
    }
    assert answer["stale"] == []
    assert answer["record_ids"] == ["unknown", "empty", "non_mapping"]


def test_git_commit_witness_uses_local_commit_existence_check():
    calls = []

    def runner(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0)

    checker = memory_revalidate.RevalidatingMemory(MemoryDouble([]), runner=runner)
    witness = {"kind": "git_commit", "repo": "unused-repo", "commit": "abc123"}

    assert checker._check(witness) == "FRESH"
    assert calls[0][0] == [
        "git", "-C", "unused-repo", "cat-file", "-e", "abc123^{commit}"
    ]
    assert calls[0][1]["timeout"] == 5
    assert calls[0][1]["stdin"] is memory_revalidate.subprocess.DEVNULL


def test_missing_git_commit_is_stale_and_excluded(monkeypatch):
    def runner(args, **kwargs):
        return SimpleNamespace(returncode=1)

    mem = MemoryDouble([record("missing", {
        "kind": "git_commit", "repo": "unused-repo", "commit": "missing",
    })])
    seen = []
    checker = memory_revalidate.RevalidatingMemory(mem, runner=runner)
    install_ask(monkeypatch, seen)

    answer = checker.ask("Question")

    assert answer["witness_status"] == {"missing": "STALE"}
    assert answer["record_ids"] == []
    assert seen[0][2] == {}


def test_cache_rechecks_after_ttl_and_stale_record_then_disappears(monkeypatch):
    now = [0.0]
    mem = MemoryDouble([record("cached", {"kind": "synthetic"})])
    seen = []
    install_ask(monkeypatch, seen)
    checker = memory_revalidate.RevalidatingMemory(
        mem, cache_ttl=2.0, clock=lambda: now[0]
    )
    checks = []

    def check(witness):
        checks.append(witness)
        return "FRESH" if len(checks) == 1 else "STALE"

    checker._check = check
    first = checker.ask("Question")
    second = checker.ask("Question")
    now[0] = 2.0
    third = checker.ask("Question")

    assert first["record_ids"] == ["cached"]
    assert second["record_ids"] == ["cached"]
    assert third["record_ids"] == []
    assert third["stale"] == ["cached"]
    assert len(checks) == 2


def test_ask_about_filters_stale_and_labels_remaining_records(monkeypatch):
    monkeypatch.setattr(Path, "read_bytes", lambda self: b"fresh")
    items = [
        record("fresh", {
            "kind": "file_sha256", "path": "unused-source",
            "sha256": hashlib.sha256(b"fresh").hexdigest(),
        }, "Mika is the named owner"),
        record("stale", {
            "kind": "file_sha256", "path": "unused-source", "sha256": "old",
        }, "Ari is the named owner"),
    ]
    mem = MemoryDouble(items)
    seen = []
    install_ask_about(monkeypatch, seen)

    answer = memory_revalidate.RevalidatingMemory(mem).ask_about(
        "Mika", "owner", kind="FACT"
    )

    assert answer["answer"] == ["Mika is the named owner"]
    assert answer["record_ids"] == ["fresh"]
    assert answer["witness_status"] == {"fresh": "FRESH", "stale": "STALE"}
    assert seen[0][:4] == ("Mika", "owner", "FACT", False)
    assert seen[0][4].keys() == {"fresh"}


def test_zero_ttl_disables_cache(monkeypatch):
    mem = MemoryDouble([record("uncached", {"kind": "synthetic"})])
    seen = []
    install_ask(monkeypatch, seen)
    checker = memory_revalidate.RevalidatingMemory(mem, cache_ttl=0)
    statuses = iter(["FRESH", "STALE"])
    checks = []

    def check(witness):
        checks.append(witness)
        return next(statuses)

    checker._check = check
    assert checker.ask("Question")["record_ids"] == ["uncached"]
    second = checker.ask("Question")

    assert second["record_ids"] == []
    assert second["witness_status"] == {"uncached": "STALE"}
    assert len(checks) == 2
