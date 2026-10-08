"""W4-m S2 / S3: the unit operations on a sovereign -- create, detach, attach, export, release.

Vera only appends to the structure-side registry and copies bytes where the user pointed.
It never writes to, moves, or deletes the sovereign's own file (checked by bytes and mtime).
"""
import os
import sqlite3
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'sovereign'))

from verantyx import sovereign as sov    # noqa: E402
import sov_memory_ledger as M    # noqa: E402
import sov_protocol_reader as P    # noqa: E402

EVENTS = [
    {"kind": "utterance", "payload": {"phrase": "alpha"}},
    {"kind": "observation", "payload": {"cell": "c1", "occupied": "UNOCCUPIED"}},
    {"kind": "decision", "payload": {"choice": "left"}},
]


def fill(root, sid="s1", owner="owner-a", **kw):
    assert sov.create(root, sid, owner, **kw)["verdict"] == "CREATED"
    led = sov.open_ledger(root, sid, now=M.FakeClock())
    for e in EVENTS:
        led.append(e)
    return led


def sov_file(root, sid="s1"):
    return Path(root) / "stores" / f"{sid}.sqlite"


def stamp(path):
    st = os.stat(path)
    return (Path(path).read_bytes(), st.st_mtime_ns, st.st_size)


def registry(root, sid=None):
    c = sqlite3.connect(str(Path(root) / "structure.sqlite"))
    try:
        q = "SELECT seq, op, store_id, path, file_sha256, content_sha256, detail FROM registry_log"
        if sid:
            return c.execute(q + " WHERE store_id = ? ORDER BY seq", (sid,)).fetchall()
        return c.execute(q + " ORDER BY seq").fetchall()
    finally:
        c.close()


# ------------------------------------------------------------------ create
def test_create_makes_one_file_and_a_registry_row(tmp_path):
    out = sov.create(tmp_path, "s1", "owner-a")
    assert out["verdict"] == "CREATED" and out["consent_promote"] is False
    assert sov_file(tmp_path).is_file() and (tmp_path / "structure.sqlite").is_file()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["stores", "structure.sqlite"]
    rows = registry(tmp_path)
    assert [r[1] for r in rows] == ["CREATE"]
    assert rows[0][4] == out["file_sha256"] == sov.sovereign_file_sha256(str(sov_file(tmp_path)))
    d = sov.describe(tmp_path, "s1")
    assert (d.store_id, d.owner, d.status) == ("s1", "owner-a", "ACTIVE")
    assert d.consent["promote"] is False       # the default is no consent


@pytest.mark.parametrize("bad", ["", "../x", "a/b", "-x", "a b", "x" * 65, "s:1", "日本"])
def test_create_refuses_bad_names_and_writes_nothing(tmp_path, bad):
    assert sov.create(tmp_path / "r", bad, "o")["verdict"] == "REFUSED_BAD_STORE_ID"
    assert not (tmp_path / "r").exists()


def test_create_refuses_a_taken_name_whatever_its_state(tmp_path):
    fill(tmp_path)
    assert sov.create(tmp_path, "s1", "o2")["verdict"] == "REFUSED_STORE_ID_TAKEN"
    sov.detach(tmp_path, "s1")
    assert sov.create(tmp_path, "s1", "o2")["verdict"] == "REFUSED_STORE_ID_TAKEN"
    sov.release(tmp_path, "s1", "s1")
    assert sov.create(tmp_path, "s1", "o2")["verdict"] == "REFUSED_STORE_ID_TAKEN"


def test_create_refuses_to_overwrite_an_existing_file(tmp_path):
    (tmp_path / "stores").mkdir()
    (tmp_path / "stores" / "s1.sqlite").write_bytes(b"someone's file")
    assert sov.create(tmp_path, "s1", "o")["verdict"] == "REFUSED_FILE_EXISTS"
    assert (tmp_path / "stores" / "s1.sqlite").read_bytes() == b"someone's file"


def test_two_sovereigns_in_one_root_are_two_files(tmp_path):
    fill(tmp_path, "s1")
    fill(tmp_path, "s2", owner="owner-b")
    assert sorted(p.name for p in (tmp_path / "stores").iterdir()) == ["s1.sqlite", "s2.sqlite"]
    out = sov.status(tmp_path)
    assert [s["store_id"] for s in out["stores"]] == ["s1", "s2"]
    assert all(s["status"] == "ACTIVE" and s["file_present"] for s in out["stores"])


