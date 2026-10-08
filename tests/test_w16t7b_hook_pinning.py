"""W16-t7b: hook のコマンドの固定 (K710)・終了コード 2 を返さない (K711)・導入前の自己検査 (K712)・不変 (K713)。

H2 の字面（読み取り専用の台帳で終了 1）は W16-t7 の既存テスト test_hook_unwritable_ledger_still_exits_zero
（書けない台帳で returncode == 0）と矛盾する。既存テストの期待は変えない裁定（中間職）なので、ここでは
「2 ではない」ことと実測値 0 を固定する（H2_LITERAL_CONFLICTS_WITH_W16T7_TEST）。
hook のコマンドの実行は必ず clean_env（PYTHONPATH を引き継がない）。
"""
import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KINDS_EXPECTED = ["owner_utterance", "tool_call", "agent_stop", "agent_stop", "process_start", "process_exit"]
ORDER = ["UserPromptSubmit", "PostToolUse", "Stop", "SubagentStop", "SessionStart", "SessionEnd"]
PAY = {
    "UserPromptSubmit": {"session_id": "s", "hook_event_name": "UserPromptSubmit", "prompt": "hi"},
    "PostToolUse": {"session_id": "s", "hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "true"}, "tool_response": {"exit_code": 0}},
    "Stop": {"session_id": "s", "hook_event_name": "Stop"},
    "SubagentStop": {"session_id": "s", "hook_event_name": "SubagentStop"},
    "SessionStart": {"session_id": "s", "hook_event_name": "SessionStart"},
    "SessionEnd": {"session_id": "s", "hook_event_name": "SessionEnd"},
}


def clean_env(**kw):
    e = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONHOME", "PYTHONSAFEPATH")}
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update(kw)
    return e


def tool_env(**kw):
    e = dict(os.environ)
    e["PYTHONPATH"] = str(ROOT)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update(kw)
    return e


def vera(*args, cwd=None, input=None, env=None):
    return subprocess.run([sys.executable, "-m", "verantyx.cli", *args], capture_output=True, text=True, input=input,
                          env=env or tool_env(), cwd=str(cwd or ROOT))


def fake_verantyx(d: Path) -> Path:
    (d / "verantyx").mkdir(parents=True, exist_ok=True)
    (d / "verantyx" / "__init__.py").write_text("")
    (d / "verantyx" / "cli.py").write_text("import sys\nsys.exit(2)\n")
    return d


def template(*extra):
    r = vera("hooks", "print", "--claude-code", *extra)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout), r.stderr


def commands(tpl):
    return {ev: tpl["hooks"][ev][0]["hooks"][0]["command"] for ev in ORDER}


def run_cmd(cmd, payload, cwd, proj):
    return subprocess.run(["/bin/sh", "-c", cmd], input=json.dumps(payload), capture_output=True, text=True, cwd=str(cwd),
                          env=clean_env(CLAUDE_PROJECT_DIR=str(proj)), timeout=30)


def ledger_rows(proj: Path):
    p = proj / ".vera" / "ledger" / "events.jsonl"
    return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []


def run_all(cmds, cwd, proj):
    return {ev: run_cmd(cmds[ev], PAY[ev], cwd, proj) for ev in ORDER}


def assert_all_ok(res, proj):
    for ev, r in res.items():
        assert r.returncode == 0, (ev, r.stderr)
        assert r.stdout == "", (ev, r.stdout)
    rows = ledger_rows(proj)
    assert [x["kind"] for x in rows] == KINDS_EXPECTED
    v = vera("events", "verify", "--ledger-dir", str(proj / ".vera" / "ledger"))
    assert v.returncode == 0, v.stdout


# ---- H1 ----
def test_h1a_fake_verantyx_in_cwd(tmp_path):
    """H1: 偽の verantyx/ が cwd にあっても 6 つとも終了 0・台帳 6 行。"""
    proj = fake_verantyx(tmp_path / "proj")
    tpl, _ = template()
    assert_all_ok(run_all(commands(tpl), proj, proj), proj)


def test_h1b_elsewhere_cwd(tmp_path):
    """H1: 別の cwd（偽なし）でも reference-verantyx を読まずに動く。"""
    proj = tmp_path / "proj"
    proj.mkdir()
    el = tmp_path / "elsewhere"
    el.mkdir()
    tpl, _ = template()
    assert_all_ok(run_all(commands(tpl), el, proj), proj)


