"""W16-t6b round 2: regression tests for the three fail-closed branches of attest.check_ledger
(a verifier fault, a ledger changed while it was verified, bytes that are not UTF-8): none of them may yield events."""
from pathlib import Path

from verantyx import attest, ledger_events as LE

ACT = {"type": "agent", "id": "t"}


def _ledger(tmp_path):
    d = tmp_path / "led"
    LE.append(d, "test_run", ACT, {"cmd": "python -m x run", "exit_code": 0})
    return d, d / "events.jsonl"


def _types(check):
    return {p["type"] for p in check["problems"]}


def test_changed_during_verify(tmp_path, monkeypatch):
    d, ev = _ledger(tmp_path)
    real = LE.verify

    def evil(dd, **kw):
        r = real(dd, **kw)
        ev.write_bytes(ev.read_bytes() + b"\n")        # same T7 verdict, different bytes
        return r

    monkeypatch.setattr(LE, "verify", evil)
    events, check, raw = attest.check_ledger(str(ev))
    assert events is None and raw is None and "LEDGER_CHANGED_DURING_VERIFY" in _types(check)


def test_verify_fault_is_not_a_verification(tmp_path, monkeypatch):
    d, ev = _ledger(tmp_path)

    def boom(*a, **kw):
        raise RuntimeError("x")

    monkeypatch.setattr(LE, "verify", boom)
    events, check, raw = attest.check_ledger(str(ev))
    assert events is None and raw is None and "LEDGER_VERIFY_FAILED" in _types(check)


def test_non_utf8_bytes_are_unreadable(tmp_path):
    d, ev = _ledger(tmp_path)
    ev.write_bytes(ev.read_bytes() + b"\xff\xfe\n")
    events, check, raw = attest.check_ledger(str(ev))
    assert events is None and raw is None and _types(check) & {"LEDGER_UNREADABLE"}
