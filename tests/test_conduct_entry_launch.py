"""Launch specifications and the runtime: the exact argument arrays, stdin handed over as a file
that ends (so a program reading stdin cannot wait forever), dry run sharing the real launch path,
and the older backends left exactly as they were."""
from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

import pytest

from test_conduct_entry_support import *  # noqa: F401,F403  (autouse guards + fixtures)
from test_conduct_entry_support import ROOT

BRIEF = "# Typed project frame\nRECORDS_JSON:\n[]\nCurrent frame task: Demo\n"


# ------------------------------------------------------------ launch specs
def test_codex_exec_launch_is_an_array_with_the_prompt_on_stdin_not_in_it():
    from verantyx.agent_adapter import LaunchSpec, codex_exec_launch

    spec = codex_exec_launch(executable="/x/codex", model="gpt-6-luna", effort="high", workdir="/w/tree",
                             prompt_path="/s/prompt.txt", last_message_path="/s/last.txt")
    assert isinstance(spec, LaunchSpec) and isinstance(spec.argv, tuple)
    assert spec.argv == ("/x/codex", "exec", "--ignore-user-config", "-m", "gpt-6-luna",
                         "-c", 'model_reasoning_effort="high"', "-s", "workspace-write",
                         "-C", "/w/tree", "-o", "/s/last.txt", "-")
    assert (spec.cwd, spec.stdin_path, spec.output_path, spec.backend) == ("/w/tree", "/s/prompt.txt", "/s/last.txt", "codex-exec")
    with pytest.raises(Exception):
        spec.argv = ()  # frozen


def test_claude_print_launch_is_an_array_run_in_the_work_directory():
    from verantyx.agent_adapter import claude_print_launch

    spec = claude_print_launch(executable="/x/claude", model="claude-sonnet-5-5", effort="max",
                               workdir="/w/tree", prompt_path="/s/prompt.txt")
    assert spec.argv == ("/x/claude", "-p", "--model", "claude-sonnet-5-5", "--effort", "max")
    assert (spec.cwd, spec.stdin_path, spec.output_path, spec.backend) == ("/w/tree", "/s/prompt.txt", None, "claude-print")


@pytest.mark.parametrize("model", ["", "a b", 'a"b', "-m", "a;b", "a\nb", "x" * 129, None, 7, "$(id)", "a`b`"])
def test_launch_rejects_models_that_are_not_plain_names(model):
    from verantyx.agent_adapter import claude_print_launch, codex_exec_launch

    kwargs = dict(executable="e", effort="high", workdir="/w", prompt_path="/p")
    with pytest.raises(ValueError):
        codex_exec_launch(model=model, last_message_path="/l", **kwargs)
    with pytest.raises(ValueError):
        claude_print_launch(model=model, **kwargs)


@pytest.mark.parametrize("effort", ["", "High", 'high"', "high x", "hi-gh", "a" * 17, None, "x\ny", '"; rm -rf /; "'])
def test_launch_rejects_efforts_that_could_break_out_of_the_toml_string(effort):
    from verantyx.agent_adapter import claude_print_launch, codex_exec_launch

    kwargs = dict(executable="e", model="m", workdir="/w", prompt_path="/p")
    with pytest.raises(ValueError):
        codex_exec_launch(effort=effort, last_message_path="/l", **kwargs)
    with pytest.raises(ValueError):
        claude_print_launch(effort=effort, **kwargs)


def test_the_older_read_only_command_builder_is_unchanged():
    from verantyx.agent_adapter import CodexExecAdapter

    command = CodexExecAdapter(project_dir="/p").build_command("hello")
    assert command == ["codex", "exec", "--ignore-user-config", "-m", "gpt-6-luna", "-c", 'service_tier="standard"',
                       "-s", "read-only", "-C", "/p", "--", "hello"]


def test_control_the_popen_guard_really_stops_a_non_git_process(no_agent_process):
    with pytest.raises(AssertionError):
        subprocess.Popen(["echo", "should not run"])
    no_agent_process.clear()  # the guard recorded its own probe; the fixture's end check must not count it
    assert subprocess.run(["git", "--version"], capture_output=True).returncode == 0  # git itself is still allowed