def test_consent_is_a_log_the_latest_row_wins(tmp_path):
    fill(tmp_path)
    clock = M.FakeClock(M.day(3))
    r = sov.set_consent(tmp_path, "s1", True, now=clock)
    assert r["verdict"] == "CONSENT_RECORDED" and r["since_seq"] == 3
    assert sov.describe(tmp_path, "s1").consent == {"promote": True, "since": "2026-10-04T00:00:00+00:00",
                                                    "since_seq": 3}
    sov.open_ledger(tmp_path, "s1").append(EVENTS[0])
    sov.set_consent(tmp_path, "s1", False, now=clock)
    assert sov.describe(tmp_path, "s1").consent["promote"] is False
    c = sqlite3.connect(str(sov_file(tmp_path)))
    assert c.execute("SELECT promote, since_seq FROM consent_log ORDER BY seq").fetchall() == \
        [(0, 0), (1, 3), (0, 4)]
    c.close()


# --------------------------------------------------------- S2 detach / attach
def test_detach_makes_it_unreadable_and_attach_brings_it_back_identical(tmp_path):
    led = fill(tmp_path)
    before = P.digest(led)
    stamp0 = stamp(sov_file(tmp_path))
    out = sov.detach(tmp_path, "s1")
    assert out["verdict"] == "DETACHED" and out["file_left_in_place"] == str(sov_file(tmp_path))
    assert stamp(sov_file(tmp_path)) == stamp0                  # detach wrote nothing into the file
    with pytest.raises(sov.Detached):
        sov.open_ledger(tmp_path, "s1")
    for call in (led.events, lambda: led.count("phrase", "alpha"),
                 lambda: led.last_seq("phrase", "alpha"), lambda: led.append(EVENTS[0])):
        with pytest.raises(sov.Detached):                       # the handle opened BEFORE detach is cut too
            call()
    assert sov.describe(tmp_path, "s1").status == "DETACHED"
    back = sov.attach(tmp_path, store_id="s1")
    assert back["verdict"] == "ATTACHED" and back["same_as_detached"] is True
    assert stamp(sov_file(tmp_path)) == stamp0                  # attach wrote nothing into the file either
    assert P.digest(sov.open_ledger(tmp_path, "s1")) == before
    assert P.digest(led) == before                              # and the old handle works again
    assert [r[1] for r in registry(tmp_path)] == ["CREATE", "DETACH", "ATTACH"]


def test_detach_is_idempotent_and_typed(tmp_path):
    fill(tmp_path)
    assert sov.detach(tmp_path, "s1")["verdict"] == "DETACHED"
    assert sov.detach(tmp_path, "s1")["verdict"] == "ALREADY_DETACHED"
    assert len(registry(tmp_path)) == 2
    assert sov.detach(tmp_path, "nope")["verdict"] == "UNKNOWN_STORE"
    assert sov.attach(tmp_path, store_id="nope")["verdict"] == "UNKNOWN_STORE"


def test_attach_of_an_active_store_changes_nothing(tmp_path):
    fill(tmp_path)
    assert sov.attach(tmp_path, store_id="s1")["verdict"] == "ALREADY_ACTIVE"
    assert len(registry(tmp_path)) == 1


def test_attach_needs_exactly_one_of_store_id_or_file(tmp_path):
    fill(tmp_path)
    assert sov.attach(tmp_path)["verdict"] == "REFUSED_BAD_ARGUMENTS"
    assert sov.attach(tmp_path, store_id="s1", file="x")["verdict"] == "REFUSED_BAD_ARGUMENTS"


def test_attach_records_whether_the_file_changed_while_detached(tmp_path):
    fill(tmp_path)
    sov.detach(tmp_path, "s1")
    # the owner (not Vera) appends one row to the detached file with a raw connection
    c = sqlite3.connect(str(sov_file(tmp_path)), isolation_level=None)
    c.execute("INSERT INTO event_log (seq, ts, kind, payload) VALUES (4, '2026-10-02T00:00:00+00:00', "
              "'decision', '{\"choice\":\"right\"}')")
    c.close()
    out = sov.attach(tmp_path, store_id="s1")
    assert out["verdict"] == "ATTACHED" and out["same_as_detached"] is False   # recorded, not refused
    assert len(sov.open_ledger(tmp_path, "s1").events()) == 4


