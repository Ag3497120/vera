"""W4-m: the `Ledger` Protocol (append / events / count / last_seq) over a persistent sovereign.

S1 (second half): a correction goes in as a forward append and the old row stays.
S6 (Protocol side): the same events through the in-memory reference and the persistent ledger give the same bytes.
"""
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'sovereign'))

from verantyx import sovereign as sov    # noqa: E402
import sov_memory_ledger as M    # noqa: E402
import sov_protocol_reader as P    # noqa: E402

EVENTS = [
    {"kind": "utterance", "payload": {"phrase": "alpha", "turn": 1}},
    {"kind": "observation", "payload": {"cell": "c1", "occupied": "UNOCCUPIED"}},
    {"kind": "utterance", "payload": {"phrase": "alpha", "turn": 2}},
    {"kind": "decision", "payload": {"choice": "left", "note": "日本語のまま"}},
    {"kind": "observation", "payload": {"cell": "c2", "occupied": "ATTESTED"}},
]


@pytest.fixture()
def ledger(tmp_path):
    assert sov.create(tmp_path, "s1", "owner-a")["verdict"] == "CREATED"
    return sov.open_ledger(tmp_path, "s1", now=M.FakeClock())


def test_satisfies_the_protocol(ledger):
    assert isinstance(ledger, sov.Ledger)
    assert isinstance(M.MemoryLedger("s1"), sov.Ledger)


def test_append_returns_id_and_events_come_back_in_seq_order(ledger):
    ids = [ledger.append(e) for e in EVENTS]
    assert ids == [f"s1:{i}" for i in range(1, len(EVENTS) + 1)]
    got = ledger.events()
    assert [e["seq"] for e in got] == [1, 2, 3, 4, 5]
    assert [e["id"] for e in got] == ids
    assert [e["kind"] for e in got] == [e["kind"] for e in EVENTS]
    assert [e["payload"] for e in got] == [e["payload"] for e in EVENTS]
    assert all(set(e) == {"id", "seq", "ts", "kind", "payload"} for e in got)
    assert got[0]["ts"] == "2026-10-01T00:00:00+00:00" and got[1]["ts"] == "2026-10-01T00:00:01+00:00"


def test_events_returns_fresh_dicts(ledger):
    ledger.append(EVENTS[0])
    ledger.events()[0]["payload"]["phrase"] = "tampered"
    assert ledger.events()[0]["payload"]["phrase"] == "alpha"


@pytest.mark.parametrize("bad", ["bogus", "", None, 3, "Utterance"])
def test_bad_kind_is_refused_and_nothing_is_written(ledger, bad):
    with pytest.raises(sov.LedgerRefusal) as e:
        ledger.append({"kind": bad, "payload": {}})
    assert e.value.code == "BAD_KIND"
    assert ledger.events() == []


@pytest.mark.parametrize("bad", [None, "text", [1], 5, {"a": {1, 2}}, {"a": float("nan")}, {1: "x"},
                                 {"a": (1, 2)}])
def test_bad_payload_is_refused(ledger, bad):
    with pytest.raises(sov.LedgerRefusal) as e:
        ledger.append({"kind": "utterance", "payload": bad})
    assert e.value.code == "BAD_PAYLOAD"
    assert ledger.events() == []


@pytest.mark.parametrize("extra", ["seq", "ts", "id", "whatever"])
def test_extra_keys_are_refused_including_seq_and_ts(ledger, extra):
    with pytest.raises(sov.LedgerRefusal) as e:
        ledger.append({"kind": "utterance", "payload": {}, extra: 1})
    assert e.value.code == "EXTRA_KEYS"
    assert ledger.events() == []


def test_missing_keys_are_refused_with_their_own_code(ledger):
    with pytest.raises(sov.LedgerRefusal) as e:
        ledger.append({"payload": {}})
    assert e.value.code == "BAD_KIND"
    with pytest.raises(sov.LedgerRefusal) as e:
        ledger.append({"kind": "utterance"})
    assert e.value.code == "BAD_PAYLOAD"
    with pytest.raises(sov.LedgerRefusal) as e:
        ledger.append(["utterance", {}])
    assert e.value.code == "BAD_PAYLOAD"


def test_since_means_after_that_event(ledger):
    ids = [ledger.append(e) for e in EVENTS]
    assert [e["id"] for e in ledger.events(since=ids[1])] == ids[2:]
    assert ledger.events(since=ids[-1]) == []          # a real, known id with nothing after it
    assert [e["id"] for e in ledger.events(since=None)] == ids


