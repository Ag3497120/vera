"""W4-m S1: the inside of a sovereign is append-only, enforced by the database itself.

Every test here talks to the files through a RAW `sqlite3` connection, not through the module's functions:
the guarantee is about the file, so the attack has to come from outside the API. Seven tables
(four in a sovereign file, three on the structure side) x six attacks.
"""
import re
import sqlite3
import sys
from pathlib import Path

import pytest

from verantyx import sovereign as sov

HERE = Path(__file__).resolve().parent
SOV_SRC = Path(sov.__file__)
TS = "2026-10-03T00:00:00+00:00"

# a legal next row for each table: (file, table, {column: value}) -- seq is added by the test
ROWS = {
    "event_log": ("sov", {"ts": TS, "kind": "utterance", "payload": '{"phrase":"x"}'}),
    "consent_log": ("sov", {"ts": TS, "promote": 1, "since_seq": 0}),
    "meta": ("sov", {"format": sov.SOVEREIGN_FORMAT, "store_id": "s1", "owner": "o", "created": TS}),
    "sov_promotion_log": ("sov", {"ts": TS, "promotion_id": "p", "kind": "construction_evidence",
                                  "cand_key": "k", "structure_seq": 1, "evidence": "[]",
                                  "structure_ref": "r"}),
    "registry_log": ("struct", {"ts": TS, "store_id": "s1", "op": "EXPORT", "path": None,
                                "file_sha256": None, "content_sha256": None, "detail": "{}"}),
    "struct_promotion_log": ("struct", {"ts": TS, "promotion_id": "p", "store_id": "s1",
                                        "kind": "construction_evidence", "basis": "conversation:s1",
                                        "payload": "{}", "thresholds": "{}"}),
    "retire_log": ("struct", {"ts": TS, "promotion_seq": 1, "promotion_id": "p", "store_id": "s1",
                              "reason": "RELEASED", "registry_seq": 1}),
}
TABLE_OF = {"sov_promotion_log": "promotion_log", "struct_promotion_log": "promotion_log"}


@pytest.fixture()
def world(tmp_path):
    assert sov.create(tmp_path, "s1", "owner-a")["verdict"] == "CREATED"
    sov_path = str(tmp_path / "stores" / "s1.sqlite")
    struct_path = str(tmp_path / "structure.sqlite")
    conns = {"sov": sqlite3.connect(sov_path, isolation_level=None),
             "struct": sqlite3.connect(struct_path, isolation_level=None)}
    yield tmp_path, conns, sov_path, struct_path
    for c in conns.values():
        c.close()


def _table(name):
    return TABLE_OF.get(name, name)


def _insert(conn, name, seq, how="INSERT"):
    _which, cols = ROWS[name]
    names = ["seq"] + list(cols) if seq is not None else list(cols)
    vals = ([seq] if seq is not None else []) + list(cols.values())
    return conn.execute(
        f"{how} INTO {_table(name)} ({','.join(names)}) VALUES ({','.join('?' * len(vals))})", vals)


def _snapshot(conn, name):
    return conn.execute(f"SELECT * FROM {_table(name)} ORDER BY seq").fetchall()


def _prepare(conns, name):
    """Make sure the table has at least one row, using a legal append (the only door)."""
    conn = conns[ROWS[name][0]]
    n = conn.execute(f"SELECT IFNULL(MAX(seq),0) FROM {_table(name)}").fetchone()[0]
    if name != "meta" and n == 0:
        _insert(conn, name, 1)
    return conn


