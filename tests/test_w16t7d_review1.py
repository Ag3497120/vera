"""W16-t7d 第 1 ラウンドのレビュー対応: actor type の組（K732）、分割で伏せが漏れない（必須 3）、計算量（必須 5）。"""
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from verantyx import ledger_events as L  # noqa: E402

SRC = "claude_code.UserPromptSubmit"


def _env(root):
    e = dict(os.environ)
    e["PYTHONPATH"] = str(root)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    return e


def cli(*args, root=ROOT):
    return subprocess.run([sys.executable, "-P", "-m", "verantyx.cli", *args], capture_output=True, text=True,
                          env=_env(root), cwd=tempfile.gettempdir())


@pytest.fixture(scope="module")
def base_root(tmp_path_factory):
    d = tmp_path_factory.mktemp("base")
    a = subprocess.run(["git", "-C", str(ROOT), "archive", "d1942e2", "verantyx"], capture_output=True)
    if a.returncode != 0:
        pytest.fail("git archive d1942e2 failed: " + a.stderr.decode(errors="replace"))
    subprocess.run(["tar", "-x", "-C", str(d)], input=a.stdout, check=True)
    return d


@pytest.mark.parametrize("kind,atype", [("approval", "system"), ("approval", "unknown"), ("owner_utterance", "unknown"),
                                        ("test_run", "system")])
def test_a11_t7_kinds_reject_new_actor_types_same_as_baseline(tmp_path, base_root, kind, atype):
    outs = []
    for root in (base_root, ROOT):
        led = tmp_path / f"l_{root.name}_{kind}_{atype}"
        r = cli("events", "add", kind, "--actor-type", atype, "--actor-id", "x", "--text", "hi", "--ledger-dir", str(led), root=root)
        assert r.returncode == 2 and not (led / "events.jsonl").exists()
        outs.append((r.returncode, r.stdout, r.stderr))
    assert outs[0] == outs[1]
    assert "('owner', 'agent', 'process')" in outs[1][1]


def _probe_verify(root, rows, d):
    """(kind, actor type) の並びから、sha を正しく計算した台帳を作って events verify の (rc, 出力) を返す。"""
    d.mkdir(parents=True, exist_ok=True)
    code = (
        "import json,sys\nfrom pathlib import Path\nfrom verantyx import ledger_events as L\n"
        "d=Path(sys.argv[1]); rows=json.loads(sys.stdin.read()); lines=[]; prev=L.GENESIS\n"
        "for k,a in rows:\n"
        "    r={'ts':'2026-10-06T00:00:00Z','kind':k,'actor':{'type':a,'id':'x'},'data':{'text':'t'},'prev':prev}\n"
        "    r['sha']=L.sha_of(r); prev=r['sha']; lines.append(L.canonical(r))\n"
        "(d/'events.jsonl').write_text('\\n'.join(lines)+'\\n'); (d/'HEAD').write_text(prev+'\\n')\n"
    )
    r = subprocess.run([sys.executable, "-P", "-c", code, str(d)], input=json.dumps(rows), capture_output=True, text=True,
                       env=_env(root), cwd=tempfile.gettempdir())
    assert r.returncode == 0, r.stderr
    v = cli("events", "verify", "--ledger-dir", str(d), root=root)
    return v.returncode, v.stdout


@pytest.mark.parametrize("rows", [
    [("approval", "system")], [("owner_utterance", "unknown")], [("approval", "owner"), ("test_run", "system")],
    [("system_message", "owner")], [("user_turn_unattributed", "system")], [("correction", "process")],
    [("correction", "system")], [("system_message", "unknown")],
])
def test_a11b_verify_shape_per_kind(tmp_path, base_root, rows):
    new = _probe_verify(ROOT, rows, tmp_path / "new")
    assert new[0] == 1 and "BAD_SHAPE" in new[1], new
    if all(k in L.KINDS for k, _a in rows):
        assert new == _probe_verify(base_root, rows, tmp_path / "base")      # T7 の語彙だけの台帳は基点と verify が一致


def test_a11c_new_kinds_accept_only_their_actor_type(tmp_path):
    ok = [("system_message", "system"), ("user_turn_unattributed", "unknown"), ("correction", "owner"), ("correction", "agent")]
    r = _probe_verify(ROOT, ok, tmp_path / "ok")
    assert r[0] == 0 and '"OK"' in r[1], r


@pytest.mark.parametrize("prompt", [
    "token=<system-reminder>abcdefgh9</system-reminder>",
    "see token=<system-reminder>abcdefgh9</system-reminder> ok",
    "Bearer <system-reminder>x</system-reminder>abcdefghijklmnopqrstuvwxyz0123456789",
])
def test_a12_secret_near_block_boundary_never_leaks(prompt):
    rows = L.claude_code_prompt_rows(prompt, SRC, "s")
    blob = json.dumps(rows, ensure_ascii=False)
    full, n = L.redact_obj({"text": prompt})
    for secret in ("abcdefgh9", "abcdefghijklmnopqrstuvwxyz0123456789"):
        # 基点（全体を伏せる）が伏せる秘密は、どの行にも出ない。基点が伏せない形は基点と同じ扱い
        if secret in prompt and secret not in full["text"]:
            assert secret not in blob
        if secret in prompt and secret in full["text"]:
            assert secret in blob
    assert sum(r[2]["redactions"] for r in rows) >= n
    if len(rows) == 1:
        assert rows[0][0] == "user_turn_unattributed" and rows[0][2]["reason"] == "SECRET_NEAR_BLOCK_BOUNDARY"


def test_a12b_ordinary_mixed_still_two_rows():
    rows = L.claude_code_prompt_rows("please look <system-reminder>r</system-reminder> thanks", SRC, "s")
    assert [r[0] for r in rows] == ["system_message", "owner_utterance"]


def test_a13_split_scales_linearly():
    def t(k):
        s = "<system-reminder></system-reminder>" * k
        a = time.perf_counter()
        r = L.split_system_blocks(s)
        assert r["status"] == "SYSTEM_ONLY" and len(r["blocks"]) == k
        return time.perf_counter() - a
    t(1000)
    small, big = min(t(5000) for _ in range(3)), min(t(40000) for _ in range(3))
    assert big < 1.0 and big < small * 24      # 8 倍の入力で 2 乗なら 64 倍