@pytest.mark.parametrize("bad", ["s1:99", "s2:1", "1", "", "s1:", "s1:01", "garbage", "s1:1:1", "s1:-1"])
def test_unknown_since_is_a_type_not_an_empty_list(ledger, bad):
    ledger.append(EVENTS[0])
    with pytest.raises(sov.UnknownSince):
        ledger.events(since=bad)
    assert issubclass(sov.UnknownSince, LookupError)


def test_count_and_last_seq_match_the_value_and_its_type(ledger):
    for e in EVENTS:
        ledger.append(e)
    ledger.append({"kind": "utterance", "payload": {"turn": "1"}})
    assert ledger.count("phrase", "alpha") == 2
    assert ledger.last_seq("phrase", "alpha") == 3
    assert ledger.count("turn", 1) == 1          # the integer 1 ...
    assert ledger.count("turn", "1") == 1        # ... and the string "1" are different
    assert ledger.last_seq("turn", "1") == 6
    assert ledger.count("turn", True) == 0       # True is not 1 here
    assert ledger.count("phrase", "beta") == 0
    assert ledger.last_seq("phrase", "beta") is None
    assert ledger.count("missing_key", "alpha") == 0
    assert ledger.last_seq("missing_key", "alpha") is None


def test_only_top_level_payload_keys_count(ledger):
    ledger.append({"kind": "utterance", "payload": {"outer": {"phrase": "alpha"}}})
    assert ledger.count("phrase", "alpha") == 0


def test_correction_is_a_forward_append_and_the_old_row_stays(ledger):
    first = ledger.append({"kind": "utterance", "payload": {"phrase": "wrongg"}})
    fix = ledger.append({"kind": "utterance", "payload": {"phrase": "wrong", "corrects": first}})
    rows = ledger.events()
    assert [r["id"] for r in rows] == [first, fix]
    assert rows[0]["payload"] == {"phrase": "wrongg"}        # the earlier row is exactly as it was
    assert rows[1]["payload"]["corrects"] == first
    assert ledger.count("phrase", "wrongg") == 1             # raw numbers: the corrected event still counts
    assert ledger.last_seq("phrase", "wrongg") == 1


@pytest.mark.parametrize("target", ["s1:5", "s9:1", "nonsense", 7, None])
def test_correction_of_a_missing_event_is_refused(ledger, target):
    ledger.append(EVENTS[0])
    with pytest.raises(sov.LedgerRefusal) as e:
        ledger.append({"kind": "utterance", "payload": {"corrects": target}})
    assert e.value.code == "UNKNOWN_CORRECTS_TARGET"
    assert len(ledger.events()) == 1


def test_same_events_through_the_reference_and_the_persistent_ledger_give_the_same_bytes(tmp_path):
    sov.create(tmp_path, "s1", "owner-a")
    persistent = sov.open_ledger(tmp_path, "s1", now=M.FakeClock())
    reference = M.MemoryLedger("s1", now=M.FakeClock())
    for e in EVENTS:
        assert persistent.append(e) == reference.append(e)
    a, b = P.digest(persistent), P.digest(reference)
    assert a == b and len(a) > 200
    assert P.candidates(persistent, "phrase") == P.candidates(reference, "phrase") == [("alpha", 2, 3)]


def test_digest_changes_when_an_event_is_added(ledger):
    for e in EVENTS[:3]:
        ledger.append(e)
    d1 = P.digest(ledger)
    ledger.append(EVENTS[3])
    assert P.digest(ledger) != d1


def test_reopening_gives_the_same_ledger(tmp_path):
    sov.create(tmp_path, "s1", "owner-a")
    l1 = sov.open_ledger(tmp_path, "s1", now=M.FakeClock())
    for e in EVENTS:
        l1.append(e)
    d = P.digest(l1)
    assert P.digest(sov.open_ledger(tmp_path, "s1")) == d


def test_naive_clock_is_refused(tmp_path):
    from datetime import datetime
    sov.create(tmp_path, "s1", "owner-a")
    ledger = sov.open_ledger(tmp_path, "s1", now=lambda: datetime(2026, 10, 1, 0, 0, 0))
    with pytest.raises(ValueError):
        ledger.append(EVENTS[0])
    assert sov.open_ledger(tmp_path, "s1").events() == []


def test_ts_is_utc_whatever_the_zone_of_the_clock(tmp_path):
    from datetime import datetime, timedelta, timezone
    sov.create(tmp_path, "s1", "owner-a")
    jst = timezone(timedelta(hours=9))
    ledger = sov.open_ledger(tmp_path, "s1", now=lambda: datetime(2026, 10, 2, 3, 0, 0, tzinfo=jst))
    ledger.append(EVENTS[0])
    assert ledger.events()[0]["ts"] == "2026-10-01T18:00:00+00:00"


def test_unknown_store_is_a_type(tmp_path):
    with pytest.raises(sov.UnknownStore):
        sov.open_ledger(tmp_path, "nope")
