"""W16-t7 K702 / T7-1(b) / T7-2: hook の雛形（出力するだけ）・hook 経路・install。"""
import ast
import json
import os
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVENTS = {"UserPromptSubmit", "PostToolUse", "Stop", "SubagentStop", "SessionStart", "SessionEnd"}


def _env(**kw):
    e = dict(os.environ)
    e["PYTHONPATH"] = str(ROOT)
    e["PYTHONDONTWRITEBYTECODE"] = "1"
    e.update(kw)
    return e


def cli(*args, input=None, cwd=None, env=None):
    return subprocess.run([sys.executable, "-m", "verantyx.cli", *args], capture_output=True, text=True, input=input,
                          env=env or _env(), cwd=str(cwd or tempfile.gettempdir()))


def template():
    r = cli("hooks", "print", "--claude-code")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def command_of(tpl, event):
    return tpl["hooks"][event][0]["hooks"][0]["command"]


def run_hook(tpl, event, payload, proj, cwd=None, raw=None):
    env = _env(CLAUDE_PROJECT_DIR=str(proj))
    return subprocess.run(command_of(tpl, event), shell=True, capture_output=True, text=True, env=env,
                          input=raw if raw is not None else json.dumps(payload), cwd=str(cwd or proj))


def ledger_rows(proj):
    p = Path(proj) / ".vera" / "ledger" / "events.jsonl"
    return [json.loads(x) for x in p.read_text(encoding="utf-8").split("\n") if x.strip()] if p.exists() else []


def validate_claude_hooks(obj):
    assert set(obj) == {"hooks"}
    assert isinstance(obj["hooks"], dict) and obj["hooks"]
    assert set(obj["hooks"]) <= EVENTS
    for ev, arr in obj["hooks"].items():
        assert isinstance(arr, list) and arr
        for ent in arr:
            assert set(ent) <= {"matcher", "hooks"}
            assert "matcher" not in ent or isinstance(ent["matcher"], str)
            assert isinstance(ent["hooks"], list) and ent["hooks"]
            for h in ent["hooks"]:
                assert h["type"] == "command" and isinstance(h["command"], str) and h["command"]
                assert "timeout" not in h or isinstance(h["timeout"], int)
                assert set(h) <= {"type", "command", "timeout"}


def test_print_claude_code_is_valid_hooks_shape():
    t = template()
    validate_claude_hooks(t)
    assert set(t["hooks"]) == EVENTS
    assert t["hooks"]["PostToolUse"][0]["matcher"] == "Bash"


def test_print_codex_toml():
    r = cli("hooks", "print", "--codex")
    assert r.returncode == 0
    d = tomllib.loads(r.stdout)
    assert isinstance(d["notify"], list) and all(isinstance(x, str) for x in d["notify"])
    assert "events" in d["notify"] and "agent_stop" in d["notify"]
    assert any(l.lstrip().startswith("#") and "notify" in l for l in r.stdout.splitlines())


