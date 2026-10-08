"""W5-b / W4-m: promote is one write transaction; a candidate is registered once; release leaves nothing active.

The attack file (tests/attack/test_attack_w4m_sovereign.py) found three races: a consent withdrawn while promote is
in flight, a release racing a promote, two processes promoting the same candidate. These tests use other inputs than
the attack: other candidates (placement cells, not only phrases), other timing points, and a raw-SQL check of the
uniqueness. Time is always injected.
"""
import collections
import multiprocessing
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from verantyx import sovereign as sov


def _day(n):
    return datetime(2026, 11, 1, tzinfo=timezone.utc) + timedelta(days=n)


def _setup(root, store="w5", phrases=("alpha", "beta", "gamma"), consent=True):
    out = sov.create(root, store, "owner-w5", consent_promote=consent, now=lambda: _day(0))
    assert out["verdict"] == "CREATED"
    led = sov.open_ledger(root, store, now=lambda: _day(0))
    for key in phrases:
        for day in (0, 1, 1):
            led._now = lambda day=day: _day(day)
            led.append({"kind": "utterance", "payload": {"phrase": key}})
    return led


def _rows(path, table):
    c = sqlite3.connect(str(path))
    try:
        return c.execute(f"SELECT * FROM {table} ORDER BY seq").fetchall()
    finally:
        c.close()


def _struct(root, table):
    return _rows(Path(root) / "structure.sqlite", table)


def _sovrows(root, store, table):
    return _rows(Path(root) / "stores" / f"{store}.sqlite", table)


def _pause_after_analysis(monkeypatch):
    """promote reads consent, analyses, then waits; returns (event reached, event resume)."""
    reached, resume = threading.Event(), threading.Event()
    real = sov._sov_analyze
    calls = []

    def pausing(*a, **kw):
        out = real(*a, **kw)
        calls.append(1)
        reached.set()
        assert resume.wait(10), "test synchronization timed out"
        return out

    monkeypatch.setattr(sov, "_sov_analyze", pausing)
    return reached, resume, calls


def _promote_in_thread(root, store, day=3):
    box = {}

    def run():
        try:
            box["out"] = sov.promote(root, store, now=lambda: _day(day))
        except BaseException as exc:    # kept for the main thread
            box["err"] = exc

    t = threading.Thread(target=run)
    t.start()
    return t, box


# ------------------------------------------------------------ (a) two processes promote at once
def _promote_gate(root, store, gate, q):
    gate.wait(20)
    q.put(sov.promote(root, store, now=lambda: _day(3))["verdict"])


def _release_gate(root, store, gate, q):
    gate.wait(20)
    q.put(sov.release(root, store, store, now=lambda: _day(4))["verdict"])


def _need_fork():
    if "fork" not in multiprocessing.get_all_start_methods():
        pytest.skip("this probe needs fork (this Mac has it; do not turn a missing fork into a pass elsewhere)")
    return multiprocessing.get_context("fork")


def test_two_processes_promoting_at_once_leave_one_active_row_per_candidate(tmp_path):
    ctx = _need_fork()
    seen = collections.Counter()
    for i in range(20):
        root = tmp_path / f"run{i}"
        _setup(root)
        gate, q = ctx.Barrier(2), ctx.Queue()
        procs = [ctx.Process(target=_promote_gate, args=(str(root), "w5", gate, q)) for _ in range(2)]
        for p in procs:
            p.start()
        verdicts = sorted(q.get(timeout=60) for _ in procs)
        for p in procs:
            p.join(30)
            assert p.exitcode == 0
        active = sov.active_promotions(root, "w5")
        ids = [a["promotion_id"] for a in active]
        assert len(ids) == len(set(ids)) == 3, (i, ids)
        assert len(_struct(root, "promotion_log")) == 3                  # no second row for any candidate
        assert len(_sovrows(root, "w5", "promotion_log")) == 3           # one back-link per candidate
        seen[tuple(verdicts)] += 1
    # each run: one process wrote the three candidates, the other wrote none (a refusal or nothing left)
    assert all(v[0] in ("NOTHING_TO_PROMOTE", "PROMOTED") and "PROMOTED" in v for v in seen), seen


# ------------------------------------------------------------ (b) promote and release together
def test_a_promote_racing_a_release_never_leaves_an_active_row_after_release(tmp_path):
    ctx = _need_fork()
    for i in range(20):
        root = tmp_path / f"run{i}"
        _setup(root)
        gate, q = ctx.Barrier(2), ctx.Queue()
        procs = [ctx.Process(target=_promote_gate, args=(str(root), "w5", gate, q)),
                 ctx.Process(target=_release_gate, args=(str(root), "w5", gate, q))]
        for p in procs:
            p.start()
        verdicts = sorted(q.get(timeout=60) for _ in procs)
        for p in procs:
            p.join(30)
            assert p.exitcode == 0
        assert sov.describe(root, "w5").status == "RELEASED", verdicts
        assert sov.active_promotions(root, "w5") == [], (i, verdicts)
        # nothing was promoted twice either
        ids = [r[2] for r in _struct(root, "promotion_log")]
        assert len(ids) == len(set(ids))