# ------------------------------------------------------------ the runtime, dry run
def _runtime(repo, tmp_path, backend="codex-exec", **kwargs):
    from verantyx.agent_runtime import AgentRuntime

    kwargs.setdefault("model", "gpt-6-luna")
    kwargs.setdefault("effort", "high")
    return AgentRuntime(repo, ["src", "tests"], backend=backend, state_dir=tmp_path / "rt", **kwargs)


def test_dry_run_runtime_plans_the_launch_and_creates_no_worktree_fifo_or_process(git_repo, tmp_path, no_agent_process):
    from verantyx.agent_runtime import DryRunHandle

    plans = []
    runtime = _runtime(git_repo, tmp_path, dry_run=True, on_plan=plans.append, executable="/x/codex")
    handle = runtime.start(BRIEF)
    assert isinstance(handle, DryRunHandle) and runtime.planned == plans and len(plans) == 1
    plan = plans[0]
    assert plan["argv"][:2] == ["/x/codex", "exec"] and plan["argv"][-1] == "-" and plan["task_id"] == "Demo"
    assert not Path(plan["cwd"]).exists()
    session = handle.session_dir
    assert sorted(p.name for p in session.iterdir()) == ["prompt.txt"]  # no fifo, lock, worktree, status
    assert (session / "prompt.txt").read_text(encoding="utf-8") == plan["prompt"]
    assert runtime.poll(handle) == [] and runtime.send(handle, "x") is None
    runtime.stop(handle)
    types = [row["type"] for row in runtime.session_rows()]
    assert types == ["SESSION_PLANNED", "DRY_RUN_STOPPED"]
    assert ".git" not in Path(runtime.state_dir).parts  # not the default .git/verantyx-agent-runtime
    listing = subprocess.run(["git", "-C", str(git_repo), "worktree", "list"], capture_output=True, text=True).stdout
    assert len(listing.strip().splitlines()) == 1


def test_dry_run_still_requires_a_git_repository_with_a_commit(tmp_path, no_agent_process):
    from verantyx.agent_runtime import AgentRuntime, RuntimeError as RuntimeErr

    with pytest.raises(Exception):
        AgentRuntime(tmp_path, ["src"], backend="claude-print", model="m", effort="low", dry_run=True, state_dir=tmp_path / "s")
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    subprocess.run(["git", "-C", str(fresh), "init", "-q"], check=True)
    runtime = AgentRuntime(fresh, ["src"], backend="claude-print", model="m", effort="low", dry_run=True, state_dir=tmp_path / "s2")
    with pytest.raises(RuntimeErr):
        runtime.start(BRIEF)  # no HEAD: the real launch would fail too


def test_runtime_option_rules(git_repo, tmp_path):
    from verantyx.agent_runtime import AgentRuntime

    with pytest.raises(ValueError):
        AgentRuntime(git_repo, ["src"], backend="codex-exec", state_dir=tmp_path / "a")  # model/effort are not defaults
    with pytest.raises(ValueError):
        AgentRuntime(git_repo, ["src"], backend="codex", model="m", effort="low", state_dir=tmp_path / "b")
    with pytest.raises(ValueError):
        AgentRuntime(git_repo, ["src"], backend="command", dry_run=True, state_dir=tmp_path / "c")
    with pytest.raises(ValueError):
        AgentRuntime(git_repo, ["src"], backend="nope", state_dir=tmp_path / "d")


def test_dry_run_and_real_start_build_the_prompt_and_the_launch_through_the_same_functions(git_repo, tmp_path, monkeypatch):
    from verantyx.agent_runtime import AgentRuntime

    calls = []
    for name in ("_build_prompt", "_launch_spec"):
        original = getattr(AgentRuntime, name)

        def spy(self, *a, _name=name, _orig=original, **k):
            calls.append((_name, self.dry_run))
            return _orig(self, *a, **k)

        monkeypatch.setattr(AgentRuntime, name, spy)
    exe = _fake_agent(tmp_path, "cat > \"$FAKE_STDIN_OUT\"\nprintf '%s\\n' '{\"type\":\"DONE\"}'\n")
    dry_plans, real_plans = [], []
    dry = _runtime(git_repo, tmp_path / "d", dry_run=True, on_plan=dry_plans.append, executable=str(exe))
    dry.start(BRIEF)
    real = _runtime(git_repo, tmp_path / "r", on_plan=real_plans.append, executable=str(exe),
                    timeout_seconds=20, env={"FAKE_STDIN_OUT": str(tmp_path / "stdin.out")})
    handle = real.start(BRIEF)
    try:
        _drain(real, handle)
    finally:
        real.stop(handle)
    assert ("_build_prompt", True) in calls and ("_build_prompt", False) in calls
    assert ("_launch_spec", True) in calls and ("_launch_spec", False) in calls
    d, r = dry_plans[0], real_plans[0]
    assert d["prompt"] == r["prompt"] and d["stdin"]["sha256"] == r["stdin"]["sha256"]
    strip = lambda argv: [a for a in argv if not a.startswith(str(tmp_path))]  # noqa: E731  (session-specific paths)
    assert strip(d["argv"]) == strip(r["argv"]) and d["dry_run"] is True and r["dry_run"] is False


