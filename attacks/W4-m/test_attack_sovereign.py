"""Adversarial W4-m probes. Three contract attacks are expected to fail."""
import json
import multiprocessing
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from verantyx import sovereign as sov


def _day(n):
    return datetime(2026, 10, 1, tzinfo=timezone.utc) + timedelta(days=n)


def _promotable(root):
    sov.create(root, "s1", "owner-a", consent_promote=True, now=lambda: _day(0))
    led = sov.open_ledger(root, "s1", now=lambda: _day(0))
    for day in (0, 1, 1):
        led._now = lambda day=day: _day(day)
        led.append({"kind": "utterance", "payload": {"phrase": "candidate"}})
    return led


def test_tampered_export_cannot_be_attached(tmp_path):
    """Drop a rewrite trigger, alter one row, restore its exact SQL, then attach the export."""
    origin, moved = tmp_path / "origin", tmp_path / "moved"
    sov.create(origin, "s1", "owner-a")
    sov.open_ledger(origin, "s1").append(
        {"kind": "utterance", "payload": {"phrase": "original"}})
    exported = tmp_path / "s1.sqlite"
    assert sov.export(origin, "s1", str(exported))["verdict"] == "EXPORTED"

    conn = sqlite3.connect(exported, isolation_level=None)
    conn.execute("DROP TRIGGER event_log_no_update")
    conn.execute("UPDATE event_log SET payload = ? WHERE seq = 1",
                 (json.dumps({"phrase": "forged"}, separators=(",", ":")),))
    conn.execute(
        "CREATE TRIGGER event_log_no_update BEFORE UPDATE ON event_log "
        "BEGIN SELECT RAISE(ABORT, 'event_log is append-only: no update'); END")
    conn.close()

    attached = sov.attach(moved, file=str(exported))
    observed = (attached["verdict"],
                sov.open_ledger(moved, "s1").events()[0]["payload"]["phrase"])
    assert observed == ("UNREADABLE_SCHEMA", "original"), observed


def test_revoking_consent_while_promote_is_in_flight_stops_writes(tmp_path, monkeypatch):
    """Pause after promote read consent=true; revoke before it appends either promotion row."""
    _promotable(tmp_path)
    analyzed, resume = threading.Event(), threading.Event()
    real_analyze = sov._sov_analyze

    def pause_after_analysis(*args, **kwargs):
        result = real_analyze(*args, **kwargs)
        analyzed.set()
        assert resume.wait(5), "test synchronization timed out"
        return result

    monkeypatch.setattr(sov, "_sov_analyze", pause_after_analysis)
    result, errors = [], []

    def run_promote():
        try:
            result.append(sov.promote(tmp_path, "s1", now=lambda: _day(3)))
        except BaseException as exc:  # preserve worker errors for the main test thread
            errors.append(exc)

    worker = threading.Thread(target=run_promote)
    worker.start()
    assert analyzed.wait(5), "promote did not reach the synchronized point"
    sov.set_consent(tmp_path, "s1", False, now=lambda: _day(4))
    resume.set()
    worker.join(5)
    assert not worker.is_alive(), "promote did not finish"
    assert not errors, errors

    assert sov.describe(tmp_path, "s1").consent["promote"] is False
    assert result[0]["verdict"] == "NO_CONSENT", result[0]


def test_release_racing_with_promote_leaves_no_active_promotion(tmp_path, monkeypatch):
    """Pause before the structure-side promotion append; release completes, then resume."""
    _promotable(tmp_path)
    reached, resume = threading.Event(), threading.Event()
    real_append = sov._sov_append_structure_promotion

    def pause_before_structure_append(*args, **kwargs):
        reached.set()
        assert resume.wait(5), "test synchronization timed out"
        return real_append(*args, **kwargs)

    monkeypatch.setattr(sov, "_sov_append_structure_promotion", pause_before_structure_append)
    result, errors = [], []

    def run_promote():
        try:
            result.append(sov.promote(tmp_path, "s1", now=lambda: _day(3)))
        except BaseException as exc:
            errors.append(exc)

    worker = threading.Thread(target=run_promote)
    worker.start()
    assert reached.wait(5), "promote did not reach the synchronized point"
    assert sov.release(tmp_path, "s1", "s1", now=lambda: _day(4))["verdict"] == "RELEASED"
    resume.set()
    worker.join(5)
    assert not worker.is_alive(), "promote did not finish"
    assert not errors, errors

    answer = sov.promotions_answer(tmp_path, include_retired=False)
    assert answer["promotions"] == [], answer


def _promote_process(root, barrier, result_queue):
    real_analyze = sov._sov_analyze

    def wait_after_analysis(*args, **kwargs):
        result = real_analyze(*args, **kwargs)
        barrier.wait(timeout=10)
        return result

    sov._sov_analyze = wait_after_analysis
    try:
        result_queue.put(("ok", sov.promote(root, "s1", now=lambda: _day(3))))
    except BaseException as exc:
        result_queue.put(("error", repr(exc)))