def test_print_writes_nothing(tmp_path):
    cli("hooks", "print", "--claude-code", cwd=tmp_path)
    cli("hooks", "print", "--codex", cwd=tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_user_prompt_verbatim_japanese_multiline_emoji(tmp_path):
    t = template()
    prompt = "全部止めて。\n子プロセスも\n  ええ、そう 🛑 \"quote\" \\ backslash\ttab"
    r = run_hook(t, "UserPromptSubmit", {"session_id": "s1", "hook_event_name": "UserPromptSubmit", "prompt": prompt, "cwd": str(tmp_path)}, tmp_path)
    assert r.returncode == 0 and r.stdout == ""
    rows = ledger_rows(tmp_path)
    assert len(rows) == 1 and rows[0]["kind"] == "owner_utterance"
    assert rows[0]["data"]["text"] == prompt
    assert rows[0]["actor"]["type"] == "owner" and rows[0]["actor"]["id"] == "s1"
    assert rows[0]["data"]["redactions"] == 0 and rows[0]["data"]["source"] == "claude_code.UserPromptSubmit"
    v = cli("events", "verify", "--ledger-dir", str(tmp_path / ".vera" / "ledger"))
    assert v.returncode == 0


def test_hook_never_fails_and_logs_rejects(tmp_path):
    t = template()
    for raw in ('{"session_id":"s","hook_event_name":"UserPromptSubmit"}', "{not json", "", "[1,2]", "null"):
        r = run_hook(t, "UserPromptSubmit", None, tmp_path, raw=raw)
        assert r.returncode == 0 and r.stdout == "", (raw, r)
    rj = tmp_path / ".vera" / "ledger" / "rejects.jsonl"
    lines = [json.loads(x) for x in rj.read_text().splitlines() if x.strip()]
    assert len(lines) == 5
    assert "NO_PROMPT_IN_PAYLOAD" in {l["reason"] for l in lines}
    assert ledger_rows(tmp_path) == []


def test_hook_unwritable_ledger_still_exits_zero(tmp_path):
    blocker = tmp_path / "blk"
    blocker.write_text("file, not dir")
    t = template()
    r = run_hook(t, "UserPromptSubmit", {"prompt": "x"}, blocker, cwd=tmp_path)
    assert r.returncode == 0 and r.stdout == ""


def test_stop_and_subagent_stop(tmp_path):
    t = template()
    for ev in ("Stop", "SubagentStop"):
        r = run_hook(t, ev, {"session_id": "s2", "hook_event_name": ev}, tmp_path)
        assert r.returncode == 0 and r.stdout == ""
    rows = ledger_rows(tmp_path)
    assert [x["kind"] for x in rows] == ["agent_stop", "agent_stop"]
    assert [x["data"]["hook_event_name"] for x in rows] == ["Stop", "SubagentStop"]
    assert rows[0]["actor"]["type"] == "agent"


def _git_repo(p):
    p.mkdir(exist_ok=True)
    g = lambda *a: subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@e", *a], cwd=p, capture_output=True, text=True)
    g("init", "-q")
    (p / "f").write_text("x")
    g("add", "f")
    g("commit", "-q", "-m", "m")
    return g("rev-parse", "HEAD").stdout.strip()


def post(tpl, proj, cmd, resp=None, cwd=None, extra_in=None):
    pl = {"session_id": "s3", "hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(cwd or proj)}
    if resp is not None:
        pl["tool_response"] = resp
    return run_hook(tpl, "PostToolUse", pl, proj, cwd=cwd)


def test_posttooluse_classification(tmp_path):
    t = template()
    repo = tmp_path / "repo"
    head = _git_repo(repo)
    proj = tmp_path / "proj"
    proj.mkdir()
    assert post(t, proj, "git commit -m x", {"exit_code": 0}, cwd=repo).returncode == 0
    assert post(t, proj, "python -m pytest -q tests/x.py", {"returncode": 1}).returncode == 0
    assert post(t, proj, "ls -la", {"stdout": "x"}).returncode == 0
    assert post(t, proj, "git commit -m x && pytest -q", {"exitCode": 0}, cwd=repo).returncode == 0
    assert post(t, proj, "npm test").returncode == 0
    rows = ledger_rows(proj)
    assert [r["kind"] for r in rows] == ["commit", "test_run", "tool_call", "tool_call", "test_run"]
    c, tr, tc, amb, nt = (r["data"] for r in rows)
    assert c["git_head"] == head and c["exit_code"] == 0
    assert tr["exit_code"] == 1 and tr["classified_by"]
    assert tc["classified_by"] is None and tc["exit_code"] is None and tc["exit_code_status"] == "UNKNOWN_NOT_IN_PAYLOAD"
    assert amb["ambiguous"] == ["commit", "test_run"] and amb["classified_by"] is None      # 同点は棄権
    assert nt["exit_code"] is None and nt["exit_code_status"] == "UNKNOWN_NOT_IN_PAYLOAD"
    for d in (c, tr, tc, amb, nt):
        assert d["tool_name"] == "Bash" and len(d["args_sha256"]) == 64 and "args" not in d


def test_commit_outside_repo_head_null(tmp_path):
    t = template()
    plain = tmp_path / "plain"
    plain.mkdir()
    proj = tmp_path / "proj"
    proj.mkdir()
    post(t, proj, "git commit -m x", {"exit_code": 0}, cwd=plain)
    d = ledger_rows(proj)[0]["data"]
    assert d["git_head"] is None and d.get("git_head_status")


def test_session_start_end_mapping(tmp_path):
    t = template()
    run_hook(t, "SessionStart", {"session_id": "s4", "hook_event_name": "SessionStart"}, tmp_path)
    run_hook(t, "SessionEnd", {"session_id": "s4", "hook_event_name": "SessionEnd"}, tmp_path)
    rows = ledger_rows(tmp_path)
    assert [r["kind"] for r in rows] == ["process_start", "process_exit"]
    assert rows[1]["data"]["exit_code"] is None and rows[1]["data"]["exit_code_status"] == "NOT_A_PROCESS_EXIT_CODE"
    assert rows[0]["actor"]["type"] == "agent" and rows[0]["data"]["source"] == "claude_code.SessionStart"


def test_codex_notify_argv(tmp_path):
    d = tmp_path / "led"
    payload = json.dumps({"type": "agent-turn-complete", "thread-id": "th1", "turn-id": "t1", "input-messages": ["a", "b"], "last-assistant-message": "done"})
    r = cli("events", "add", "agent_stop", "--from", "codex", "--ledger-dir", str(d), payload)
    assert r.returncode == 0 and r.stdout == ""
    row = json.loads((d / "events.jsonl").read_text().splitlines()[0])
    assert row["kind"] == "agent_stop" and row["actor"]["id"] == "th1"
    assert row["data"]["source"] == "codex.notify" and row["data"]["input_messages_count"] == 2
    assert "done" not in json.dumps(row)                       # 本文は入れない（sha だけ）
    r = cli("events", "add", "agent_stop", "--from", "codex", "--ledger-dir", str(d), "{bad")
    assert r.returncode == 0 and r.stdout == ""


def test_install_without_flag_writes_nothing(tmp_path):
    r = cli("hooks", "install", "--project", str(tmp_path))
    assert r.returncode == 0 and "NOT_WRITTEN_NO_FLAG" in r.stdout
    assert not (tmp_path / ".claude").exists()


def test_install_write_idempotent_keeps_other_keys(tmp_path):
    (tmp_path / ".claude").mkdir()
    s = tmp_path / ".claude" / "settings.json"
    s.write_text(json.dumps({"permissions": {"allow": ["Bash(ls)"]}, "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo mine"}]}]}}))
    for _ in range(2):
        r = cli("hooks", "install", "--project", str(tmp_path), "--write")
        assert r.returncode == 0, r.stdout + r.stderr
    d = json.loads(s.read_text())
    assert d["permissions"] == {"allow": ["Bash(ls)"]}
    validate_claude_hooks({"hooks": d["hooks"]})
    stops = [h["command"] for e in d["hooks"]["Stop"] for h in e["hooks"]]
    assert "echo mine" in stops and len(stops) == 2 and len(set(stops)) == 2
    assert len(d["hooks"]["UserPromptSubmit"]) == 1