def test_attach_after_the_file_went_missing_is_its_own_type(tmp_path):
    fill(tmp_path)
    sov.detach(tmp_path, "s1")
    os.unlink(sov_file(tmp_path))          # the owner deletes it
    assert sov.attach(tmp_path, store_id="s1")["verdict"] == "UNREADABLE_FILE_MISSING"
    assert sov.describe(tmp_path, "s1").status == "DETACHED"


# ----------------------------------------------------------- S2 export / attach
def test_export_then_attach_elsewhere_gives_the_same_content(tmp_path):
    a, b = tmp_path / "A", tmp_path / "B"
    b.mkdir()
    led = fill(a)
    before = P.digest(led)
    stamp0 = stamp(sov_file(a))
    out = sov.export(a, "s1", str(b / "s1.sqlite"))
    assert out["verdict"] == "EXPORTED"
    assert stamp(sov_file(a)) == stamp0                          # export wrote nothing into the source
    assert out["file_sha256"] == sov.sovereign_file_sha256(str(b / "s1.sqlite")) == \
        sov.sovereign_file_sha256(str(sov_file(a)))
    assert [p.name for p in b.iterdir()] == ["s1.sqlite"]        # exactly one file where the user pointed
    att = sov.attach(b / "root2", file=str(b / "s1.sqlite"))
    assert att["verdict"] == "ATTACHED" and att["store_id"] == "s1"
    assert att["file_sha256"] == out["file_sha256"] and att["content_sha256"] == out["content_sha256"]
    assert att["path"] == str(b / "s1.sqlite")                   # registered in place, not copied again
    assert sorted(p.name for p in b.iterdir()) == ["root2", "s1.sqlite"]
    assert not (b / "root2" / "stores").exists()
    assert P.digest(sov.open_ledger(b / "root2", "s1")) == before
    assert [e["id"] for e in sov.open_ledger(b / "root2", "s1").events()] == ["s1:1", "s1:2", "s1:3"]
    assert [r[1] for r in registry(a)] == ["CREATE", "EXPORT"]
    assert registry(a)[1][4] == out["file_sha256"] and registry(a)[1][5] == out["content_sha256"]


def test_export_refuses_an_existing_destination_and_leaves_it_alone(tmp_path):
    fill(tmp_path / "A")
    dest = tmp_path / "taken.sqlite"
    dest.write_bytes(b"mine")
    assert sov.export(tmp_path / "A", "s1", str(dest))["verdict"] == "REFUSED_DESTINATION_EXISTS"
    assert dest.read_bytes() == b"mine"
    assert [r[1] for r in registry(tmp_path / "A")] == ["CREATE"]


def test_export_refuses_a_missing_parent_and_does_not_create_it(tmp_path):
    fill(tmp_path / "A")
    out = sov.export(tmp_path / "A", "s1", str(tmp_path / "nodir" / "s1.sqlite"))
    assert out["verdict"] == "REFUSED_DESTINATION_PARENT_MISSING"
    assert not (tmp_path / "nodir").exists()


def test_export_refuses_when_a_hot_journal_is_next_to_the_file(tmp_path):
    fill(tmp_path / "A")
    jr = Path(str(sov_file(tmp_path / "A")) + "-journal")
    jr.write_bytes(b"x")
    out = sov.export(tmp_path / "A", "s1", str(tmp_path / "out.sqlite"))
    assert out["verdict"] == "REFUSED_HOT_JOURNAL"
    assert not (tmp_path / "out.sqlite").exists()


def test_export_is_typed_for_unknown_detached_and_released(tmp_path):
    fill(tmp_path / "A")
    out = str(tmp_path / "out.sqlite")
    assert sov.export(tmp_path / "A", "zz", out)["verdict"] == "UNKNOWN_STORE"
    sov.detach(tmp_path / "A", "s1")
    assert sov.export(tmp_path / "A", "s1", out)["verdict"] == "DETACHED"
    sov.attach(tmp_path / "A", store_id="s1")
    sov.release(tmp_path / "A", "s1", "s1")
    assert sov.export(tmp_path / "A", "s1", out)["verdict"] == "RELEASED"
    assert not (tmp_path / "out.sqlite").exists()


