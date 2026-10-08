"""W2-a settings: time limits (frame / command line / default), the Claude write permission in the
argument array (R6), and the toy frame run through a scripted codex."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_conduct_entry_support import *  # noqa: F401,F403  (autouse guards + fixtures)
from test_conduct_entry_support import ROOT, VERA_FRAME, conduct_argv, read_ledger, rows_of, run_cli
from test_conduct_run_support import GOOD_GREET, WRITE_GOOD, execute, frame_text, write_script

CLAUDE_SETTINGS = ("claude_model: claude-sonnet-5-5", "claude_effort: low")
TOY = ROOT / "docs" / "frames" / "toy" / "greet.md"


def cargv(*args):
    return [str(item) for item in conduct_argv(*args)]


def plan_of(out):
    return [r for r in rows_of(read_ledger(out["ledger"]), "LAUNCH_PLANNED") if r["run_id"] == out["run_id"]][0]


def claude_frame(tmp_path, *extra):
    path = tmp_path / "claude.md"
    path.write_text(frame_text(settings=(*CLAUDE_SETTINGS, *extra)), encoding="utf-8")
    return path


# ------------------------------------------------------------------ R6: claude write permission
def test_r6_the_frame_can_give_the_permission_mode_and_tools(git_repo, tmp_path, capsys, no_agent_process):
    frame = claude_frame(tmp_path, "claude_permission_mode: acceptEdits", "claude_allowed_tools: Edit,Write")
    code, out, _ = run_cli(cargv(frame, git_repo, "claude", "--dry-run", "--state-dir", tmp_path / "s"), capsys)
    assert (code, out["verdict"]) == (0, "DRY_RUN_PLANNED")
    plan = plan_of(out)
    assert plan["argv"] == ["claude", "-p", "--model", "claude-sonnet-5-5", "--effort", "low",
                            "--permission-mode", "acceptEdits", "--allowedTools", "Edit,Write"]
    assert plan["permission_mode"] == {"value": "acceptEdits", "source": "frame"}
    assert plan["allowed_tools"] == {"value": "Edit,Write", "source": "frame"}


def test_r6_the_command_line_beats_the_frame(git_repo, tmp_path, capsys, no_agent_process):
    frame = claude_frame(tmp_path, "claude_permission_mode: plan", "claude_allowed_tools: Read")
    code, out, _ = run_cli(cargv(frame, git_repo, "claude", "--dry-run", "--state-dir", tmp_path / "s",
                                        "--permission-mode", "acceptEdits", "--allowed-tools", "Edit,Write"), capsys)
    plan = plan_of(out)
    assert plan["argv"][-4:] == ["--permission-mode", "acceptEdits", "--allowedTools", "Edit,Write"]
    assert plan["permission_mode"]["source"] == "cli" and plan["allowed_tools"]["source"] == "cli"


def test_r6_with_neither_the_argument_array_is_the_older_one_and_the_ledger_says_unset(git_repo, tmp_path, capsys,
                                                                                        no_agent_process):
    code, out, _ = run_cli(cargv(claude_frame(tmp_path), git_repo, "claude", "--dry-run",
                                        "--state-dir", tmp_path / "s"), capsys)
    plan = plan_of(out)
    assert plan["argv"] == ["claude", "-p", "--model", "claude-sonnet-5-5", "--effort", "low"]
    assert plan["permission_mode"] == {"value": None, "source": "unset"}
    assert plan["allowed_tools"] == {"value": None, "source": "unset"}


@pytest.mark.parametrize("flag, value", [
    ("--permission-mode", "bypassPermissions"), ("--permission-mode", "auto"), ("--permission-mode", "yolo"),
    ("--allowed-tools", "Bash(git *)"), ("--allowed-tools", "Edit,Edit"), ("--allowed-tools", "edit"),
    ("--allowed-tools", "Edit;Write"), ("--allowed-tools", ""),
])
def test_r6_unsafe_permission_values_are_refused(flag, value, git_repo, tmp_path, capsys, no_agent_process):
    code, out, _ = run_cli(cargv(claude_frame(tmp_path), git_repo, "claude", "--dry-run",
                                        "--state-dir", tmp_path / "s", flag, value), capsys)
    assert (code, out["refusal"]["reason"]) == (2, "AGENT_SETTING_INVALID")


def test_r6_bypass_in_the_frame_is_a_parse_error_with_its_line(git_repo, tmp_path, capsys):
    frame = claude_frame(tmp_path, "claude_permission_mode: bypassPermissions")
    code, out, _ = run_cli(cargv(frame, git_repo, "claude", "--dry-run", "--state-dir", tmp_path / "s"), capsys)
    assert (code, out["refusal"]["reason"]) == (2, "FRAME_PARSE_ERROR") and out["refusal"]["line"]
    assert "bypassPermissions" in out["refusal"]["missing"]


def test_r6_codex_does_not_take_claude_permission_options(git_repo, tmp_path, capsys, no_agent_process):
    code, out, _ = run_cli(cargv(TOY, git_repo, "codex", "--dry-run", "--state-dir", tmp_path / "s",
                                        "--permission-mode", "acceptEdits"), capsys)
    assert (code, out["refusal"]["reason"]) == (2, "AGENT_SETTING_INVALID")
    assert "claude" in out["refusal"]["missing"]


def test_r6_a_real_claude_start_receives_the_write_permission_at_the_end_of_its_arguments(tmp_path):
    record = tmp_path / "argv.txt"
    body = f"printf '%s\\n' \"$@\" > {record}\n" + WRITE_GOOD
    run = execute(tmp_path / "w", body, adapter="claude", model="claude-sonnet-5-5", effort="low",
                  permission_mode="acceptEdits", allowed_tools="Edit,Write",
                  frame=frame_text(settings=CLAUDE_SETTINGS))
    assert run.out["outcome"] == "COMPLETE"
    assert record.read_text().split() == ["-p", "--model", "claude-sonnet-5-5", "--effort", "low",
                                          "--permission-mode", "acceptEdits", "--allowedTools", "Edit,Write"]


# ------------------------------------------------------------------ time limits
def test_the_default_time_limits_are_recorded_as_defaults(git_repo, tmp_path, capsys, no_agent_process):
    frame = tmp_path / "f.md"
    frame.write_text(frame_text(), encoding="utf-8")
    code, out, _ = run_cli(cargv(frame, git_repo, "codex", "--dry-run", "--state-dir", tmp_path / "s"), capsys)
    plan = plan_of(out)
    assert plan["agent_timeout_seconds"] == {"value": 1800, "source": "default"}
    assert plan["acceptance_timeout_seconds"] == {"value": 600, "source": "default"}


def test_the_frame_sets_the_agent_limit_and_the_command_line_beats_it(git_repo, tmp_path, capsys, no_agent_process):
    code, out, _ = run_cli(cargv(TOY, git_repo, "codex", "--dry-run", "--state-dir", tmp_path / "s"), capsys)
    assert plan_of(out)["agent_timeout_seconds"] == {"value": 600, "source": "frame"}
    code, out, _ = run_cli(cargv(TOY, git_repo, "codex", "--dry-run", "--state-dir", tmp_path / "t",
                                        "--agent-timeout-seconds", "90", "--acceptance-timeout-seconds", "45"), capsys)
    plan = plan_of(out)
    assert plan["agent_timeout_seconds"] == {"value": 90, "source": "cli"}
    assert plan["acceptance_timeout_seconds"] == {"value": 45, "source": "cli"}


@pytest.mark.parametrize("bad", [0, 86401, 1.5, -3])
@pytest.mark.parametrize("key", ["agent_timeout_seconds", "acceptance_timeout_seconds"])
def test_unusable_time_limits_are_refused(key, bad, git_repo, tmp_path):
    from verantyx.conductor_run import conduct_entry

    outcome = conduct_entry(TOY, git_repo, "codex", dry_run=True, state_dir=tmp_path / "s", **{key: bad})
    assert (outcome.verdict, outcome.refusal["reason"]) == ("REFUSED", "AGENT_SETTING_INVALID")


@pytest.mark.parametrize("line", ["agent_timeout_seconds: 0", "agent_timeout_seconds: 90000",
                                  "acceptance_timeout_seconds: 1.5", "agent_timeout_seconds: ten"])
def test_unusable_time_limits_in_a_frame_are_parse_errors_with_a_line(line, git_repo, tmp_path, capsys):
    frame = tmp_path / "f.md"
    frame.write_text(frame_text(settings=("codex_model: gpt-6-luna", "codex_effort: low", line)), encoding="utf-8")
    code, out, _ = run_cli(cargv(frame, git_repo, "codex", "--dry-run", "--state-dir", tmp_path / "s"), capsys)
    assert (code, out["refusal"]["reason"]) == (2, "FRAME_PARSE_ERROR") and out["refusal"]["line"]


def test_the_limits_are_in_the_run_limits_row_of_a_real_run(tmp_path):
    run = execute(tmp_path, WRITE_GOOD, agent_timeout_seconds=77, acceptance_timeout_seconds=33)
    limits = run.one("RUN_LIMITS")
    assert limits["agent_timeout_seconds"] == {"value": 77, "source": "cli"}
    assert limits["acceptance_timeout_seconds"] == {"value": 33, "source": "cli"}
    assert limits["output_limit_bytes"] == 8 * 1024 * 1024 and limits["stop_file"].endswith("/STOP")


# ------------------------------------------------------------------ the toy frame
def test_the_toy_frame_runs_end_to_end_with_a_scripted_codex(git_repo, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("PATH", f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}")
    script = write_script(tmp_path / "fake-codex.sh", f"printf '%s\\n' '{GOOD_GREET}' > greet.py\n")
    code, out, err = run_cli(cargv(TOY, git_repo, "codex", "--codex-bin", script, "--state-dir", tmp_path / "s"),
                             capsys)
    assert (code, out["verdict"], out["outcome"]) == (0, "RUN_COMPLETE", "COMPLETE"), err
    rows = [r for r in read_ledger(out["ledger"]) if r["run_id"] == out["run_id"]]
    first = rows_of(rows, "ACCEPTANCE_COMMAND")[0]
    assert first["argv"] == ["python", "greet.py", "Vera"] and first["stdout"] == "Hello, Vera!\n"
    assert rows_of(rows, "LAUNCH_PLANNED")[0]["model"]["value"] == "gpt-6-luna"
    assert rows_of(rows, "RUN_LIMITS")[0]["agent_timeout_seconds"] == {"value": 600, "source": "frame"}