def test_two_process_promotions_do_not_duplicate_the_same_candidate(tmp_path):
    if "fork" not in multiprocessing.get_all_start_methods():
        pytest.skip("this race probe requires fork so both children inherit initialized test helpers")
    _promotable(tmp_path)
    ctx = multiprocessing.get_context("fork")
    both_analyzed, result_queue = ctx.Barrier(2), ctx.Queue()
    children = [ctx.Process(target=_promote_process,
                            args=(str(tmp_path), both_analyzed, result_queue)) for _ in range(2)]
    for child in children:
        child.start()
    results = [result_queue.get(timeout=15) for _ in children]
    for child in children:
        child.join(15)
    assert all(child.exitcode == 0 for child in children), [child.exitcode for child in children]
    assert all(status == "ok" for status, _ in results), results
    active = sov.active_promotions(tmp_path, "s1")
    assert len(active) == 1, {"results": results, "active": active}


def test_two_concurrent_appends_keep_contiguous_unique_seq_and_valid_chain(tmp_path):
    sov.create(tmp_path, "s1", "owner-a")

    def append(i):
        return sov.open_ledger(tmp_path, "s1", now=lambda: _day(i)).append(
            {"kind": "utterance", "payload": {"phrase": f"parallel-{i}"}})

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(append, (0, 1)))
    events = sov.open_ledger(tmp_path, "s1").events()
    assert sorted(ids) == ["s1:1", "s1:2"]
    assert [event["seq"] for event in events] == [1, 2]
    assert {event["id"] for event in events} == set(ids)


def _append_process(root, index, barrier, result_queue):
    real_txn = sov._sov_txn

    def wait_before_begin(conn, fn):
        barrier.wait(timeout=10)
        return real_txn(conn, fn)

    sov._sov_txn = wait_before_begin
    try:
        event_id = sov.open_ledger(root, "s1", now=lambda: _day(index)).append(
            {"kind": "utterance", "payload": {"phrase": f"process-{index}"}})
        result_queue.put(("ok", event_id))
    except BaseException as exc:
        result_queue.put(("error", repr(exc)))


def test_two_process_appends_serialize_without_seq_holes(tmp_path):
    if "fork" not in multiprocessing.get_all_start_methods():
        pytest.skip("this stress probe requires fork so both children share the initialized test module")
    sov.create(tmp_path, "s1", "owner-a")
    ctx = multiprocessing.get_context("fork")
    barrier, result_queue = ctx.Barrier(2), ctx.Queue()
    children = [ctx.Process(target=_append_process,
                            args=(str(tmp_path), i, barrier, result_queue)) for i in (0, 1)]
    for child in children:
        child.start()
    results = [result_queue.get(timeout=15) for _ in children]
    for child in children:
        child.join(15)
    assert all(child.exitcode == 0 for child in children), [child.exitcode for child in children]
    assert all(status == "ok" for status, _ in results), results
    events = sov.open_ledger(tmp_path, "s1").events()
    assert [event["seq"] for event in events] == [1, 2]
    assert {event["id"] for event in events} == {value for _, value in results}


def test_negative_seq_is_rejected_by_raw_sqlite_insert(tmp_path):
    sov.create(tmp_path, "s1", "owner-a")
    conn = sqlite3.connect(tmp_path / "stores" / "s1.sqlite", isolation_level=None)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO event_log (seq, ts, kind, payload) VALUES (-1, ?, 'utterance', '{}')",
            (_day(0).isoformat(),))
    assert conn.execute("SELECT COUNT(*) FROM event_log").fetchone()[0] == 0
    conn.close()


def test_events_written_before_later_consent_stay_outside_its_window(tmp_path):
    sov.create(tmp_path, "s1", "owner-a")
    led = sov.open_ledger(tmp_path, "s1", now=lambda: _day(0))
    for day in (0, 1, 1):
        led._now = lambda day=day: _day(day)
        led.append({"kind": "utterance", "payload": {"phrase": "pre-consent"}})
    sov.set_consent(tmp_path, "s1", True, now=lambda: _day(2))
    out = sov.promote(tmp_path, "s1", now=lambda: _day(3))
    assert out["verdict"] == "NOTHING_TO_PROMOTE"
    assert out["counts"]["outside_consent_window"] == 3
    assert sov.active_promotions(tmp_path) == []


def test_sequential_release_blocks_later_promote_and_attach(tmp_path):
    _promotable(tmp_path)
    assert sov.promote(tmp_path, "s1", now=lambda: _day(3))["verdict"] == "PROMOTED"
    exported = tmp_path / "s1.sqlite"
    assert sov.export(tmp_path, "s1", str(exported))["verdict"] == "EXPORTED"
    assert sov.release(tmp_path, "s1", "s1", now=lambda: _day(4))["verdict"] == "RELEASED"
    assert sov.promote(tmp_path, "s1", now=lambda: _day(5))["verdict"] == "RELEASED"
    assert sov.attach(tmp_path, file=str(exported))["verdict"] == "REFUSED_RELEASED"
    assert sov.active_promotions(tmp_path, "s1") == []


def test_alter_table_attack_is_detected_on_next_api_open(tmp_path):
    sov.create(tmp_path, "s1", "owner-a")
    conn = sqlite3.connect(tmp_path / "stores" / "s1.sqlite", isolation_level=None)
    conn.execute("ALTER TABLE event_log ADD COLUMN altered TEXT")
    conn.close()
    with pytest.raises(sov.SchemaMismatch):
        sov.open_ledger(tmp_path, "s1")