# ------------------------------------------------------------ (c)(d) the consent is read again at the write
def test_a_consent_withdrawn_after_the_analysis_stops_the_write_on_both_sides(tmp_path, monkeypatch):
    _setup(tmp_path, phrases=("one", "two"))
    reached, resume, _calls = _pause_after_analysis(monkeypatch)
    t, box = _promote_in_thread(tmp_path, "w5")
    assert reached.wait(10)
    sov.set_consent(tmp_path, "w5", False, now=lambda: _day(4))
    resume.set()
    t.join(15)
    assert not t.is_alive() and "err" not in box, box
    assert box["out"]["verdict"] == "NO_CONSENT" and box["out"]["wrote"] == 0
    assert _struct(tmp_path, "promotion_log") == [] and _sovrows(tmp_path, "w5", "promotion_log") == []


def test_a_consent_withdrawn_and_given_again_is_a_changed_consent_and_writes_nothing(tmp_path, monkeypatch):
    _setup(tmp_path, phrases=("one", "two"))
    reached, resume, _calls = _pause_after_analysis(monkeypatch)
    t, box = _promote_in_thread(tmp_path, "w5")
    assert reached.wait(10)
    sov.set_consent(tmp_path, "w5", False, now=lambda: _day(4))
    led = sov.open_ledger(tmp_path, "w5", now=lambda: _day(4))
    led.append({"kind": "utterance", "payload": {"phrase": "said between the two consents"}})
    sov.set_consent(tmp_path, "w5", True, now=lambda: _day(5))     # since_seq moved: another window
    resume.set()
    t.join(15)
    assert not t.is_alive() and "err" not in box, box
    out = box["out"]
    assert out["verdict"] == "CONSENT_CHANGED" and out["wrote"] == 0, out
    assert out["consent"]["since_seq"] != out["consent_at_start"]["since_seq"]
    assert _struct(tmp_path, "promotion_log") == [] and _sovrows(tmp_path, "w5", "promotion_log") == []
    # the analysis is the part that was stale: the next run, with the new window, decides again
    again = sov.promote(tmp_path, "w5", now=lambda: _day(6))
    assert again["verdict"] == "NOTHING_TO_PROMOTE" and again["counts"]["outside_consent_window"] > 0


# ------------------------------------------------------------ (e) the uniqueness is in the structure ledger
def test_a_second_row_for_the_same_candidate_is_refused_by_the_ledger_itself(tmp_path):
    _setup(tmp_path, phrases=("one",))
    assert sov.promote(tmp_path, "w5", now=lambda: _day(3))["verdict"] == "PROMOTED"
    path = Path(tmp_path) / "structure.sqlite"
    first = _struct(tmp_path, "promotion_log")[0]
    conn = sqlite3.connect(str(path), isolation_level=None)
    try:
        for verb in ("INSERT", "INSERT OR REPLACE", "INSERT OR IGNORE"):
            with pytest.raises(sqlite3.IntegrityError) as exc:
                conn.execute(
                    f"{verb} INTO promotion_log (seq, ts, promotion_id, store_id, kind, basis, payload, thresholds) "
                    "VALUES (2, ?, ?, ?, ?, ?, '{}', '{}')",
                    (first[1], first[2], first[3], first[4], first[5]))
            assert "DUPLICATE_PROMOTION" in str(exc.value)
        assert conn.execute("SELECT COUNT(*) FROM promotion_log").fetchone()[0] == 1
    finally:
        conn.close()
    assert _struct(tmp_path, "promotion_log")[0] == first            # the old row is untouched


def test_the_uniqueness_is_a_trigger_and_not_a_second_key_and_counts_retired_rows(tmp_path):
    _setup(tmp_path, phrases=("one",))
    sov.promote(tmp_path, "w5", now=lambda: _day(3))
    conn = sqlite3.connect(str(Path(tmp_path) / "structure.sqlite"))
    try:
        sql = [r[0] for r in conn.execute("SELECT sql FROM sqlite_master WHERE name = 'promotion_log_one_per_candidate'")]
        assert len(sql) == 1 and "RAISE(ABORT, 'DUPLICATE_PROMOTION')" in sql[0]
        assert not [r for r in conn.execute("SELECT name FROM sqlite_master WHERE type = 'index' AND sql IS NOT NULL")]
    finally:
        conn.close()
    sov.release(tmp_path, "w5", "w5", now=lambda: _day(4))
    assert sov.active_promotions(tmp_path, "w5") == [] and len(_struct(tmp_path, "promotion_log")) == 1


