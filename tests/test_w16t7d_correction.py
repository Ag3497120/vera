"""W16-t7d K731 / U2: 取り違えた行の訂正（追記専用）。基点のコードで取り違えを作り、新しいコードで訂正する。"""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from verantyx import ledger_events as L  # noqa: E402

TN = "<task-notification>\n<task-id>x</task-id>\n</task-notification>"


def _env(root=None, **kw):
    e = dict(os.environ)
    e["PYTHONPATH"] = str(root or ROOT)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update(kw)
    return e


def cli(*args, input=None, root=None):
    return subprocess.run([sys.executable, "-P", "-m", "verantyx.cli", *args], capture_output=True, text=True, input=input,
                          env=_env(root), cwd=tempfile.gettempdir())


def rows_of(led):
    p = Path(led) / "events.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").split("\n") if x.strip()] if p.exists() else []


@pytest.fixture(scope="module")
def base_root(tmp_path_factory):
    d = tmp_path_factory.mktemp("base")
    a = subprocess.run(["git", "-C", str(ROOT), "archive", "d1942e2", "verantyx"], capture_output=True)
    if a.returncode != 0:
        pytest.fail("git archive d1942e2 failed: " + a.stderr.decode(errors="replace"))
    subprocess.run(["tar", "-x", "-C", str(d)], input=a.stdout, check=True)
    return d


def make_misattributed(led, base_root):
    payload = {"session_id": "s1", "hook_event_name": "UserPromptSubmit", "prompt": TN}
    r = cli("events", "add", "owner_utterance", "--stdin", "--from", "claude-code", "--ledger-dir", str(led),
            input=json.dumps(payload), root=base_root)
    assert r.returncode == 0
    row = rows_of(led)[-1]
    assert row["kind"] == "owner_utterance" and row["actor"]["type"] == "owner"   # 取り違えの再現（基点）
    return row["sha"]


def correct(led, sha, *extra, kind="system_message", note="通知の塊", atype="agent", aid="t7d-test"):
    args = ["events", "correct", "--ledger-dir", str(led), "--refers", sha, "--kind-should-be", kind]
    if note is not None:
        args += ["--note", note]
    if atype is not None:
        args += ["--actor-type", atype]
    if aid is not None:
        args += ["--actor-id", aid]
    return cli(*args, *extra)


def test_b1_correction_appended_verify_ok(tmp_path, base_root):
    led = tmp_path / "l"
    sha = make_misattributed(led, base_root)
    v0 = L.verify(led)
    assert v0["status"] == "OK" and v0["n"] == 1
    r = correct(led, sha[:12])
    assert r.returncode == 0, r.stderr + r.stdout
    last = rows_of(led)[-1]
    assert last["kind"] == "correction"
    assert last["data"]["refers"] == sha
    assert last["data"]["kind_should_be"] == "system_message"
    assert last["data"]["actor_should_be"]["type"] == "system"
    assert last["data"]["refers_kind"] == "owner_utterance"
    assert last["actor"] == {"type": "agent", "id": "t7d-test"}
    assert set(last) == {"ts", "kind", "actor", "data", "prev", "sha"}
    v1 = L.verify(led)
    assert v1["status"] == "OK" and v1["n"] == 2 and v1["head"] == last["sha"]
    assert json.loads(r.stdout)["sha"] == last["sha"]


def test_b1b_original_row_untouched(tmp_path, base_root):
    led = tmp_path / "l"
    sha = make_misattributed(led, base_root)
    before = (led / "events.jsonl").read_bytes()
    assert correct(led, sha).returncode == 0
    assert (led / "events.jsonl").read_bytes().startswith(before)


def test_b2_annotations_on_tail_show_grep(tmp_path, base_root):
    led = tmp_path / "l"
    sha = make_misattributed(led, base_root)
    cli("events", "add", "approval", "--ledger-dir", str(led), "--actor-type", "owner", "--actor-id", "o", "--text", "ok")
    # 訂正の前: どの行にも corrected_by は無い
    t = cli("events", "tail", "-n", "5", "--ledger-dir", str(led))
    assert all("corrected_by" not in json.loads(x) for x in t.stdout.splitlines())
    assert correct(led, sha).returncode == 0
    t = [json.loads(x) for x in cli("events", "tail", "-n", "5", "--ledger-dir", str(led)).stdout.splitlines()]
    assert len(t) == 3
    assert "corrected_by" in t[0] and t[0]["corrected_by"][0]["kind_should_be"] == "system_message"
    assert t[0]["corrected_by"][0]["sha"] == rows_of(led)[-1]["sha"]
    assert "corrected_by" not in t[1] and "corrected_by" not in t[2]
    s = json.loads(cli("events", "show", sha[:10], "--ledger-dir", str(led)).stdout)
    assert "corrected_by" in s
    body = {k: v for k, v in s.items() if k != "corrected_by"}
    assert L.sha_of(body) == sha
    g = [json.loads(x) for x in cli("events", "grep", "owner_utterance", "--ledger-dir", str(led)).stdout.splitlines()]
    assert len(g) == 1 and "corrected_by" in g[0]
    for r in rows_of(led):
        assert "corrected_by" not in r            # 台帳には書かない


