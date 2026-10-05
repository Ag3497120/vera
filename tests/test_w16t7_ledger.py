"""W16-t7 K700 / T7-1(c): 追記専用・ハッシュ連鎖の台帳。改ざんの検出。"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _env():
    e = dict(os.environ)
    e["PYTHONPATH"] = str(ROOT)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


def cli(*args, input=None, cwd=None):
    return subprocess.run([sys.executable, "-m", "verantyx.cli", *args], capture_output=True,
                          text=True, input=input, env=_env(), cwd=str(cwd or tempfile.gettempdir()))


@pytest.fixture
def led(tmp_path):
    from verantyx import ledger_events as L
    d = tmp_path / "led"
    for i in range(3):
        L.append(d, "approval", {"type": "owner", "id": "o"}, {"text": f"ok {i}", "redactions": 0})
    return d


def _lines(d):
    return (d / "events.jsonl").read_text(encoding="utf-8").split("\n")


def _types(v):
    return {p["type"] for p in v["problems"]}


def test_row_shape_and_chain(led):
    from verantyx import ledger_events as L
    rows = L.read_events(led)
    assert len(rows) == 3
    assert all(set(r) == {"ts", "kind", "actor", "data", "prev", "sha"} for r in rows)
    assert rows[0]["prev"] == "0" * 64 == L.GENESIS
    assert rows[1]["prev"] == rows[0]["sha"]
    assert (led / "HEAD").read_text().strip() == rows[2]["sha"]
    assert L.verify(led)["status"] == "OK"
    assert L.verify(led)["n"] == 3
    assert set(L.KINDS) == {"owner_utterance", "agent_stop", "tool_call", "process_start", "process_exit",
                            "process_interrupted", "process_orphaned", "approval", "commit", "test_run"}


def test_empty(tmp_path):
    from verantyx import ledger_events as L
    d = tmp_path / "e"
    d.mkdir()
    assert L.verify(d)["status"] == "EMPTY"


def test_rewrite_is_sha_mismatch(led):
    from verantyx import ledger_events as L
    ls = _lines(led)
    ls[1] = ls[1].replace("ok 1", "ok X")
    (led / "events.jsonl").write_text("\n".join(ls), encoding="utf-8")
    v = L.verify(led)
    assert v["status"] == "TAMPERED" and "SHA_MISMATCH" in _types(v)


def test_delete_middle_is_prev_mismatch(led):
    from verantyx import ledger_events as L
    ls = _lines(led)
    del ls[1]
    (led / "events.jsonl").write_text("\n".join(ls), encoding="utf-8")
    v = L.verify(led)
    assert v["status"] == "TAMPERED" and "PREV_MISMATCH" in _types(v)


def test_swap_is_prev_mismatch(led):
    from verantyx import ledger_events as L
    ls = _lines(led)
    ls[0], ls[1] = ls[1], ls[0]
    (led / "events.jsonl").write_text("\n".join(ls), encoding="utf-8")
    v = L.verify(led)
    assert v["status"] == "TAMPERED" and "PREV_MISMATCH" in _types(v)


def test_truncate_tail_head_untouched(led):
    from verantyx import ledger_events as L
    ls = [x for x in _lines(led) if x]
    (led / "events.jsonl").write_text("\n".join(ls[:2]) + "\n", encoding="utf-8")
    v = L.verify(led)
    assert v["status"] == "HEAD_MISMATCH"
    assert not (_types(v) - {"HEAD_MISMATCH"})
    mm = [p for p in v["problems"] if p["type"] == "HEAD_MISMATCH"][0]
    assert "HEAD_NOT_IN_CHAIN" in json.dumps(mm) or "HEAD_POINTS_TO_LINE" in json.dumps(mm)


def test_extra_after_head_points_to_line(led):
    from verantyx import ledger_events as L
    head = (led / "HEAD").read_text().strip()
    rows = L.read_events(led)
    (led / "HEAD").write_text(rows[0]["sha"] + "\n")
    v = L.verify(led)
    assert v["status"] == "HEAD_MISMATCH"
    assert "HEAD_POINTS_TO_LINE" in json.dumps(v)
    assert head != rows[0]["sha"]


def test_torn_tail(led):
    from verantyx import ledger_events as L
    ls = [x for x in _lines(led) if x]
    (led / "events.jsonl").write_text("\n".join(ls[:2]) + "\n" + ls[2][:40], encoding="utf-8")
    v = L.verify(led)
    assert "TORN_TAIL" in _types(v)
    assert v["status"] != "OK"


def test_unparsable_middle(led):
    from verantyx import ledger_events as L
    ls = _lines(led)
    ls[1] = "{not json"
    (led / "events.jsonl").write_text("\n".join(ls), encoding="utf-8")
    assert "LINE_UNPARSABLE" in _types(L.verify(led))


def test_bad_shape_extra_key(led):
    from verantyx import ledger_events as L
    ls = _lines(led)
    r = json.loads(ls[2])
    r["extra"] = 1
    ls[2] = json.dumps(r, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    (led / "events.jsonl").write_text("\n".join(ls), encoding="utf-8")
    assert "BAD_SHAPE" in _types(L.verify(led))


def test_head_missing(led):
    from verantyx import ledger_events as L
    (led / "HEAD").unlink()
    v = L.verify(led)
    assert "HEAD_MISSING" in json.dumps(v) and v["status"] != "OK"


def test_expected_head(led):
    from verantyx import ledger_events as L
    assert L.verify(led, expected_head=(led / "HEAD").read_text().strip())["status"] == "OK"
    v = L.verify(led, expected_head="f" * 64)
    assert v["status"] != "OK" and "EXPECTED_HEAD_MISMATCH" in json.dumps(v)


def test_unknown_kind_and_actor_rejected(tmp_path):
    from verantyx import ledger_events as L
    with pytest.raises(Exception) as e:
        L.append(tmp_path / "x", "made_up_kind", {"type": "owner", "id": "o"}, {})
    assert "UNKNOWN_KIND" in str(e.value) or "UNKNOWN_KIND" in type(e.value).__name__ or getattr(e.value, "code", "") == "UNKNOWN_KIND"
    with pytest.raises(Exception):
        L.append(tmp_path / "x", "approval", {"type": "robot", "id": "o"}, {})


def test_cli_verify_exit_codes_and_tamper(tmp_path):
    d = tmp_path / "c"
    for i in range(3):
        r = cli("events", "--ledger-dir", str(d), "add", "approval", "--actor-type", "owner", "--actor-id", "o", "--text", f"ok {i}")
        assert r.returncode == 0, r.stderr
    r = cli("events", "--ledger-dir", str(d), "verify")
    assert r.returncode == 0 and json.loads(r.stdout.strip().splitlines()[-1])["status"] == "OK"
    ls = (d / "events.jsonl").read_text().split("\n")
    del ls[1]
    (d / "events.jsonl").write_text("\n".join(ls))
    r = cli("events", "verify", "--ledger-dir", str(d))
    assert r.returncode == 1 and "PREV_MISMATCH" in r.stdout


def test_cli_tail_show_grep(tmp_path):
    d = tmp_path / "q"
    for i in range(3):
        cli("events", "add", "approval", "--ledger-dir", str(d), "--actor-type", "owner", "--actor-id", "o", "--text", f"ok {i}")
    cli("events", "add", "agent_stop", "--ledger-dir", str(d), "--actor-type", "agent", "--actor-id", "a")
    out = cli("events", "tail", "-n", "2", "--ledger-dir", str(d)).stdout.strip().splitlines()
    assert len(out) == 2 and json.loads(out[-1])["kind"] == "agent_stop"
    g = cli("events", "grep", "approval", "--ledger-dir", str(d)).stdout.strip().splitlines()
    assert len(g) == 3
    sha = json.loads(g[0])["sha"]
    s = cli("events", "show", sha[:8], "--ledger-dir", str(d))
    assert s.returncode == 0 and json.loads(s.stdout.strip().splitlines()[0])["sha"] == sha
    nf = cli("events", "show", "deadbeefdeadbeef", "--ledger-dir", str(d))
    assert nf.returncode != 0 and "NOT_FOUND" in nf.stdout + nf.stderr


def test_concurrent_append_two_processes(tmp_path):
    d = tmp_path / "conc"
    script = (
        "import subprocess,sys,os\n"
        "d,tag=sys.argv[1],sys.argv[2]\n"
        "for i in range(20):\n"
        "    r=subprocess.run([sys.executable,'-m','verantyx.cli','events','add','approval','--ledger-dir',d,"
        "'--actor-type','owner','--actor-id',tag,'--text',tag+str(i)],capture_output=True)\n"
        "    assert r.returncode==0,r.stderr\n"
    )
    ps = [subprocess.Popen([sys.executable, "-c", script, str(d), t], env=_env(), cwd=tempfile.gettempdir()) for t in ("a", "b")]
    assert [p.wait(timeout=240) for p in ps] == [0, 0]
    from verantyx import ledger_events as L
    v = L.verify(d)
    assert v["n"] == 40 and v["status"] == "OK", v