def test_a_candidate_that_is_already_in_the_structure_is_refused_and_counted_not_written(tmp_path, monkeypatch):
    _setup(tmp_path, phrases=("one", "two"))
    real = sov._sov_analyze
    # the analysis does not know about the first promote (as in a second process that analysed before it wrote)
    box = {}

    def stale(events, since_seq, n, d, store_id, active_ids):
        box.setdefault("first", real(events, since_seq, n, d, store_id, set()))
        return box["first"]

    monkeypatch.setattr(sov, "_sov_analyze", stale)
    first = sov.promote(tmp_path, "w5", now=lambda: _day(3))
    assert first["verdict"] == "PROMOTED" and len(first["promoted"]) == 2 and first["refused"] == []
    before = (_struct(tmp_path, "promotion_log"), _sovrows(tmp_path, "w5", "promotion_log"))
    second = sov.promote(tmp_path, "w5", now=lambda: _day(4))
    assert second["verdict"] == "NOTHING_TO_PROMOTE" and second["promoted"] == []
    assert sorted(r["reason"] for r in second["refused"]) == ["DUPLICATE_PROMOTION"] * 2
    assert second["counts"]["duplicate_promotion"] == 2
    assert (_struct(tmp_path, "promotion_log"), _sovrows(tmp_path, "w5", "promotion_log")) == before


# ------------------------------------------------------------ (f) a promote between the retirement and RELEASE
def test_a_promotion_written_between_the_retirement_and_the_release_row_is_retired_with_it(tmp_path, monkeypatch):
    _setup(tmp_path, phrases=("kept", "late"))
    # two promotions exist; a third structure row is added by hand in the gap before the RELEASE row
    first = sov.promote(tmp_path, "w5", now=lambda: _day(3))
    assert first["verdict"] == "PROMOTED" and len(first["promoted"]) == 2
    real = sov._sov_registry_append
    seen = {}

    def inject(root, **kw):
        if kw.get("op") == "RELEASE":
            conn = sov._sov_struct_open(root, write=True)
            try:
                def add():
                    return sov._sov_insert(conn, "promotion_log", {
                        "ts": "2026-11-05T00:00:00+00:00",
                        "promotion_id": sov._sov_promotion_id("w5", "construction_evidence", "inserted in the gap"),
                        "store_id": "w5", "kind": "construction_evidence", "basis": "conversation:w5",
                        "payload": sov._sov_dump({"key": "inserted in the gap", "count": 3, "days": 2, "evidence": []}),
                        "thresholds": sov._sov_dump({"n": 3, "d": 2, "source": "prereg"})})
                seen["seq"] = sov._sov_txn(conn, add)
            finally:
                conn.close()
        return real(root, **kw)

    monkeypatch.setattr(sov, "_sov_registry_append", inject)
    out = sov.release(tmp_path, "w5", "w5", now=lambda: _day(6))
    assert out["verdict"] == "RELEASED" and seen["seq"] == 3
    assert sov.active_promotions(tmp_path, "w5") == []
    reg = sov._sov_struct_open(tmp_path)
    try:
        release_row = [r for r in sov._sov_registry(reg, "w5") if r["op"] == "RELEASE"][-1]
    finally:
        reg.close()
    assert release_row["detail"]["retired_with_release"] == 1
    assert release_row["detail"]["retired_this_run"] == 3 and out["retired_this_run"] == 3
    retired = _struct(tmp_path, "retire_log")
    assert len(retired) == 3 and len({r[2] for r in retired}) == 3        # each promotion retired exactly once


# ------------------------------------------------------------ (g) an old structure ledger is not repaired silently
def test_a_structure_ledger_without_the_uniqueness_trigger_is_a_schema_mismatch(tmp_path):
    statements = [s for s in sov._sov_statements("structure") if "promotion_log_one_per_candidate" not in s]
    assert len(statements) == len(sov._sov_statements("structure")) - 1
    path = Path(tmp_path) / "structure.sqlite"
    conn = sqlite3.connect(str(path), isolation_level=None)
    for s in statements:
        conn.execute(s)
    conn.close()
    with pytest.raises(sov.SchemaMismatch) as exc:
        sov._sov_struct_open(tmp_path)
    assert exc.value.detail["missing"] == ["trigger:promotion_log_one_per_candidate"]
    out = sov.status(tmp_path)
    assert out["verdict"] == "UNREADABLE_SCHEMA"
    assert [r[0] for r in sqlite3.connect(str(path)).execute(
        "SELECT name FROM sqlite_master WHERE name = 'promotion_log_one_per_candidate'")] == []   # not added behind our back