def test_h1c_pin_shape_and_vera_note():
    """H1: -P 形・|| exit 1 終わり・標準エラーの _vera・標準出力は {hooks} のまま。"""
    tpl, err = template()
    assert set(tpl) == {"hooks"}
    for ev, c in commands(tpl).items():
        assert " -P -m verantyx.cli events add " in c, c
        assert c.endswith(" || exit 1"), c
    note = json.loads(err.strip().splitlines()[-1])["_vera"]
    assert note["python"] == sys.executable
    assert note["code_root"] == str(ROOT)
    assert note["form"] == "dash_P"
    assert note["python_source"] == "sys.executable" and note["code_root_source"] == "loaded_package"


def test_h1d_quoting_space_and_dollar(tmp_path):
    """H1: 空白と $ を含む --code-root でも展開されず動く。"""
    link = tmp_path / "code root $HOME"
    link.symlink_to(ROOT)
    proj = fake_verantyx(tmp_path / "proj")
    tpl, err = template("--code-root", str(link))
    assert json.loads(err.strip().splitlines()[-1])["_vera"]["code_root_source"] == "--code-root"
    assert_all_ok(run_all(commands(tpl), proj, proj), proj)


def test_h1e_dash_c_form(tmp_path):
    """H1: 3.10 以下用の -c の形（3.11 上で実行。3.10 そのものでは実行していない）。"""
    from verantyx import hooks_templates as H
    pin = {**H.resolve_pin(None, None), "form": "dash_c_syspath"}
    prefix = H.pinned_shell_prefix(pin)
    assert " -P " not in prefix and "runpy" in prefix
    tpl = H.claude_code_template(pin=pin)
    proj = fake_verantyx(tmp_path / "proj")
    assert_all_ok(run_all(commands(tpl), proj, proj), proj)


# ---- H2 ----
def _ro_hook_runs(tmp_path, with_events):
    proj = tmp_path / "proj"
    proj.mkdir()
    led = proj / ".vera" / "ledger"
    tpl, _ = template()
    cmds = commands(tpl)
    if with_events:
        assert run_cmd(cmds["Stop"], PAY["Stop"], proj, proj).returncode == 0
    else:
        led.mkdir(parents=True)
    assert led.is_dir() and os.geteuid() != 0, "root では読み取り専用が効かない（前提）"
    led.chmod(0o555)
    try:
        return {ev: run_cmd(cmds[ev], PAY[ev], proj, proj).returncode for ev in ORDER}
    finally:
        led.chmod(0o755)


@pytest.mark.parametrize("with_events", [False, True])
def test_h2a_readonly_ledger_not_two(tmp_path, with_events):
    """H2（字面は矛盾。上の docstring）: 読み取り専用の台帳で終了コードは 2 ではない。実測は 0（W16-t7 の既存の挙動）。"""
    rcs = _ro_hook_runs(tmp_path, with_events)
    assert all(rc != 2 for rc in rcs.values()), rcs
    assert all(rc == 0 for rc in rcs.values()), rcs


def test_h2b_failures_become_one(tmp_path):
    """H2: 本当に非 0 になる失敗（存在しない python）は || exit 1 で 1。"""
    proj = fake_verantyx(tmp_path / "proj")
    tpl, _ = template("--python", "/nonexistent/python")
    for ev, c in commands(tpl).items():
        assert run_cmd(c, PAY[ev], proj, proj).returncode == 1, ev


def test_h2b_arg_errors(tmp_path):
    """K711: --from claude-code の引数の誤りは 1。--from 無し・--from codex・他のサブコマンドは 2 のまま (K713)。"""
    led = str(tmp_path / "l")
    r = vera("events", "add", "bogus", "--from", "claude-code", "--stdin", input="{}", cwd=tmp_path)
    assert r.returncode == 1, r.stderr
    r = vera("events", "add", "bogus", "--from=claude-code", "--stdin", input="{}", cwd=tmp_path)
    assert r.returncode == 1, r.stderr
    r = vera("events", "add", "auto", "--from", "claude-code", "--stdin", "--bogus", "--ledger-dir", led, input="{}", cwd=tmp_path)
    assert r.returncode == 1, r.stderr
    r = vera("events", "add", "bogus", "--actor-type", "owner", "--actor-id", "x", cwd=tmp_path)
    assert r.returncode == 2
    r = vera("events", "add", "bogus", "--from", "codex", "x", cwd=tmp_path)
    assert r.returncode == 2
    r = vera("events", "add", "auto", "--bogus", "--ledger-dir", led, cwd=tmp_path)
    assert r.returncode == 2
    r = vera("events", "tail", "--bogus", cwd=tmp_path)
    assert r.returncode == 2


