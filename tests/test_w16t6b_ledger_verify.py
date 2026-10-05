"""W16-t6b (K605/K606): `vera attest --ledger` uses an events ledger only if T7's own verify (ledger_events.verify) says OK.

Every ledger below is in the T7 layout (<dir>/events.jsonl + <dir>/HEAD). A correct ledger is made with ledger_events.append;
a tampered one is made by editing its bytes (and, for the "recomputed" forms, by recomputing the chain with T7's own rule).

Known limit, written as an expectation (test_replace_recomputed_with_head_not_pinned_is_still_record):
without a pinned HEAD, a ledger whose every row AND the HEAD file are recomputed by the T7 rule verifies OK (that is a property of T7),
so attest cannot tell it from the original. Only `ledger_head` (API) closes it.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from verantyx import attest, ledger_events as LE
from verantyx.attest import MISMATCH, RECORD, TESTIMONY, Verifier

ROOT = str(Path(__file__).resolve().parent.parent)
ACT = {"type": "agent", "id": "t"}
CMD_A = "python -m pytest -q tests/test_a.py -p no:cacheprovider"
CMD_B = "python -m x run"


@pytest.fixture
def tree(tmp_path):
    t = tmp_path / "tree"
    (t / "tests").mkdir(parents=True)
    (t / "tests" / "test_a.py").write_text("def test_a():\n    assert True\n")
    (t / "pytest.ini").write_text("")
    return str(t)


def make(tmp_path, name, events):
    d = tmp_path / name
    for kind, data in events:
        LE.append(d, kind, ACT, data)
    return d


def three(tmp_path, name="led"):
    return make(tmp_path, name, [("test_run", {"cmd": CMD_A, "exit_code": 0}), ("test_run", {"cmd": CMD_B, "exit_code": 3}),
                                 ("test_run", {"cmd": "python -m y run", "exit_code": 0})])


def rows_of(d):
    return [json.loads(ln) for ln in (Path(d) / "events.jsonl").read_text().splitlines() if ln.strip()]


def write_rows(d, rows, head="last"):
    """Write rows as given; head: 'last' = HEAD file becomes the last row's sha, None = leave HEAD, 'none' = delete HEAD, else the string."""
    d = Path(d)
    (d / "events.jsonl").write_text("".join(LE.canonical(r) + "\n" for r in rows))
    if head == "last":
        (d / "HEAD").write_text(rows[-1]["sha"] + "\n")
    elif head == "none":
        (d / "HEAD").unlink()
    elif head is not None:
        (d / "HEAD").write_text(head + "\n")


def recompute(rows):
    """Re-chain rows with T7's rule (the tamperer knows the rule)."""
    out, prev = [], LE.GENESIS
    for r in rows:
        r = dict(r, prev=prev)
        r["sha"] = LE.sha_of(r)
        out.append(r)
        prev = r["sha"]
    return out


def head_of(d):
    return (Path(d) / "HEAD").read_text().strip()


def evpath(d):
    return str(Path(d) / "events.jsonl")


def fact(tree, d, cmd, code, head=None, path=None):
    kw = {"ledger": path or evpath(d)}
    if head is not None:
        kw["ledger_head"] = head
    return Verifier(tree, **kw).exit_fact(cmd, code)


def unverified(f, *types):
    assert (f["mark"], f["reason"]) == (TESTIMONY, "LEDGER_UNVERIFIED"), f
    got = {p["type"] for p in f["evidence"]["problems"]}
    for t in types:
        assert t in got, (t, f["evidence"])
    assert f["evidence"]["status"] != "OK"
    return f