def test_install_write_creates_file(tmp_path):
    r = cli("hooks", "install", "--project", str(tmp_path), "--write")
    assert r.returncode == 0
    validate_claude_hooks(json.loads((tmp_path / ".claude" / "settings.json").read_text()))


def test_install_refuses_user_settings(tmp_path):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    env = _env(HOME=str(home))
    for proj in (home, home / ".claude", home / ".claude" / "x"):
        r = cli("hooks", "install", "--project", str(proj), "--write", env=env)
        assert r.returncode == 2 and "REFUSED_USER_SETTINGS" in r.stdout, (proj, r.stdout, r.stderr)
    assert not (home / ".claude" / "settings.json").exists()


def test_install_refuses_unparsable(tmp_path):
    (tmp_path / ".claude").mkdir()
    (tmp_path / ".claude" / "settings.json").write_text("{broken")
    r = cli("hooks", "install", "--project", str(tmp_path), "--write")
    assert r.returncode != 0 and "REFUSED_UNPARSABLE_SETTINGS" in r.stdout
    assert (tmp_path / ".claude" / "settings.json").read_text() == "{broken"


# ---- 静的検査 ---------------------------------------------------------------
MODS = ["hooks_templates.py", "run_recorder.py", "ledger_events.py"]
WRITE_ATTRS = {"write_text", "write_bytes", "replace", "rename", "unlink", "touch", "mkdir"}