# ---- H3 ----
def _install(proj, *extra):
    r = vera("hooks", "install", "--project", str(proj), "--write", *extra)
    return r, (json.loads(r.stdout) if r.stdout.strip() else None)


def test_h3a_install_with_fake_cwd_package(tmp_path):
    """H3: 偽の verantyx/ があっても自己検査を通って書く。.vera は作らない。settings.json に _vera は入れない。"""
    proj = fake_verantyx(tmp_path / "proj")
    r, out = _install(proj)
    assert r.returncode == 0, r.stdout + r.stderr
    assert out["status"] == "WRITTEN" and out["selftest"]["ok"] is True and out["selftest"]["n"] == 6
    assert out["_vera"]["form"] == "dash_P"
    s = json.loads((proj / ".claude" / "settings.json").read_text())
    assert "_vera" not in s and set(s["hooks"]) == set(ORDER)
    assert not (proj / ".vera").exists()
    assert sorted(p.name for p in proj.iterdir()) == [".claude", "verantyx"]


def test_h3b_bad_python_refused(tmp_path):
    """H3: 存在しない --python は REFUSED_HOOK_SELFTEST・終了 2・何も書かない。既存 settings はバイト不変。"""
    proj = tmp_path / "proj"
    proj.mkdir()
    r, out = _install(proj, "--python", "/nonexistent/python")
    assert r.returncode == 2
    assert out["status"] == "REFUSED_HOOK_SELFTEST"
    cases = out["selftest"]["cases"]
    assert len(cases) == 6 and all(c["returncode"] == 1 for c in cases)
    assert not (proj / ".claude").exists() and not (proj / ".vera").exists()
    proj2 = tmp_path / "proj2"
    (proj2 / ".claude").mkdir(parents=True)
    f = proj2 / ".claude" / "settings.json"
    f.write_text('{"model": "x"}\n')
    before = f.read_bytes()
    r, out = _install(proj2, "--python", "/nonexistent/python")
    assert r.returncode == 2 and out["status"] == "REFUSED_HOOK_SELFTEST"
    assert f.read_bytes() == before and not (proj2 / ".vera").exists()


def test_h3c_unpinned_old_form_refused(tmp_path):
    """H3: 固定しない古い形は偽の verantyx/ のある cwd で自己検査に落ちる。"""
    proj = fake_verantyx(tmp_path / "proj")
    r, out = _install(proj, "--vera-cmd", f"{sys.executable} -m verantyx.cli")
    assert r.returncode == 2 and out["status"] == "REFUSED_HOOK_SELFTEST"
    assert not (proj / ".claude").exists()


def test_h3d_dry_run_no_selftest_no_write(tmp_path):
    proj = fake_verantyx(tmp_path / "proj")
    r = vera("hooks", "install", "--project", str(proj))
    assert r.returncode == 0 and json.loads(r.stdout)["status"] == "NOT_WRITTEN_NO_FLAG"
    assert not (proj / ".claude").exists() and not (proj / ".vera").exists()


def test_h3e_vera_cmd_and_python_exclusive(tmp_path):
    r = vera("hooks", "print", "--claude-code", "--vera-cmd", "x", "--python", "y")
    assert r.returncode == 2


def test_h3f_old_hooks_not_removed(tmp_path):
    """既存の古い雛形（|| exit 1 無し）は消さない・書き換えない。"""
    proj = fake_verantyx(tmp_path / "proj")
    (proj / ".claude").mkdir()
    old = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "x -m verantyx.cli events add agent_stop --stdin --from claude-code", "timeout": 10}]}]}}
    (proj / ".claude" / "settings.json").write_text(json.dumps(old))
    r, out = _install(proj)
    assert r.returncode == 0 and out["status"] == "WRITTEN"
    s = json.loads((proj / ".claude" / "settings.json").read_text())
    assert s["hooks"]["Stop"][0] == old["hooks"]["Stop"][0] and len(s["hooks"]["Stop"]) == 2
    assert out["stale_vera_hooks"] == 1


# ---- H4 ----
def _codex_argv(proj, *extra):
    r = vera("hooks", "print", "--codex", "--project", str(proj), *extra)
    assert r.returncode == 0, r.stderr
    assert "# _vera:" in r.stdout
    return tomllib.loads(r.stdout)["notify"]