@pytest.mark.parametrize("name", sorted(ROWS))
def test_every_table_refuses_every_rewrite(world, name):
    _tmp, conns, _sp, _stp = world
    conn = _prepare(conns, name)
    before = _snapshot(conn, name)
    assert before, "the table must hold a row to attack"
    last = before[-1][0]
    first_col = [r[1] for r in conn.execute(f"PRAGMA table_info({_table(name)})")][1]
    attacks = [
        f"UPDATE {_table(name)} SET {first_col} = {first_col}",
        f"UPDATE {_table(name)} SET seq = seq + 100",
        f"DELETE FROM {_table(name)}",
        f"DELETE FROM {_table(name)} WHERE seq = {last}",
    ]
    for sql in attacks:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(sql)
    # INSERT OR REPLACE on an existing seq, INSERT ... ON CONFLICT DO UPDATE, skipped seq, no seq
    with pytest.raises(sqlite3.IntegrityError):
        _insert(conn, name, last, how="INSERT OR REPLACE")
    with pytest.raises(sqlite3.IntegrityError):
        _which, cols = ROWS[name]
        names = ["seq"] + list(cols)
        vals = [last] + list(cols.values())
        conn.execute(
            f"INSERT INTO {_table(name)} ({','.join(names)}) VALUES ({','.join('?' * len(vals))}) "
            f"ON CONFLICT(seq) DO UPDATE SET {first_col} = excluded.{first_col}", vals)
    with pytest.raises(sqlite3.IntegrityError):
        _insert(conn, name, last + 2)
    with pytest.raises(sqlite3.IntegrityError):
        _insert(conn, name, None)
    with pytest.raises(sqlite3.IntegrityError):
        _insert(conn, name, last, how="INSERT OR IGNORE")
    with pytest.raises(sqlite3.IntegrityError):
        _insert(conn, name, last, how="INSERT OR FAIL")
    # not one of the attacks changed anything
    assert _snapshot(conn, name) == before


def test_meta_holds_exactly_one_row(world):
    _tmp, conns, _sp, _stp = world
    with pytest.raises(sqlite3.IntegrityError):
        _insert(conns["sov"], "meta", 2)
    assert conns["sov"].execute("SELECT COUNT(*) FROM meta").fetchone()[0] == 1


def test_legal_append_is_the_only_door(world):
    _tmp, conns, _sp, _stp = world
    conn = conns["sov"]
    n = conn.execute("SELECT COUNT(*) FROM event_log").fetchone()[0]
    _insert(conn, "event_log", n + 1)
    assert conn.execute("SELECT COUNT(*) FROM event_log").fetchone()[0] == n + 1


def test_check_constraints_hold(world):
    _tmp, conns, _sp, _stp = world
    with pytest.raises(sqlite3.IntegrityError):
        conns["sov"].execute("INSERT INTO event_log (seq, ts, kind, payload) VALUES (1, 't', 'bogus', '{}')")
    with pytest.raises(sqlite3.IntegrityError):
        conns["sov"].execute("INSERT INTO consent_log (seq, ts, promote, since_seq) VALUES (2, 't', 7, 0)")
    with pytest.raises(sqlite3.IntegrityError):
        conns["struct"].execute(
            "INSERT INTO registry_log (seq, ts, store_id, op) VALUES (2, 't', 's1', 'WIPE')")
    with pytest.raises(sqlite3.IntegrityError):
        conns["struct"].execute(
            "INSERT INTO retire_log (seq, ts, promotion_seq, promotion_id, store_id, reason) "
            "VALUES (1, 't', 1, 'p', 's1', 'DELETED')")


def test_no_table_has_any_unique_or_second_primary_key(world):
    """An extra UNIQUE column lets INSERT OR REPLACE silently drop an old row (measured), so there must be none."""
    _tmp, conns, _sp, _stp = world
    for conn in conns.values():
        tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")]
        assert tables
        for t in tables:
            cols = conn.execute(f"PRAGMA table_info({t})").fetchall()
            assert [c[1] for c in cols if c[5]] == ["seq"], t
            assert not [r for r in conn.execute(f"PRAGMA index_list({t})")], t
        for t in tables:
            trig = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name = ?", (t,))}
            assert {f"{t}_next_seq", f"{t}_no_update", f"{t}_no_delete"} <= trig, t