# ------------------------------------------------------------ the runtime, real supervisor (fake program)
def _fake_agent(tmp_path, body, name="fake-agent.sh"):
    path = tmp_path / name
    path.write_text("#!/bin/sh\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def _drain(runtime, handle, seconds=15):
    events, deadline = [], time.monotonic() + seconds
    while time.monotonic() < deadline:
        batch = runtime.poll(handle)
        events.extend(batch)
        if any(e["type"] in ("DONE", "ERROR") for e in events) or handle.finalized:
            return events
        time.sleep(0.02)
    raise AssertionError("agent did not finish in time")


def test_stdin_ends_after_the_prompt_so_a_reader_of_stdin_finishes(git_repo, tmp_path):
    """The fake agent does `cat > file` first: it only gets past that line if stdin reaches EOF."""
    exe = _fake_agent(tmp_path, 'cat > "$FAKE_STDIN_OUT"\nprintf \'%s\\n\' "$@" > "$FAKE_ARGV_OUT"\nprintf \'%s\\n\' \'{"type":"DONE"}\'\n')
    out, argv_out = tmp_path / "stdin.out", tmp_path / "argv.out"
    plans = []
    runtime = _runtime(git_repo, tmp_path, executable=str(exe), timeout_seconds=20, on_plan=plans.append,
                       env={"FAKE_STDIN_OUT": str(out), "FAKE_ARGV_OUT": str(argv_out)})
    started = time.monotonic()
    handle = runtime.start(BRIEF)
    try:
        events = _drain(runtime, handle)
    finally:
        runtime.stop(handle)
    assert time.monotonic() - started < 10  # a hung cat would run into the 20 s timeout
    assert [e["type"] for e in events] == ["DONE"]
    plan = plans[0]
    assert out.read_text(encoding="utf-8") == plan["prompt"]
    assert hashlib.sha256(out.read_bytes()).hexdigest() == plan["stdin"]["sha256"]
    assert argv_out.read_text(encoding="utf-8").splitlines() == plan["argv"][1:]  # the array as planned, nothing joined or added
    assert plan["argv"][-1] == "-" and BRIEF.splitlines()[0] not in "\n".join(plan["argv"])
    types = [row["type"] for row in runtime.session_rows()]
    assert "PROCESS_STARTED" in types and "SESSION_ACCEPTED" in types


def test_claude_print_backend_gets_its_prompt_on_stdin_in_its_work_directory(git_repo, tmp_path):
    exe = _fake_agent(tmp_path, 'cat > "$FAKE_STDIN_OUT"\npwd > "$FAKE_CWD_OUT"\nprintf \'%s\\n\' "$@" > "$FAKE_ARGV_OUT"\nprintf \'%s\\n\' \'{"type":"DONE"}\'\n')
    outs = {k: tmp_path / f"{k}.out" for k in ("stdin", "cwd", "argv")}
    plans = []
    runtime = _runtime(git_repo, tmp_path, backend="claude-print", model="claude-sonnet-5-5", effort="low",
                       executable=str(exe), timeout_seconds=20, on_plan=plans.append,
                       env={"FAKE_STDIN_OUT": str(outs["stdin"]), "FAKE_CWD_OUT": str(outs["cwd"]), "FAKE_ARGV_OUT": str(outs["argv"])})
    handle = runtime.start(BRIEF)
    try:
        _drain(runtime, handle)
    finally:
        runtime.stop(handle)
    assert outs["stdin"].read_text(encoding="utf-8") == plans[0]["prompt"]
    assert outs["argv"].read_text(encoding="utf-8").splitlines() == ["-p", "--model", "claude-sonnet-5-5", "--effort", "low"]
    assert Path(outs["cwd"].read_text().strip()).resolve() == Path(plans[0]["cwd"]).resolve()


WAIT_FOR_EOF = f"""#!{sys.executable}
import os, select, sys
# A reader that waits for end-of-file the way a program polling its stdin does.
while True:
    try:
        data = os.read(0, 65536)
    except BlockingIOError:
        select.select([0], [], [], 0.1)
        continue
    if data == b"":
        break
sys.stdout.write('{{"type":"DONE"}}\\n')
"""


def _python_agent(tmp_path):
    path = tmp_path / "wait-for-eof.py"
    path.write_text(WAIT_FOR_EOF)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return path


def test_control_the_older_fifo_backend_never_gives_a_polling_reader_its_end_of_file(git_repo, tmp_path):
    """Why the new backends exist: through the FIFO this reader never sees EOF and hits the timeout."""
    runtime = _runtime(git_repo, tmp_path, backend="codex", model=None, effort=None,
                       executable=str(_python_agent(tmp_path)), timeout_seconds=2)
    handle = runtime.start(BRIEF)
    events = _drain(runtime, handle, seconds=10)
    assert [e["type"] for e in events] == ["ERROR"]
    assert "SESSION_TIMED_OUT" in [row["type"] for row in runtime.session_rows()]
    runtime.stop(handle)


def test_the_same_polling_reader_finishes_at_once_with_the_stdin_file_backends(git_repo, tmp_path):
    runtime = _runtime(git_repo, tmp_path, executable=str(_python_agent(tmp_path)), timeout_seconds=20)
    started = time.monotonic()
    handle = runtime.start(BRIEF)
    try:
        events = _drain(runtime, handle)
    finally:
        runtime.stop(handle)
    assert [e["type"] for e in events] == ["DONE"] and time.monotonic() - started < 10


def test_a_change_outside_the_allowlist_still_rejects_the_session(git_repo, tmp_path):
    exe = _fake_agent(tmp_path, 'cat > /dev/null\necho x > outside.txt\nprintf \'%s\\n\' \'{"type":"DONE"}\'\n')
    runtime = _runtime(git_repo, tmp_path, executable=str(exe), timeout_seconds=20)
    handle = runtime.start(BRIEF)
    try:
        events = _drain(runtime, handle)
    finally:
        runtime.stop(handle)
    assert [e["type"] for e in events] == ["ERROR"] and "allowlist" in events[0]["message"]
    assert "SESSION_REJECTED" in [row["type"] for row in runtime.session_rows()]


# ------------------------------------------------------------ older backends are untouched
def test_existing_runtime_backends_keep_their_command_shapes(git_repo, tmp_path):
    from verantyx.agent_runtime import AgentRuntime, _SUPERVISOR

    wt = tmp_path / "wt"
    command = AgentRuntime(git_repo, ["src"], backend="command", executable="/bin/echo -n", state_dir=tmp_path / "c")._command(wt, "PROMPT")
    assert command == ["/bin/echo", "-n", "--", "PROMPT"]
    codex = AgentRuntime(git_repo, ["src"], backend="codex", executable="/x/codex", state_dir=tmp_path / "x")._command(wt, "PROMPT")
    assert codex[:2] == ["/x/codex", "exec"] and codex[codex.index("-s") + 1] == "workspace-write"
    assert codex[-2:] == ["--", "PROMPT"] and 'service_tier="standard"' in codex
    # the supervisor still opens the FIFO unless it was given a stdin file
    assert 'os.open(config["fifo"], os.O_RDWR | os.O_NONBLOCK)' in _SUPERVISOR
    assert 'if config.get("stdin_path")' in _SUPERVISOR


def test_demo_runtime_and_demo_driver_still_run(tmp_path):
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
    for demo in ("demo_runtime.py", "demo_driver.py", "demo_conduct.py"):
        proc = subprocess.run([sys.executable, str(ROOT / "tools" / demo)], capture_output=True, text=True, env=env,
                              cwd=str(tmp_path), timeout=240)
        assert proc.returncode == 0 and "DEMO OK" in proc.stdout, (demo, proc.stdout[-300:], proc.stderr[-300:])
    leftovers = [p.name for p in ROOT.iterdir() if p.name.startswith(".demo-")]
    assert leftovers == []