def _run_codex(argv, proj):
    argv = argv + [json.dumps({"type": "agent-turn-complete", "thread-id": "t1"})]
    r = subprocess.run(argv, capture_output=True, text=True, cwd=str(proj), env=clean_env(), timeout=30)
    assert r.returncode == 0, r.stderr
    rows = ledger_rows(proj)
    assert [x["kind"] for x in rows] == ["agent_stop"]


def test_h4_codex_notify(tmp_path):
    """H4: Codex の notify の argv も偽の verantyx/ のある cwd で終了 0・台帳 1 行。"""
    proj = fake_verantyx(tmp_path / "proj")
    argv = _codex_argv(proj)
    assert argv[0] == "/usr/bin/env" and argv[1].startswith("PYTHONPATH=") and "-P" in argv
    _run_codex(argv, proj)


def test_h4_codex_notify_dash_c(tmp_path):
    from verantyx import hooks_templates as H
    pin = {**H.resolve_pin(None, None), "form": "dash_c_syspath"}
    proj = fake_verantyx(tmp_path / "proj")
    argv = H.pinned_argv_prefix(pin) + ["events", "add", "agent_stop", "--from", "codex", "--ledger-dir", str(proj / ".vera" / "ledger")]
    _run_codex(argv, proj)


# ---- K713 ----
def test_k713_same_rows_as_old_form(tmp_path):
    """K713: 固定の形と従来の PYTHONPATH=ROOT 形とで、行の kind・actor・data が一致（ts・prev・sha を除く）。"""
    tpl, _ = template()
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir(); b.mkdir()
    cmds = commands(tpl)
    old = {ev: c.replace(" -P -m", " -m").removesuffix(" || exit 1") for ev, c in cmds.items()}
    for ev in ORDER:
        assert run_cmd(cmds[ev], PAY[ev], a, a).returncode == 0
        r = subprocess.run(["/bin/sh", "-c", old[ev]], input=json.dumps(PAY[ev]), capture_output=True, text=True, cwd=str(b),
                           env=clean_env(CLAUDE_PROJECT_DIR=str(b)))
        assert r.returncode == 0, r.stderr
    strip = lambda rows: [{k: x[k] for k in ("kind", "actor", "data")} for x in rows]
    assert strip(ledger_rows(a)) == strip(ledger_rows(b)) and len(ledger_rows(a)) == 6


def test_resolve_pin_does_not_resolve_symlink(tmp_path):
    from verantyx import hooks_templates as H
    link = tmp_path / "py"
    link.symlink_to(sys.executable)
    p = H.resolve_pin(str(link), None)
    assert p["python"] == str(link) and p["python_source"] == "--python"


# ---- 第 2 ラウンド（レビュー M1）: --python と --code-root は同時に指定できる ----
def test_m1a_python_and_code_root_together(tmp_path):
    link = tmp_path / "a b$x"
    link.symlink_to(ROOT)
    r = vera("hooks", "print", "--claude-code", "--python", sys.executable, "--code-root", str(link))
    assert r.returncode == 0, r.stderr
    note = json.loads(r.stderr.strip().splitlines()[-1])["_vera"]
    assert note["python_source"] == "--python" and note["code_root_source"] == "--code-root"
    proj = fake_verantyx(tmp_path / "proj")
    cmds = commands(json.loads(r.stdout))
    for ev in ORDER:
        c = run_cmd(cmds[ev], PAY[ev], proj, proj)
        assert c.returncode == 0, (ev, c.stderr)
    assert len(ledger_rows(proj)) == 6


@pytest.mark.parametrize("sub", [("print", "--claude-code"), ("print", "--codex"), ("install", "--write")])
@pytest.mark.parametrize("other", ["--python", "--code-root"])
def test_m1b_vera_cmd_exclusive_with_python_and_code_root(tmp_path, sub, other):
    proj = tmp_path / "proj"
    proj.mkdir()
    extra = ["--project", str(proj)] if sub[0] == "install" else []
    r = vera("hooks", *sub, *extra, "--vera-cmd", "x", other, "y")
    assert r.returncode == 2, r.stderr
    assert list(proj.iterdir()) == []


def test_m1c_frozen_requires_both(monkeypatch):
    sys.path.insert(0, str(ROOT))
    from verantyx import hooks_templates as H
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    for a in [(None, None), (sys.executable, None), (None, str(ROOT))]:
        with pytest.raises(H.PinError) as e:
            H.resolve_pin(*a)
        assert e.value.code == "PIN_UNRESOLVABLE_FROZEN"
    assert H.resolve_pin(sys.executable, str(ROOT))["form"] == "dash_P"