def test_attach_of_a_file_whose_store_id_is_already_registered_is_refused(tmp_path):
    a = tmp_path / "A"
    fill(a)
    sov.export(a, "s1", str(tmp_path / "copy.sqlite"))
    assert sov.attach(a, file=str(tmp_path / "copy.sqlite"))["verdict"] == "REFUSED_STORE_ID_CONFLICT"
    assert len(registry(a)) == 2          # CREATE, EXPORT -- no ATTACH was added


def test_attach_of_a_released_store_id_is_refused_in_that_root_but_fine_elsewhere(tmp_path):
    a, b = tmp_path / "A", tmp_path / "B"
    fill(a)
    sov.export(a, "s1", str(tmp_path / "copy.sqlite"))
    sov.release(a, "s1", "s1")
    assert sov.attach(a, file=str(tmp_path / "copy.sqlite"))["verdict"] == "REFUSED_RELEASED"
    assert sov.attach(a, store_id="s1")["verdict"] == "REFUSED_RELEASED"
    assert sov.attach(b, file=str(tmp_path / "copy.sqlite"))["verdict"] == "ATTACHED"   # the user's own copy lives on


# ------------------------------------------------------------------------ S3
def test_release_needs_the_exact_confirmation_and_writes_nothing_otherwise(tmp_path):
    fill(tmp_path)
    for wrong in ("", "wrong", "S1", "s1 ", None):
        out = sov.release(tmp_path, "s1", wrong)
        assert out["verdict"] == "REFUSED_NOT_CONFIRMED"
    assert len(registry(tmp_path)) == 1
    assert sov.describe(tmp_path, "s1").status == "ACTIVE"
    sov.open_ledger(tmp_path, "s1").events()


def test_release_cuts_the_reference_records_the_hash_and_leaves_the_file(tmp_path):
    led = fill(tmp_path)
    pre = stamp(sov_file(tmp_path))
    pre_hash = sov.sovereign_file_sha256(str(sov_file(tmp_path)))
    out = sov.release(tmp_path, "s1", "s1")
    assert out["verdict"] == "RELEASED" and out["file_state"] == "PRESENT"
    assert out["file_sha256"] == pre_hash
    assert out["file_left_in_place"] == str(sov_file(tmp_path))
    assert "owner's operation" in out["note"]
    # Vera did not remove, rewrite, or touch the file
    assert sov_file(tmp_path).is_file() and stamp(sov_file(tmp_path)) == pre
    # the registry carries RELEASE with the hash
    rel = registry(tmp_path)[-1]
    assert rel[1] == "RELEASE" and rel[4] == pre_hash
    # no way back in through this root
    with pytest.raises(sov.Released):
        sov.open_ledger(tmp_path, "s1")
    for call in (led.events, lambda: led.count("phrase", "alpha"), lambda: led.append(EVENTS[0])):
        with pytest.raises(sov.Released):
            call()
    assert sov.describe(tmp_path, "s1").status == "RELEASED"


def test_released_stays_released_after_the_owner_deletes_the_file(tmp_path):
    fill(tmp_path)
    sov.release(tmp_path, "s1", "s1")
    os.unlink(sov_file(tmp_path))                 # the owner's operation, done in the test
    assert sov.status(tmp_path, "s1")["stores"][0]["status"] == "RELEASED"
    assert sov.status(tmp_path, "s1")["stores"][0]["file_present"] is False
    with pytest.raises(sov.Released):             # not UnknownStore, not FileMissing
        sov.open_ledger(tmp_path, "s1")
    assert sov.attach(tmp_path, store_id="s1")["verdict"] == "REFUSED_RELEASED"
    assert sov.describe(tmp_path, "s1").status == "RELEASED"


def test_release_when_the_file_is_already_gone_records_what_it_last_knew(tmp_path):
    fill(tmp_path)
    last = registry(tmp_path)[0][4]
    os.unlink(sov_file(tmp_path))
    out = sov.release(tmp_path, "s1", "s1")
    assert out["verdict"] == "RELEASED" and out["file_state"] == "MISSING"
    assert out["file_sha256"] is None and out["last_known_file_sha256"] == last
    assert out["file_left_in_place"] is None
    assert registry(tmp_path)[-1][4] is None