def test_dropped_trigger_is_detected_by_the_shape_check(world):
    tmp, conns, sov_path, _stp = world
    conns["sov"].execute("DROP TRIGGER event_log_no_update")
    # the owner of the file can do anything; the shape check is what notices
    with pytest.raises(sov.SchemaMismatch) as e:
        sov.open_ledger(tmp, "s1")
    assert "trigger:event_log_no_update" in e.value.detail["missing"]
    out = sov.status(tmp, "s1")
    assert out["verdict"] == "ANSWER"       # the structure side is untouched
    r = sov.export(tmp, "s1", str(tmp / "out.sqlite"))
    assert r["verdict"] == "UNREADABLE_SCHEMA"
    assert not (tmp / "out.sqlite").exists()


def test_changed_trigger_body_is_detected_not_only_missing_names(world):
    tmp, conns, _sp, _stp = world
    conns["sov"].execute("DROP TRIGGER event_log_no_delete")
    conns["sov"].execute(
        "CREATE TRIGGER event_log_no_delete BEFORE DELETE ON event_log BEGIN SELECT 1; END")
    with pytest.raises(sov.SchemaMismatch) as e:
        sov.open_ledger(tmp, "s1")
    assert "trigger:event_log_no_delete" in e.value.detail["different"]


def test_extra_table_is_detected(world):
    tmp, conns, _sp, _stp = world
    conns["sov"].execute("CREATE TABLE side_channel (x)")
    with pytest.raises(sov.SchemaMismatch) as e:
        sov.open_ledger(tmp, "s1")
    assert "table:side_channel" in e.value.detail["unexpected"]


def test_dropped_trigger_on_the_structure_side_is_detected(world):
    tmp, conns, _sp, _stp = world
    conns["struct"].execute("DROP TRIGGER registry_log_no_delete")
    out = sov.status(tmp)
    assert out["verdict"] == "UNREADABLE_SCHEMA"
    assert "trigger:registry_log_no_delete" in out["detail"]["missing"]


def test_a_file_that_is_not_sqlite_is_its_own_type(tmp_path):
    junk = tmp_path / "junk.sqlite"
    junk.write_bytes(b"this is not a database " * 40)
    out = sov.attach(tmp_path / "root", file=str(junk))
    assert out["verdict"] == "UNREADABLE_NOT_SQLITE"
    empty = tmp_path / "empty.sqlite"
    empty.write_bytes(b"")
    assert sov.attach(tmp_path / "root", file=str(empty))["verdict"] == "UNREADABLE_SCHEMA"
    assert not (tmp_path / "root").exists()     # a refused attach creates nothing


def test_shape_check_wrong_meta_store_id(tmp_path):
    """A file whose meta names another store is not read as this one."""
    assert sov.create(tmp_path, "s1", "o")["verdict"] == "CREATED"
    other = tmp_path / "stores" / "s2.sqlite"
    other.write_bytes((tmp_path / "stores" / "s1.sqlite").read_bytes())
    # register s2 in a root whose file is actually s1's bytes: the read must refuse
    r3 = tmp_path / "r3"
    sov.create(r3, "s2", "o")
    (r3 / "stores" / "s2.sqlite").write_bytes(other.read_bytes())
    with pytest.raises(sov.SchemaMismatch) as e:
        sov.open_ledger(r3, "s2")
    assert e.value.detail["meta_store_id"] == "s1"


def test_the_new_code_never_deletes_or_drops_and_uses_no_clock_or_randomness():
    """The Vera code path has no way to remove a file or a row (test-only DROPs live in tests, not here)."""
    text = SOV_SRC.read_text(encoding="utf-8")
    marker = "# 記憶のソブリン (W4-m)"
    assert text.count(marker) == 1
    mine = text[text.index(marker):]
    for pat in (r"\.unlink\(", r"os\.remove", r"os\.unlink", r"rmtree", r"os\.rmdir", r"\.rmdir\(",
                r"DROP\s+(TABLE|TRIGGER|INDEX)", r"DELETE\s+FROM", r"VACUUM", r"journal_mode",
                r"\buuid\b", r"\brandom\b", r"datetime\.now\(\)", r"time\.strftime", r"os\.rename",
                r"shutil\.move"):
        assert not re.search(pat, mine), pat