def a16(tmp_path, name="a16", cmd=CMD_B, code=0):
    """The attack's shape: a genesis `prev: null`, sha by an assumed rule, actor a dict, a HEAD file holding that sha."""
    d = tmp_path / name
    d.mkdir()
    r = {"ts": "2026-10-06T00:00:00Z", "kind": "test_run", "actor": ACT, "data": {"cmd": cmd, "exit_code": code}, "prev": None}
    r["sha"] = hashlib.sha256(json.dumps({k: v for k, v in r.items() if k != "sha"}, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    write_rows(d, [r])
    return d


# ---------------------------------------------------------------- the attack and its variants
def test_a16_null_genesis_is_not_a_record(tree, tmp_path):
    d = a16(tmp_path)
    assert LE.verify(d)["status"] == "TAMPERED"
    f = unverified(fact(tree, d, CMD_B, 0), "BAD_SHAPE", "PREV_MISMATCH")
    assert {(p["type"], p["line"]) for p in f["evidence"]["problems"]} >= {("BAD_SHAPE", 1), ("PREV_MISMATCH", 1)}
    assert f["evidence"]["ledger"] == evpath(d)


@pytest.mark.parametrize("variant", ["prev_empty", "actor_str", "kind_note", "extra_key", "prev_zero_but_actor_str"])
def test_a16_variants_are_not_records(tree, tmp_path, variant):
    d = a16(tmp_path, "v_" + variant)
    r = rows_of(d)[0]
    if variant == "prev_empty":
        r["prev"] = ""
    elif variant == "actor_str":
        r["actor"] = "synth"
    elif variant == "kind_note":
        r["kind"] = "note"
        r["data"] = {"cmd": CMD_B, "exit_code": 0}
    elif variant == "extra_key":
        r["extra"] = 1
    elif variant == "prev_zero_but_actor_str":
        r["prev"] = LE.GENESIS
        r["actor"] = "x"
    r["sha"] = hashlib.sha256(json.dumps({k: v for k, v in r.items() if k != "sha"}, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    write_rows(d, [r])
    assert LE.verify(d)["status"] != "OK"
    f = fact(tree, d, CMD_B, 0)
    want = "PREV_MISMATCH" if variant == "prev_empty" else "BAD_SHAPE"        # prev "" is a string (shape ok) but is not T7's genesis
    unverified(f, want)
    assert {(p["type"], p["line"]) for p in f["evidence"]["problems"]} >= {(want, 1)}


def test_replace_recomputed_head_untouched(tree, tmp_path):
    d = three(tmp_path)
    orig_head = head_of(d)
    rows = rows_of(d)
    rows[1]["data"] = {"cmd": CMD_B, "exit_code": 0}
    write_rows(d, recompute(rows), head=None)
    assert head_of(d) == orig_head
    f = unverified(fact(tree, d, CMD_B, 0), "HEAD_MISMATCH")
    assert any(p.get("HEAD_NOT_IN_CHAIN") for p in f["evidence"]["problems"])


def test_delete_recomputed_head_untouched(tree, tmp_path):
    d = three(tmp_path)
    rows = rows_of(d)
    del rows[1]
    write_rows(d, recompute(rows), head=None)
    f = unverified(fact(tree, d, CMD_A, 0), "HEAD_MISMATCH")
    assert f["evidence"]["status"] == "HEAD_MISMATCH"


def test_reorder_recomputed_head_untouched(tree, tmp_path):
    d = three(tmp_path)
    rows = rows_of(d)
    rows[0], rows[1] = rows[1], rows[0]
    write_rows(d, recompute(rows), head=None)
    unverified(fact(tree, d, CMD_B, 3), "HEAD_MISMATCH")


def test_truncate_tail_head_untouched(tree, tmp_path):
    d = three(tmp_path)
    rows = rows_of(d)[:-1]
    write_rows(d, rows, head=None)
    f = unverified(fact(tree, d, CMD_B, 3), "HEAD_MISMATCH")
    assert any(p.get("HEAD_POINTS_TO_LINE") is None and p.get("HEAD_NOT_IN_CHAIN") for p in f["evidence"]["problems"])


def test_truncate_with_head_rewritten_is_caught_by_pinned_head(tree, tmp_path):
    d = three(tmp_path)
    pinned = head_of(d)
    rows = rows_of(d)[:-1]
    write_rows(d, rows, head="last")
    assert LE.verify(d)["status"] == "OK"
    f = unverified(fact(tree, d, CMD_B, 3, head=pinned), "EXPECTED_HEAD_MISMATCH")
    assert f["evidence"]["problems"][-1]["expected"] == pinned


def test_replace_recomputed_with_head_rewritten_is_caught_by_pinned_head(tree, tmp_path):
    d = three(tmp_path)
    pinned = head_of(d)
    rows = rows_of(d)
    rows[1]["data"] = {"cmd": CMD_B, "exit_code": 0}
    write_rows(d, recompute(rows), head="last")
    assert LE.verify(d)["status"] == "OK"
    unverified(fact(tree, d, CMD_B, 0, head=pinned), "EXPECTED_HEAD_MISMATCH")


def test_replace_recomputed_with_head_not_pinned_is_still_record(tree, tmp_path):
    """KNOWN LIMIT (not fixed): T7's verify returns OK for a fully recomputed chain + HEAD; only a pinned ledger_head catches it."""
    d = three(tmp_path)
    rows = rows_of(d)
    rows[1]["data"] = {"cmd": CMD_B, "exit_code": 0}
    write_rows(d, recompute(rows), head="last")
    f = fact(tree, d, CMD_B, 0)
    assert (f["mark"], f["reason"]) == (RECORD, "MATCH")


def test_naive_edit_without_recompute_is_unverified(tree, tmp_path):
    d = three(tmp_path)
    rows = rows_of(d)
    rows[1]["data"] = {"cmd": CMD_B, "exit_code": 0}
    write_rows(d, rows, head=None)
    unverified(fact(tree, d, CMD_B, 0), "SHA_MISMATCH")


def test_missing_head_file_is_unverified(tree, tmp_path):
    d = three(tmp_path)
    (d / "HEAD").unlink()
    unverified(fact(tree, d, CMD_B, 3), "HEAD_MISSING")


def test_file_not_named_events_jsonl_is_not_verifiable(tree, tmp_path):
    d = three(tmp_path)
    copy = tmp_path / "ev.jsonl"
    copy.write_bytes((d / "events.jsonl").read_bytes())
    f = unverified(fact(tree, d, CMD_B, 3, path=str(copy)), "LEDGER_PATH_NOT_T7")
    assert f["evidence"]["ledger"] == str(copy)


def test_decoy_dir_verified_but_other_file_read_is_refused(tree, tmp_path):
    """A different file in a good ledger's dir must not be read as if it were verified."""
    d = three(tmp_path)
    other = d / "S05.ledger.jsonl"
    other.write_bytes(a16(tmp_path, "decoy_src").joinpath("events.jsonl").read_bytes())
    unverified(fact(tree, d, CMD_B, 0, path=str(other)), "LEDGER_PATH_NOT_T7")


def test_dir_argument_is_accepted_for_a_verified_ledger(tree, tmp_path):
    d = three(tmp_path)
    f = fact(tree, d, CMD_B, 3, path=str(d))
    assert (f["mark"], f["reason"], f["actual"]) == (RECORD, "MATCH", 3)
    assert f["evidence"]["sha256"] == hashlib.sha256((d / "events.jsonl").read_bytes()).hexdigest()


def test_dir_argument_of_a_tampered_ledger_is_unverified(tree, tmp_path):
    d = a16(tmp_path)
    unverified(fact(tree, d, CMD_B, 0, path=str(d)), "BAD_SHAPE")


def test_empty_ledger_is_not_verified(tree, tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    (d / "events.jsonl").write_text("")
    f = fact(tree, d, CMD_B, 0)
    assert f["mark"] == TESTIMONY and f["reason"] == "LEDGER_UNVERIFIED" and f["evidence"]["status"] == "EMPTY"


def test_missing_ledger_is_unverified(tree, tmp_path):
    f = fact(tree, tmp_path / "nope", CMD_B, 0)
    assert (f["mark"], f["reason"]) == (TESTIMONY, "LEDGER_UNVERIFIED")


def test_torn_tail_is_unverified(tree, tmp_path):
    d = three(tmp_path)
    with open(d / "events.jsonl", "ab") as fh:
        fh.write(b'{"ts":')
    f = fact(tree, d, CMD_B, 3)
    assert (f["mark"], f["reason"]) == (TESTIMONY, "LEDGER_UNVERIFIED") and f["evidence"]["status"] == "TORN_TAIL"


def test_passed_fact_from_a16_is_not_a_record(tree, tmp_path):
    d = a16(tmp_path, "a16p", cmd="pytest -q tests/test_a.py", code=0)
    v = Verifier(tree, ledger=evpath(d))
    ev = v.exit_code_for([], lambda a: attest._is_pytest_argv(a) is not None, "pytest -q tests/test_a.py", attest._passed_event_match("tests/test_a.py"))
    f = v._exit_result("test_passed:tests/test_a.py", "passed", ev, passed=True)
    unverified(f, "BAD_SHAPE")


def test_passed_fact_from_a_verified_ledger_is_a_record(tree, tmp_path):
    d = make(tmp_path, "okp", [("test_run", {"cmd": "pytest -q tests/test_a.py", "exit_code": 0})])
    v = Verifier(tree, ledger=evpath(d))
    ev = v.exit_code_for([], lambda a: attest._is_pytest_argv(a) is not None, "pytest -q tests/test_a.py", attest._passed_event_match("tests/test_a.py"))
    f = v._exit_result("test_passed:tests/test_a.py", "passed", ev, passed=True)
    assert (f["mark"], f["reason"]) == (RECORD, "MATCH")


# ---------------------------------------------------------------- the verified ledger keeps its old output
def test_good_ledger_old_behaviour_and_evidence_keys(tree, tmp_path):
    d = make(tmp_path, "good", [("test_run", {"cmd": CMD_B, "exit_code": 3}), ("process_exit", {"argv": ["python", "-m", "z"], "exit_code": 0}),
                                ("test_run", {"cmd": "python -m amb", "exit_code": 0}), ("test_run", {"cmd": "python -m amb", "exit_code": 1})])
    assert LE.verify(d)["status"] == "OK"
    f = fact(tree, d, CMD_B, 3)
    assert (f["mark"], f["reason"], f["actual"]) == (RECORD, "MATCH", 3)
    assert set(f["evidence"]) == {"path", "sha256", "event_sha"} and f["evidence"]["path"] == evpath(d)
    assert f["evidence"]["sha256"] == hashlib.sha256((d / "events.jsonl").read_bytes()).hexdigest()
    f = fact(tree, d, CMD_B, 0)
    assert (f["mark"], f["reason"], f["claimed"], f["actual"]) == (MISMATCH, "EXIT_CODE_DIFFERS", 0, 3)
    f = fact(tree, d, "python -m amb", 0)
    assert (f["mark"], f["reason"], f["evidence"]) == (TESTIMONY, "AMBIGUOUS_EVENT", None)
    f = fact(tree, d, "python -m other", 0)
    assert (f["mark"], f["reason"], f["evidence"]) == (TESTIMONY, "NO_EVENT", None)


def test_no_ledger_is_no_event_with_no_evidence(tree):
    f = Verifier(tree).exit_fact(CMD_B, 0)
    assert (f["mark"], f["reason"], f["evidence"]) == (TESTIMONY, "NO_EVENT", None)


def test_unverified_ledger_with_rerun_falls_back_to_rerun(tree, tmp_path, monkeypatch):
    d = a16(tmp_path, "a16r", cmd="pytest -q tests/test_a.py", code=1)
    calls = []
    monkeypatch.setattr(attest, "_spawn", lambda *a, **k: (calls.append(a) or (0, b"", b"")))
    f = Verifier(tree, ledger=evpath(d), rerun=True).exit_fact("pytest -q tests/test_a.py", 0)
    assert f["mark"] == RECORD and len(calls) == 1 and "stdout_sha256" in f["evidence"]


def test_flags_keys_unchanged_when_no_pinned_head(tree):
    out = attest.run_attest("完了:\n- x\n", tree)
    assert set(out["flags"]) == {"ledger", "rerun", "base", "rev", "extractors", "partial_tree", "search_dirs", "history"}
    out = attest.run_attest("完了:\n- x\n", tree, ledger_head="a" * 64)
    assert out["flags"]["ledger_head"] == "a" * 64


# ---------------------------------------------------------------- through the CLI (cli_main)
REPORT = "完了:\n- 受入 A1: `%s` を実行し、終了コード 0\n" % CMD_A


def _cli(tmp_path, tree, ledger):
    rep = tmp_path / "rep.md"
    rep.write_text(REPORT)
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run([sys.executable, "-P", "-m", "verantyx.cli", "attest", str(rep), "--tree", tree, "--ledger", ledger, "--json"],
                          capture_output=True, text=True, env=env, cwd=ROOT, timeout=300)


def _facts(p):
    res = json.loads(p.stdout)
    out = []
    for ex in res["extractors"].values():
        for c in ex["claims"] if isinstance(ex, dict) and "claims" in ex else ex:
            out.extend(c["facts"])
    return out


def test_cli_a16_is_testimony_exit_4(tree, tmp_path):
    d = a16(tmp_path, "cli16", cmd=CMD_A, code=0)
    p = _cli(tmp_path, tree, evpath(d))
    assert p.returncode == 4, p.stderr[-400:] + p.stdout[-400:]
    ex = [f for f in _facts(p) if f["fact"].startswith("exit:")]
    assert ex and all((f["mark"], f["reason"]) == (TESTIMONY, "LEDGER_UNVERIFIED") for f in ex)


def test_cli_verified_ledger_stays_record_exit_0(tree, tmp_path):
    d = make(tmp_path, "cligood", [("test_run", {"cmd": CMD_A, "exit_code": 0})])
    p = _cli(tmp_path, tree, evpath(d))
    assert p.returncode == 0, p.stderr[-400:] + p.stdout[-400:]
    ex = [f for f in _facts(p) if f["fact"].startswith("exit:")]
    assert ex and all((f["mark"], f["reason"]) == (RECORD, "MATCH") for f in ex)