def test_b2b_multiple_corrections_all_shown(tmp_path, base_root):
    led = tmp_path / "l"
    sha = make_misattributed(led, base_root)
    assert correct(led, sha, note="one").returncode == 0
    assert correct(led, sha, kind="user_turn_unattributed", note="two").returncode == 0
    s = json.loads(cli("events", "show", sha[:10], "--ledger-dir", str(led)).stdout)
    assert [c["note"] for c in s["corrected_by"]] == ["one", "two"]


def _state(led):
    return len(rows_of(led)), (led / "HEAD").read_text()


def test_b3_typed_rejections(tmp_path, base_root):
    led = tmp_path / "l"
    sha = make_misattributed(led, base_root)
    cli("events", "add", "approval", "--ledger-dir", str(led), "--actor-type", "owner", "--actor-id", "o", "--text", "ok")
    appr = rows_of(led)[-1]["sha"]
    st = _state(led)

    def err(r):
        return json.loads(r.stdout)["error"]

    r = correct(led, sha[:7]); assert (r.returncode, err(r)) == (2, "PREFIX_TOO_SHORT")
    r = correct(led, "f" * 12); assert (r.returncode, err(r)) == (1, "NOT_FOUND")
    r = correct(led, appr); assert (r.returncode, err(r)) == (2, "NOT_AN_ATTRIBUTION_ROW")
    r = correct(led, sha, kind="owner_utterance"); assert (r.returncode, err(r)) == (2, "NO_CHANGE")
    r = correct(led, sha, note="   "); assert (r.returncode, err(r)) == (2, "NOTE_REQUIRED")
    r = correct(led, sha, aid=None); assert r.returncode == 2
    r = correct(led, sha, atype=None); assert r.returncode == 2
    r = correct(led, sha, note=None); assert r.returncode == 2
    assert _state(led) == st


def test_b3b_ambiguous_prefix(tmp_path):
    led = tmp_path / "l"
    # 同じ 8 字の接頭辞を持つ 2 行を、sha を直接書いて作る（検査用の合成。verify は見ない関数だけを呼ぶ）
    rows = [{"sha": "abcdef012345" + "0" * 52, "kind": "owner_utterance"}, {"sha": "abcdef01" + "9" * 56, "kind": "owner_utterance"}]
    led.mkdir()
    (led / "events.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
    assert len(L.find_by_prefix(led, "abcdef01")) == 2
    r = cli("events", "show", "abcdef01", "--ledger-dir", str(led))
    assert json.loads(r.stdout)["error"] == "AMBIGUOUS_PREFIX"


def test_b3c_ambiguous_correct_via_function(tmp_path, monkeypatch):
    led = tmp_path / "l"
    for i in range(1):
        L.append(led, "owner_utterance", {"type": "owner", "id": "s"}, {"text": "a"})
    monkeypatch.setattr(L, "find_by_prefix", lambda d, p: [{"sha": "a" * 64, "kind": "owner_utterance", "actor": {"type": "owner", "id": "s"}}] * 2)
    with pytest.raises(L.LedgerError) as e:
        L.append_correction(led, "aaaaaaaa", "system_message", "n", {"type": "agent", "id": "x"})
    assert e.value.code == "AMBIGUOUS_PREFIX"


def test_b3d_tampered_ledger_unverified(tmp_path, base_root):
    led = tmp_path / "l"
    sha = make_misattributed(led, base_root)
    cli("events", "add", "approval", "--ledger-dir", str(led), "--actor-type", "owner", "--actor-id", "o", "--text", "ok")
    p = led / "events.jsonl"
    p.write_text(p.read_text().replace('"ok"', '"OK"'))
    st = _state(led)
    r = correct(led, sha)
    assert r.returncode == 1 and json.loads(r.stdout)["error"] == "LEDGER_UNVERIFIED"
    assert _state(led) == st


def test_b4_manual_add_cannot_write_new_kinds(tmp_path):
    for k in ("correction", "system_message", "user_turn_unattributed"):
        r = cli("events", "add", k, "--ledger-dir", str(tmp_path / "l"), "--text", "x")
        assert r.returncode == 2 and "invalid choice" in r.stderr
    assert not (tmp_path / "l" / "events.jsonl").exists()


def test_b5_note_secret_redacted(tmp_path, base_root):
    led = tmp_path / "l"
    sha = make_misattributed(led, base_root)
    r = correct(led, sha, note="leak sk-ant-abcdefgh12345678 here")
    assert r.returncode == 0
    last = rows_of(led)[-1]
    assert "abcdefgh12345678" not in json.dumps(last)
    assert last["data"]["redactions"] >= 1
    assert L.verify(led)["status"] == "OK"


def test_b6_no_correction_ledger_output_identical_via_annotate():
    row = {"sha": "a" * 64, "kind": "approval"}
    assert L.annotate_corrections(row, L.corrections_index([row])) is row
