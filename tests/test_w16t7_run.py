"""W16-t7 K701 / T7-1(a): vera run が子孫を含めてプロセスの開始・終了・中断・孤児を台帳に残す。sweep が後で孤児の終了を拾う。"""
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JOB = "sleep 20 & sleep 20 & wait"


def _env():
    e = dict(os.environ)
    e["PYTHONPATH"] = str(ROOT)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


def cli(*args, cwd=None):
    return subprocess.run([sys.executable, "-m", "verantyx.cli", *args], capture_output=True, text=True,
                          env=_env(), cwd=str(cwd or tempfile.gettempdir()))


def lstart(pid):
    r = subprocess.run(["ps", "-p", str(pid), "-o", "lstart="], capture_output=True, text=True)
    return " ".join(r.stdout.split()) if r.returncode == 0 and r.stdout.strip() else None


def rows(d):
    p = Path(d) / "events.jsonl"
    if not p.exists():
        return []
    return [json.loads(x) for x in p.read_text(encoding="utf-8").split("\n") if x.strip()]


def wait_for(cond, timeout=20.0, step=0.1):
    t = time.time() + timeout
    while time.time() < t:
        v = cond()
        if v:
            return v
        time.sleep(step)
    return None


def start_job(d, extra=()):
    p = subprocess.Popen([sys.executable, "-m", "verantyx.cli", "run", "--ledger-dir", str(d), "--label", "demo",
                          "--sample-interval", "0.2", *extra, "--", "sh", "-c", JOB],
                         env=_env(), cwd=tempfile.gettempdir(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    start = wait_for(lambda: next((r for r in rows(d) if r["kind"] == "process_start"), None))
    assert start, "process_start が出ない"
    rid = start["data"]["run_id"]
    sf = Path(d) / "runs" / f"{rid}.json"

    def two():
        try:
            return len(json.loads(sf.read_text())["descendants"]) >= 2
        except Exception:
            return False
    assert wait_for(two), "子孫が 2 つ採取されない"
    return p, start["data"], sf


def kill_ours(pairs):
    """テストが自分で作った (pid, lstart) だけを止める。pkill/killall は使わない。"""
    for pid, ls in pairs:
        if pid and ls and lstart(pid) == ls:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass


def ours(d, p, sdata, sf):
    out = {(sdata["pid"], sdata["lstart"]), (p.pid, lstart(p.pid))}
    try:
        for x in json.loads(sf.read_text())["descendants"]:
            out.add((x["pid"], x["lstart"]))
    except Exception:
        pass
    for r in rows(d):
        if r["kind"] == "process_orphaned":
            out.add((r["data"]["pid"], r["data"]["lstart"]))
    return {(a, b) for a, b in out if a and b}       # lstart を確かめられないもの（もう居ない）は対象外


def end_rows(d, rid):
    return [r for r in rows(d) if r["data"].get("run_id") == rid and (
        r["kind"] == "process_interrupted" or (r["kind"] == "process_exit" and "pid" not in r["data"]))]


def orphan_rows(d, rid):
    return [r for r in rows(d) if r["kind"] == "process_orphaned" and r["data"].get("run_id") == rid]


def sweep_exits(d, rid):
    return [r for r in rows(d) if r["kind"] == "process_exit" and r["data"].get("run_id") == rid and "pid" in r["data"]]


def all_gone(pairs):
    return wait_for(lambda: all(lstart(pid) != ls for pid, ls in pairs), timeout=10)


def test_normal_exit_code(tmp_path):
    d = tmp_path / "l"
    r = cli("run", "--ledger-dir", str(d), "--label", "L", "--", "sh", "-c", "exit 3")
    assert r.returncode == 3, r.stderr
    ks = [x["kind"] for x in rows(d)]
    assert ks == ["process_start", "process_exit"]
    ex = rows(d)[1]["data"]
    assert ex["exit_code"] == 3 and ex["duration_s"] >= 0
    assert rows(d)[0]["data"]["label"] == "L" and rows(d)[0]["data"]["run_id"] == ex["run_id"]


def test_argv_and_store_before_subcommand(tmp_path):
    d = tmp_path / "l"
    r = cli("run", "--ledger-dir", str(d), "--", "echo", "hi")
    assert r.returncode == 0
    assert rows(d)[0]["data"]["argv0"] == "echo"
    r = cli("--store", str(tmp_path / "s.json"), "run", "--ledger-dir", str(d), "--", "sh", "-c", "exit 0")
    assert r.returncode == 0
    assert len([x for x in rows(d) if x["kind"] == "process_start"]) == 2


def test_no_command(tmp_path):
    r = cli("run", "--ledger-dir", str(tmp_path / "l"))
    assert r.returncode == 2 and "NO_COMMAND" in r.stdout + r.stderr


def test_job_sigterm_then_sweep(tmp_path):
    d = tmp_path / "l"
    p, s, sf = start_job(d)
    try:
        os.kill(s["pid"], signal.SIGTERM)
        assert p.wait(timeout=15) == 128 + signal.SIGTERM
        rid = s["run_id"]
        e = end_rows(d, rid)
        assert len(e) == 1 and e[0]["kind"] == "process_interrupted"
        assert e[0]["data"]["signal"] == "SIGTERM" and e[0]["data"]["target"] == "job"
        o = orphan_rows(d, rid)
        assert len(o) == 2 and all(x["data"]["lstart"] and x["data"]["pid"] for x in o)
        sw = json.loads(cli("events", "sweep", "--ledger-dir", str(d)).stdout.strip().splitlines()[-1])
        assert sw["appended"] == 0 and len(sw["still_alive"]) == 2      # まだ生きている
    finally:
        pairs = ours(d, p, s, sf)
        kill_ours(pairs)
    assert all_gone(pairs)
    sw = json.loads(cli("events", "sweep", "--ledger-dir", str(d)).stdout.strip().splitlines()[-1])
    assert sw["appended"] == 2 and sw["still_alive"] == []
    ex = sweep_exits(d, s["run_id"])
    assert len(ex) == 2 and all(x["data"]["exit_code"] is None and x["data"]["exit_code_status"] == "UNOBSERVABLE_NOT_A_CHILD" for x in ex)
    n = len(rows(d))
    sw = json.loads(cli("events", "sweep", "--ledger-dir", str(d)).stdout.strip().splitlines()[-1])
    assert sw["appended"] == 0 and len(rows(d)) == n                      # 冪等
    v = cli("events", "verify", "--ledger-dir", str(d))
    assert v.returncode == 0 and '"OK"' in v.stdout


def test_job_sigkill(tmp_path):
    d = tmp_path / "l"
    p, s, sf = start_job(d)
    try:
        os.kill(s["pid"], signal.SIGKILL)
        assert p.wait(timeout=15) == 128 + signal.SIGKILL
        e = end_rows(d, s["run_id"])
        assert len(e) == 1 and e[0]["kind"] == "process_interrupted" and e[0]["data"]["signal"] == "SIGKILL"
        assert len(orphan_rows(d, s["run_id"])) == 2
    finally:
        pairs = ours(d, p, s, sf)
        kill_ours(pairs)
    assert all_gone(pairs)
    cli("events", "sweep", "--ledger-dir", str(d))
    assert len(sweep_exits(d, s["run_id"])) == 2
    assert cli("events", "verify", "--ledger-dir", str(d)).returncode == 0


def test_recorder_sigterm(tmp_path):
    d = tmp_path / "l"
    p, s, sf = start_job(d)
    try:
        os.kill(p.pid, signal.SIGTERM)
        assert p.wait(timeout=20) == 128 + signal.SIGTERM
        e = end_rows(d, s["run_id"])
        assert len(e) == 1 and e[0]["kind"] == "process_interrupted"
        assert e[0]["data"]["target"] == "recorder" and e[0]["data"]["signal"] == "SIGTERM"
        assert len(orphan_rows(d, s["run_id"])) >= 2
    finally:
        pairs = ours(d, p, s, sf)
        kill_ours(pairs)
    assert all_gone(pairs)
    cli("events", "sweep", "--ledger-dir", str(d))
    assert len(sweep_exits(d, s["run_id"])) >= 2
    assert cli("events", "verify", "--ledger-dir", str(d)).returncode == 0


def test_recorder_sigkill_then_sweep(tmp_path):
    d = tmp_path / "l"
    p, s, sf = start_job(d)
    pairs = set()
    try:
        rec = (p.pid, lstart(p.pid))
        os.kill(p.pid, signal.SIGKILL)
        p.wait(timeout=15)
        assert [r["kind"] for r in rows(d)] == ["process_start"]
        sw = json.loads(cli("events", "sweep", "--ledger-dir", str(d)).stdout.strip().splitlines()[-1])
        assert sw["recorder_vanished"] == 1
        rid = s["run_id"]
        e = [r for r in rows(d) if r["kind"] == "process_interrupted"]
        assert len(e) == 1 and e[0]["data"]["cause"] == "RECORDER_VANISHED" and e[0]["data"]["target"] == "recorder"
        o = orphan_rows(d, rid)
        assert len(o) >= 3 and {(x["data"]["pid"]) for x in o} >= {s["pid"]}       # ジョブ自身と 2 つの子孫
        again = json.loads(cli("events", "sweep", "--ledger-dir", str(d)).stdout.strip().splitlines()[-1])
        assert again["appended"] == 0 and again["recorder_vanished"] == 0
    finally:
        pairs = ours(d, p, s, sf)
        kill_ours(pairs)
    assert all_gone(pairs)
    cli("events", "sweep", "--ledger-dir", str(d))
    assert len(sweep_exits(d, s["run_id"])) >= 3
    assert cli("events", "verify", "--ledger-dir", str(d)).returncode == 0


def test_pid_reuse_is_not_alive(tmp_path):
    """pid だけで生死を判定しない: lstart が違う pid は『居ない』。"""
    from verantyx import ledger_events as L
    d = tmp_path / "l"
    L.append(d, "process_start", {"type": "process", "id": "1"}, {"run_id": "r1", "pid": 1, "lstart": "Mon Jan  1 00:00:00 2001",
             "recorder_pid": os.getpid(), "recorder_lstart": lstart(os.getpid()), "redactions": 0})
    L.append(d, "process_interrupted", {"type": "process", "id": "1"}, {"run_id": "r1", "signal": "SIGTERM", "target": "job"})
    L.append(d, "process_orphaned", {"type": "process", "id": "1"}, {"run_id": "r1", "pid": 1, "lstart": "Mon Jan  1 00:00:00 2001",
             "argv0": "launchd", "cmd_sha256": "0" * 64})
    sw = json.loads(cli("events", "sweep", "--ledger-dir", str(d)).stdout.strip().splitlines()[-1])
    assert sw["appended"] == 1 and sw["still_alive"] == []           # pid 1 は居るが lstart が違う


# ---- 第 2 ラウンド追加（レビュー必須 2）: 追記できない台帳では子を起動しない／起動後の追記失敗で落ちない -------
def _blocked_ledgers(tmp_path):
    torn = tmp_path / "torn"
    torn.mkdir()
    (torn / "events.jsonl").write_text('{"ts":"x')
    filed = tmp_path / "filed"
    filed.write_text("i am a file")
    return {"torn": (torn, "TORN_TAIL_BLOCKS_APPEND"), "file": (filed / "sub", "LEDGER_NOT_WRITABLE")}


@pytest.mark.parametrize("which", ["torn", "file"])
def test_blocked_ledger_does_not_start_child(tmp_path, which):
    d, code = _blocked_ledgers(tmp_path)[which]
    marker = tmp_path / "marker"
    r = cli("run", "--ledger-dir", str(d), "--", "sh", "-c", f"touch {marker}")
    assert r.returncode != 0
    assert code in r.stderr and "Traceback" not in r.stderr
    assert not marker.exists()


def test_secret_label_does_not_traceback_and_child_runs_recorded(tmp_path):
    d = tmp_path / "l"
    r = cli("run", "--ledger-dir", str(d), "--label", "token:\nabcdefg", "--", "sh", "-c", "exit 0")
    assert r.returncode == 0 and "Traceback" not in r.stderr
    assert [x["kind"] for x in rows(d)] == ["process_start", "process_exit"]


def test_append_failure_after_start_is_typed_not_traceback(tmp_path):
    d = tmp_path / "l"
    # 子が台帳の最終行を壊す（起動前の検査は通り、起動後の追記が TORN_TAIL で失敗する）
    r = cli("run", "--ledger-dir", str(d), "--", "sh", "-c", f"printf '{{\"ts\":\"x' >> {d}/events.jsonl; exit 5")
    assert "Traceback" not in r.stderr
    assert r.returncode == 5, (r.returncode, r.stderr)
    assert "LEDGER_APPEND_FAILED_AFTER_START" in r.stderr and "TORN_TAIL_BLOCKS_APPEND" in r.stderr
