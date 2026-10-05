"""W16-t6: attestation rows in the testimony ledger (kind: attestation) and the reading of an (assumed shape) T7 events ledger."""
import hashlib
import json

import pytest

from verantyx import attest, testimony_ledger
from verantyx.attest import MISMATCH, RECORD, TESTIMONY, Verifier
from verantyx.testimony_ledger import LedgerError, TestimonyLedger


def _row(kind, data, prev):
    r = {"ts": "t", "kind": kind, "actor": "x", "data": data, "prev": prev}
    r["sha"] = hashlib.sha256(json.dumps(r, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    return r


def chain(events):
    rows, prev = [], None
    for k, d in events:
        rows.append(_row(k, d, prev))
        prev = rows[-1]["sha"]
    return rows


def write(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


RES = {"attest_id": "a1", "claim_id": "V-1", "extractor": "V", "mark": "MISMATCH", "reason": "SHA_DIFFERS", "report": {"path": "r.md", "sha256": "0" * 64},
       "tree": {"path": "/t", "head": None}, "flags": {}, "facts": [{"fact": "file_sha:a", "mark": "MISMATCH", "reason": "SHA_DIFFERS", "claimed": "x", "actual": "y", "observation": "z" * 900}]}


def _seed(led):
    led.record_assumption({"word": "ねこ", "kind": "noun_type", "assumed": "ANIMAL", "source": "llm", "sentence_sha256": "s1", "doc_id": "d"})


def test_record_attestation_chains_and_does_not_disturb_the_fold(tmp_path):
    led = TestimonyLedger(tmp_path / "l.jsonl")
    _seed(led)
    before = (json.dumps(led.fold(), sort_keys=True, default=str), led.listing(), led.promotion_plan("L"))
    row = led.record_attestation(RES)
    assert row["type"] == "attestation" and row["kind"] == "attestation" and "fill_id" not in row and "key" not in row and "word" not in row
    assert len(row["facts"][0]["observation"]) == 300
    led.verify()
    assert TestimonyLedger(tmp_path / "l.jsonl").verify()
    after = (json.dumps(led.fold(), sort_keys=True, default=str), led.listing(), led.promotion_plan("L"))
    assert before == after
    assert led.show("V-1") is None


def test_row_types_are_unchanged_and_attestation_is_separate():
    assert testimony_ledger.ROW_TYPES[-1] == "assumption" and "attestation" not in testimony_ledger.ROW_TYPES
    assert testimony_ledger.ATTESTATION_ROW_TYPES == ("attestation",)


def test_llm_judge_answers_and_bad_marks_are_refused(tmp_path):
    led = TestimonyLedger(tmp_path / "l.jsonl")
    with pytest.raises(LedgerError):
        led.record_attestation(dict(RES, extractor="c"))
    with pytest.raises(LedgerError):
        led.record_attestation(dict(RES, mark="LLM_YES"))
    assert [e["type"] for e in led.entries()] == ["header"]


def test_events_ledger_valid_tampered_and_split(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "a.py").write_text("def test_a():\n    assert True\n")
    (tmp_path / "pytest.ini").write_text("")
    good = chain([("note", {"t": 1}), ("test_run", {"cmd": "python -m x run", "exit_code": 3}), ("process_exit", {"argv": ["pytest", "-q", "tests/a.py"], "returncode": 0})])
    p = tmp_path / "ev.jsonl"
    write(p, good)
    v = Verifier(str(tmp_path), ledger=str(p))
    f = v.exit_fact("python -m x run", 3)
    assert (f["mark"], f["reason"], f["actual"]) == (RECORD, "MATCH", 3)
    f = v.exit_fact("python -m x run", 0)
    assert (f["mark"], f["reason"], f["claimed"], f["actual"]) == (MISMATCH, "EXIT_CODE_DIFFERS", 0, 3)
    assert v.exit_fact("python -m other", 0)["reason"] == "NO_EVENT"
    # a rewritten row: the whole ledger is unverified
    bad = [dict(r) for r in good]
    bad[1] = dict(bad[1], data={"cmd": "python -m x run", "exit_code": 0})
    write(p, bad)
    f = Verifier(str(tmp_path), ledger=str(p)).exit_fact("python -m x run", 0)
    assert (f["mark"], f["reason"]) == (TESTIMONY, "LEDGER_UNVERIFIED")
    # a cut-in row (prev does not chain)
    write(p, [good[0], good[2]])
    assert Verifier(str(tmp_path), ledger=str(p)).exit_fact("python -m x run", 3)["reason"] == "LEDGER_UNVERIFIED"
    # the same command with two exit codes: a tie is not decided
    split = chain([("test_run", {"cmd": "python -m x run", "exit_code": 0}), ("test_run", {"cmd": "python -m x run", "exit_code": 1})])
    write(p, split)
    f = Verifier(str(tmp_path), ledger=str(p)).exit_fact("python -m x run", 0)
    assert (f["mark"], f["reason"]) == (TESTIMONY, "AMBIGUOUS_EVENT")
    # the unreadable ledger
    p.write_text("not json\n")
    assert Verifier(str(tmp_path), ledger=str(p)).exit_fact("python -m x run", 0)["reason"] == "LEDGER_UNVERIFIED"


def test_ledger_event_beats_rerun_and_unverified_falls_back_to_rerun(tmp_path, monkeypatch):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "a.py").write_text("def test_a():\n    assert True\n")
    p = tmp_path / "ev.jsonl"
    write(p, chain([("test_run", {"cmd": "pytest -q tests/a.py", "exit_code": 1})]))
    calls = []
    monkeypatch.setattr(attest, "_spawn", lambda *a, **k: (calls.append(a) or (0, b"", b"")))
    f = Verifier(str(tmp_path), ledger=str(p), rerun=True).exit_fact("pytest -q tests/a.py", 1)
    assert f["mark"] == RECORD and calls == []
    p.write_text("garbage\n")
    f = Verifier(str(tmp_path), ledger=str(p), rerun=True).exit_fact("pytest -q tests/a.py", 0)
    assert f["mark"] == RECORD and len(calls) == 1