def test_release_twice_and_release_of_a_detached_or_unknown_store(tmp_path):
    fill(tmp_path)
    sov.detach(tmp_path, "s1")
    out = sov.release(tmp_path, "s1", "s1")                # a detached store can be released
    assert out["verdict"] == "RELEASED" and out["file_sha256"]
    again = sov.release(tmp_path, "s1", "s1")
    assert again["verdict"] == "ALREADY_RELEASED" and again["retired_on_rerun"] == 0
    assert len([r for r in registry(tmp_path) if r[1] == "RELEASE"]) == 1
    assert sov.release(tmp_path, "zz", "zz")["verdict"] == "UNKNOWN_STORE"


def test_releasing_one_sovereign_leaves_the_other_readable_and_unchanged(tmp_path):
    fill(tmp_path, "s1")
    other = fill(tmp_path, "s2", owner="owner-b")
    d2 = P.digest(other)
    sov.release(tmp_path, "s1", "s1")
    assert P.digest(sov.open_ledger(tmp_path, "s2")) == d2


# ----------------------------------------------------- separation of types
def test_unavailability_comes_in_separate_types(tmp_path):
    fill(tmp_path, "s1")
    fill(tmp_path, "s2")
    fill(tmp_path, "s3")
    fill(tmp_path, "s4")
    sov.detach(tmp_path, "s2")
    sov.release(tmp_path, "s3", "s3")
    os.unlink(sov_file(tmp_path, "s4"))
    garbage = tmp_path / "root2"
    sov.create(garbage, "g1", "o")
    sov_file(garbage, "g1").write_bytes(b"not sqlite at all" * 50)
    types = {}
    for root, sid, want in ((tmp_path, "zz", sov.UnknownStore), (tmp_path, "s2", sov.Detached),
                            (tmp_path, "s3", sov.Released), (tmp_path, "s4", sov.FileMissing),
                            (garbage, "g1", sov.NotSqlite)):
        with pytest.raises(want) as e:
            sov.open_ledger(root, sid)
        types[want] = e.value
    assert len({type(v) for v in types.values()}) == 5
    assert {v.verdict for v in types.values()} == {
        "UNKNOWN_STORE", "DETACHED", "RELEASED", "UNREADABLE_FILE_MISSING", "UNREADABLE_NOT_SQLITE"}
    for cls in types:
        assert issubclass(cls, sov.SovereignUnavailable) and issubclass(cls, LookupError)
    # no one of them is a subclass of another
    for x in types:
        for y in types:
            if x is not y:
                assert not issubclass(x, y)
    assert sov.status(tmp_path, "s4")["stores"][0]["file_present"] is False   # still registered, ACTIVE


def test_structure_absent_is_not_the_same_as_store_unknown(tmp_path):
    assert sov.status(tmp_path) == {"verdict": "ANSWER", "structure": "ABSENT", "stores": []}
    assert sov.status(tmp_path, "s1")["verdict"] == "UNKNOWN_STORE"
    assert not tmp_path.joinpath("structure.sqlite").exists()   # reading creates nothing
    # the list readers: no store_id on an absent structure is an empty list, but the typed answer says
    # ABSENT; an unregistered store_id is never an empty list (review r1, must 2)
    assert sov.all_promotions(tmp_path) == [] and sov.active_promotions(tmp_path) == []
    assert sov.promotions_answer(tmp_path) == {"verdict": "ANSWER", "structure": "ABSENT",
                                               "scope": "active", "promotions": []}
    for reader in (sov.all_promotions, sov.active_promotions):
        with pytest.raises(sov.UnknownStore):
            reader(tmp_path, "s1")
    assert sov.promotions_answer(tmp_path, "s1")["verdict"] == "UNKNOWN_STORE"
    assert not tmp_path.joinpath("structure.sqlite").exists()   # none of the reads created it


def test_status_reads_do_not_change_any_file(tmp_path):
    fill(tmp_path)
    before = (stamp(sov_file(tmp_path)), stamp(tmp_path / "structure.sqlite"))
    sov.status(tmp_path)
    sov.describe(tmp_path, "s1")
    sov.open_ledger(tmp_path, "s1").events()
    sov.active_promotions(tmp_path)
    assert (stamp(sov_file(tmp_path)), stamp(tmp_path / "structure.sqlite")) == before


def test_tz_naive_now_is_refused_by_create(tmp_path):
    from datetime import datetime
    with pytest.raises(ValueError):
        sov.create(tmp_path, "s1", "o", now=lambda: datetime(2026, 10, 1))