def _funcs(tree):
    """各ノードを内側の関数名に結びつける。"""
    out = []

    def visit(n, fn):
        for c in ast.iter_child_nodes(n):
            f = c.name if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef)) else fn
            out.append((c, f))
            visit(c, f)
    visit(tree, "<module>")
    return out


def _docstring_ids(tree):
    ids = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
            b = n.body
            if b and isinstance(b[0], ast.Expr) and isinstance(getattr(b[0], "value", None), ast.Constant):
                ids.add(id(b[0].value))
    return ids


def test_static_no_home_expansion_and_user_settings_path_only_in_install():
    for m in MODS:
        tree = ast.parse((ROOT / "verantyx" / m).read_text(encoding="utf-8"))
        doc = _docstring_ids(tree)
        for n, fn in _funcs(tree):
            if isinstance(n, ast.Call):
                f = n.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
                assert name not in {"expanduser", "home"}, (m, fn, name)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in doc:
                assert not n.value.startswith("~"), (m, fn, n.value)
                if ".claude" in n.value or "settings.json" in n.value:
                    assert m == "hooks_templates.py" and fn == "install_project", (m, fn, n.value)


def test_static_write_calls_are_in_allowed_functions():
    """hooks_templates.py で書き込みの呼び出しがあるのは settings を書く 1 関数だけ。"""
    tree = ast.parse((ROOT / "verantyx" / "hooks_templates.py").read_text(encoding="utf-8"))
    sites = set()
    for n, fn in _funcs(tree):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute) and f.attr in WRITE_ATTRS:
                sites.add(fn)
            if isinstance(f, ast.Name) and f.id == "open":
                mode = ""
                if len(n.args) > 1 and isinstance(n.args[1], ast.Constant):
                    mode = str(n.args[1].value)
                for k in n.keywords:
                    if k.arg == "mode" and isinstance(k.value, ast.Constant):
                        mode = str(k.value.value)
                if any(c in mode for c in "wax+"):
                    sites.add(fn)
            if isinstance(f, ast.Attribute) and f.attr == "open":
                for a in list(n.args) + [k.value for k in n.keywords]:
                    if isinstance(a, ast.Constant) and isinstance(a.value, str) and any(c in a.value for c in "wax+"):
                        sites.add(fn)
    assert sites <= {"_write_settings_atomic"}, sites
    assert sites == {"_write_settings_atomic"}, "検査が意味を持つには書き込み関数が見つかる必要がある"


# ---- 第 2 ラウンド追加（レビュー必須 3）: シンボリックリンク経由でホームの設定に書かない -----------------
def test_install_refuses_symlinked_dot_claude_to_home(tmp_path):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text('{"theme":"dark"}\n')
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".claude").symlink_to(home / ".claude")
    for extra in (["--write"], []):
        r = cli("hooks", "install", "--project", str(proj), *extra, env=_env(HOME=str(home)))
        assert r.returncode == 2, (extra, r.stdout, r.stderr)
        assert "REFUSED_" in r.stdout
    assert json.loads((home / ".claude" / "settings.json").read_text()) == {"theme": "dark"}


def test_install_refuses_symlinked_settings_file_to_home(tmp_path):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "settings.json").write_text('{"theme":"dark"}\n')
    proj = tmp_path / "proj"
    (proj / ".claude").mkdir(parents=True)
    (proj / ".claude" / "settings.json").symlink_to(home / ".claude" / "settings.json")
    r = cli("hooks", "install", "--project", str(proj), "--write", env=_env(HOME=str(home)))
    assert r.returncode == 2 and "REFUSED_" in r.stdout
    assert json.loads((home / ".claude" / "settings.json").read_text()) == {"theme": "dark"}


def test_install_refuses_symlinked_dot_claude_to_home_missing_target(tmp_path):
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)          # settings.json は無い
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / ".claude").symlink_to(home / ".claude")
    r = cli("hooks", "install", "--project", str(proj), "--write", env=_env(HOME=str(home)))
    assert r.returncode == 2 and "REFUSED_" in r.stdout
    assert not (home / ".claude" / "settings.json").exists()
