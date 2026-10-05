"""W16-t6b round 2: `vera attest --ledger-head SHA` through the real CLI (subprocess, `-P`, PYTHONPATH = this tree).

A forged ledger whose every row and HEAD are recomputed by T7's own rule verifies OK for T7 (a property of T7);
only a HEAD pinned out of band (`--ledger-head`) catches it. Test 2 states that limit as an expectation (disclosure, not a weakening).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from verantyx import ledger_events as LE
from verantyx.attest import RECORD, TESTIMONY, MISMATCH

ROOT = str(Path(__file__).resolve().parent.parent)
ACT = {"type": "agent", "id": "t"}
CMD_A = "python -m pytest -q tests/test_a.py -p no:cacheprovider"
CMD_B = "python -m x run"
REPORT = "完了:\n- 受入 A1: `%s` を実行し、終了コード 0\n" % CMD_A


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


def rows_of(d):
    return [json.loads(ln) for ln in (Path(d) / "events.jsonl").read_text().splitlines() if ln.strip()]


def head_of(d):
    return (Path(d) / "HEAD").read_text().strip()


def write_rows_recomputed(d, rows):
    """Re-chain rows with T7's rule AND rewrite HEAD to the last sha (what a careful forger does)."""
    out, prev = [], LE.GENESIS
    for r in rows:
        r = dict(r, prev=prev)
        r["sha"] = LE.sha_of(r)
        out.append(r)
        prev = r["sha"]
    (Path(d) / "events.jsonl").write_text("".join(LE.canonical(r) + "\n" for r in out))
    (Path(d) / "HEAD").write_text(out[-1]["sha"] + "\n")


def run_cli(tmp_path, tree, d, head=None):
    rep = tmp_path / "rep.md"
    rep.write_text(REPORT)
    cmd = [sys.executable, "-P", "-m", "verantyx.cli", "attest", str(rep), "--tree", tree,
           "--ledger", str(Path(d) / "events.jsonl"), "--json"]
    if head is not None:
        cmd += ["--ledger-head", head]
    env = dict(os.environ, PYTHONPATH=ROOT, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(tmp_path), timeout=300)


def facts(p):
    res = json.loads(p.stdout)
    out = []
    for ex in res["extractors"].values():
        for c in ex["claims"] if isinstance(ex, dict) and "claims" in ex else ex:
            out.extend(c["facts"])
    return [f for f in out if f["fact"].startswith("exit:")], res


def forged(tmp_path, name):
    """True ledger says CMD_A exited 3; the forger rewrites it to 0, recomputes every sha and HEAD."""
    d = make(tmp_path, name, [("test_run", {"cmd": CMD_A, "exit_code": 3}), ("test_run", {"cmd": CMD_B, "exit_code": 0})])
    pinned = head_of(d)
    rows = rows_of(d)
    rows[0]["data"] = {"cmd": CMD_A, "exit_code": 0}
    write_rows_recomputed(d, rows)
    assert LE.verify(d)["status"] == "OK"        # T7 alone is fooled
    return d, pinned


def test_cli_recomputed_forgery_with_pinned_head_is_unverified(tree, tmp_path):
    d, pinned = forged(tmp_path, "f1")
    p = run_cli(tmp_path, tree, d, head=pinned)
    assert p.returncode == 4, p.stderr[-400:] + p.stdout[-400:]
    ex, _ = facts(p)
    assert ex and all((f["mark"], f["reason"]) == (TESTIMONY, "LEDGER_UNVERIFIED") for f in ex)
    assert all("EXPECTED_HEAD_MISMATCH" in {x["type"] for x in f["evidence"]["problems"]} for f in ex)


def test_cli_recomputed_forgery_without_head_is_still_record(tree, tmp_path):
    """KNOWN LIMIT (disclosed, not fixed): without a pinned HEAD a fully recomputed forgery passes T7's verify, so the forged exit code is a RECORD."""
    d, _ = forged(tmp_path, "f2")
    p = run_cli(tmp_path, tree, d)
    ex, _ = facts(p)
    assert ex and all((f["mark"], f["reason"]) == (RECORD, "MATCH") for f in ex)


def test_cli_truncated_with_pinned_head_is_unverified(tree, tmp_path):
    d = make(tmp_path, "t3", [("test_run", {"cmd": CMD_A, "exit_code": 0}), ("test_run", {"cmd": CMD_B, "exit_code": 0})])
    pinned = head_of(d)
    rows = rows_of(d)[:-1]
    (d / "events.jsonl").write_text("".join(LE.canonical(r) + "\n" for r in rows))
    (d / "HEAD").write_text(rows[-1]["sha"] + "\n")
    assert LE.verify(d)["status"] == "OK"
    p = run_cli(tmp_path, tree, d, head=pinned)
    assert p.returncode == 4, p.stderr[-400:] + p.stdout[-400:]
    ex, _ = facts(p)
    assert ex and all((f["mark"], f["reason"]) == (TESTIMONY, "LEDGER_UNVERIFIED") for f in ex)
    assert all("EXPECTED_HEAD_MISMATCH" in {x["type"] for x in f["evidence"]["problems"]} for f in ex)


def test_cli_correct_head_keeps_record(tree, tmp_path):
    d = make(tmp_path, "t4", [("test_run", {"cmd": CMD_A, "exit_code": 0})])
    pinned = head_of(d)
    p = run_cli(tmp_path, tree, d, head=pinned)
    assert p.returncode == 0, p.stderr[-400:] + p.stdout[-400:]
    ex, res = facts(p)
    assert ex and all((f["mark"], f["reason"]) == (RECORD, "MATCH") for f in ex)
    assert res["flags"]["ledger_head"] == pinned


def test_cli_no_head_flag_adds_no_key(tree, tmp_path):
    d = make(tmp_path, "t5", [("test_run", {"cmd": CMD_A, "exit_code": 0})])
    p = run_cli(tmp_path, tree, d)
    _, res = facts(p)
    assert "ledger_head" not in res["flags"]
