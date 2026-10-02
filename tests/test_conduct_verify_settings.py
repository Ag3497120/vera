"""W2-b: the verifier settings, the read-only launch arguments, the read-only runtime, and the refusals
that happen before anything is started."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from test_conduct_entry_support import *  # noqa: F401,F403  (autouse guards + fixtures)
from test_conduct_entry_support import conduct_argv, read_ledger, rows_of, run_cli
from test_conduct_verify_support import (HONEST, IMPLEMENTER_SETTINGS, VERIFIER_SETTINGS, light_execute, new_repo,
                                         pool_fixture, register, sum_frame)


# ------------------------------------------------------------------ frame settings
SETTING_CASES = [
    ("verifier_adapter", "codex", True), ("verifier_adapter", "claude", True), ("verifier_adapter", "none", True),
    ("verifier_adapter", "gemini", False), ("verifier_adapter", "", False), ("verifier_adapter", "Claude", False),
    ("verifier_model", "claude-sonnet-5-5", True), ("verifier_model", "bad model", False),
    ("verifier_effort", "low", True), ("verifier_effort", "LOW", False), ("verifier_effort", 'lo"w', False),
    ("verifier_timeout_seconds", "900", True), ("verifier_timeout_seconds", "86400", True),
    ("verifier_timeout_seconds", "86401", False), ("verifier_timeout_seconds", "0", False),
    ("verifier_timeout_seconds", "-5", False), ("verifier_timeout_seconds", "1.5", False),
    ("verification_retries", "0", True), ("verification_retries", "2", True), ("verification_retries", "5", True),
    ("verification_retries", "6", False), ("verification_retries", "-1", False), ("verification_retries", "10", False),
    ("verification_retries", "two", False),
]


def test_the_new_agent_settings_are_validated_with_closed_patterns():
    from verantyx.project_frame import AGENT_SETTING_KEYS, validate_agent_setting

    for key, value, ok in SETTING_CASES:       # a loop, not 24 test items: every item pays the suite's per-test guards
        assert key in AGENT_SETTING_KEYS
        assert (validate_agent_setting(key, value) is None) is ok, (key, value, ok)


def test_the_existing_settings_still_validate_as_before():
    from verantyx.project_frame import validate_agent_setting

    assert validate_agent_setting("max_concurrency", "3") is None
    assert validate_agent_setting("max_concurrency", "0") is not None
    assert validate_agent_setting("agent_timeout_seconds", "600") is None
    assert validate_agent_setting("nonsense", "1") is not None


# ------------------------------------------------------------------ launch arguments
def test_the_default_launch_arguments_are_exactly_the_w2a_ones():
    from verantyx.agent_adapter import claude_print_launch, codex_exec_launch

    codex = codex_exec_launch(executable="codex", model="gpt-6-luna", effort="low", workdir="/w", prompt_path="/p",
                              last_message_path="/m")
    assert codex.argv == ("codex", "exec", "--ignore-user-config", "-m", "gpt-6-luna", "-c",
                          'model_reasoning_effort="low"', "-s", "workspace-write", "-C", "/w", "-o", "/m", "-")
    claude = claude_print_launch(executable="claude", model="m", effort="low", workdir="/w", prompt_path="/p")
    assert claude.argv == ("claude", "-p", "--model", "m", "--effort", "low")
    both = claude_print_launch(executable="claude", model="m", effort="low", workdir="/w", prompt_path="/p",
                               permission_mode="acceptEdits", allowed_tools="Edit,Write")
    assert both.argv[-4:] == ("--permission-mode", "acceptEdits", "--allowedTools", "Edit,Write")


def test_the_read_only_launch_arguments():
    from verantyx.agent_adapter import (VERIFIER_CLAUDE_ALLOWED_TOOLS, VERIFIER_CLAUDE_DISALLOWED_TOOLS,
                                        VERIFIER_CLAUDE_PERMISSION_MODE, claude_print_launch, codex_exec_launch)

    codex = codex_exec_launch(executable="codex", model="m", effort="low", workdir="/w", prompt_path="/p",
                              last_message_path="/m", sandbox="read-only")
    assert codex.argv[codex.argv.index("-s") + 1] == "read-only"
    for bad in ("danger-full-access", "", "READ-ONLY", None):
        with pytest.raises(ValueError):
            codex_exec_launch(executable="codex", model="m", effort="low", workdir="/w", prompt_path="/p",
                              last_message_path="/m", sandbox=bad)
    claude = claude_print_launch(executable="claude", model="m", effort="low", workdir="/w", prompt_path="/p",
                                 permission_mode=VERIFIER_CLAUDE_PERMISSION_MODE,
                                 allowed_tools=VERIFIER_CLAUDE_ALLOWED_TOOLS,
                                 disallowed_tools=VERIFIER_CLAUDE_DISALLOWED_TOOLS)
    assert claude.argv[6:] == ("--permission-mode", "dontAsk", "--disallowedTools",
                               "Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch", "--allowedTools", "Read,Grep,Glob")
    assert set(VERIFIER_CLAUDE_ALLOWED_TOOLS).isdisjoint(VERIFIER_CLAUDE_DISALLOWED_TOOLS)
    for bad in ("bash", "Bash(git *)", "", ["Bash", "Bash"]):
        with pytest.raises(ValueError):
            claude_print_launch(executable="claude", model="m", effort="low", workdir="/w", prompt_path="/p",
                                disallowed_tools=bad)


# ------------------------------------------------------------------ the read-only runtime
def make_linked_worktree(git_repo: Path, tmp_path: Path) -> Path:
    """A committed linked worktree, as the conductor's implementer worktree is."""
    work = tmp_path / "impl-worktree"
    subprocess.run(["git", "-C", str(git_repo), "worktree", "add", "--detach", str(work), "HEAD"],
                   check=True, capture_output=True)
    (work / "a.txt").write_text("candidate\n")
    subprocess.run(["git", "-C", str(work), "add", "a.txt"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(work), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "-m", "cand"],
                   check=True, capture_output=True)
    return work


def read_only_runtime(work: Path, tmp_path: Path, script: Path, **kwargs):
    from verantyx.agent_runtime import AgentRuntime

    return AgentRuntime(work, (), backend="claude-print", executable=str(script), model="m", effort="low",
                        state_dir=tmp_path / "vrt", read_only=True, poll_interval=0.02, timeout_seconds=30, **kwargs)


def drive(runtime, brief="Current frame task: T\nbody"):
    handle = runtime.start(brief)
    import time

    end = time.monotonic() + 30
    while not (handle.finalized and not handle.pending) and time.monotonic() < end:
        runtime.poll(handle)
    return handle


def script_in(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "fake-verifier.sh"
    path.write_text("#!/bin/sh\ncat > /dev/null\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def test_a_read_only_runtime_works_from_a_linked_worktree_and_leaves_no_copy(git_repo, tmp_path):
    work = make_linked_worktree(git_repo, tmp_path)
    runtime = read_only_runtime(work, tmp_path, script_in(tmp_path, 'cat a.txt\n'))
    assert runtime.allowed_paths == () and runtime.read_only is True
    handle = drive(runtime)
    assert handle.final_kind == "SESSION_ACCEPTED", handle.final_message
    assert "candidate" in (handle.session_dir / "agent.output").read_text()      # it saw the committed candidate
    assert not handle.worktree.exists()
    assert subprocess.run(["git", "-C", str(work), "status", "--porcelain"], capture_output=True, text=True).stdout == ""
    refs = subprocess.run(["git", "-C", str(git_repo), "for-each-ref"], capture_output=True, text=True).stdout
    assert refs.count("\n") == 1                                                    # still one branch, nothing new


def test_a_read_only_session_that_writes_is_rejected_and_its_copy_is_removed(git_repo, tmp_path):
    work = make_linked_worktree(git_repo, tmp_path)
    runtime = read_only_runtime(work, tmp_path, script_in(tmp_path, "echo x > new.txt\nrm a.txt\n"))   # an added and a deleted file
    handle = drive(runtime)
    assert handle.final_kind == "SESSION_REJECTED" and handle.final_message.startswith("write allowlist violation")
    assert "new.txt" in handle.final_message and "a.txt" in handle.final_message
    assert not handle.worktree.exists()


def test_a_read_only_runtime_refuses_what_would_give_it_write_access(git_repo, tmp_path):
    from verantyx.agent_runtime import AgentRuntime

    work = make_linked_worktree(git_repo, tmp_path)
    script = script_in(tmp_path, "true\n")
    base = dict(model="m", effort="low", state_dir=tmp_path / "x", read_only=True)
    with pytest.raises(ValueError):
        AgentRuntime(work, ("a.txt",), backend="claude-print", executable=str(script), **base)      # an allowlist
    with pytest.raises(ValueError):
        AgentRuntime(work, (), backend="claude-print", executable=str(script), claude_permission_mode="acceptEdits",
                     **base)
    with pytest.raises(ValueError):
        AgentRuntime(work, (), backend="claude-print", executable=str(script), claude_allowed_tools="Edit", **base)
    with pytest.raises(ValueError):
        AgentRuntime(work, (), backend="claude-print", executable=str(script), keep_worktree_on_accept=True, **base)
    for backend in ("codex", "command"):
        with pytest.raises(ValueError):
            AgentRuntime(work, (), backend=backend, executable=str(script), state_dir=tmp_path / "y", read_only=True)
    with pytest.raises(ValueError):
        AgentRuntime(work, (), backend="claude-print", executable=str(script), model="m", effort="low",
                     state_dir=tmp_path / "z", read_only="yes")
    # without read_only an empty allowlist is still refused, as before
    with pytest.raises(ValueError):
        AgentRuntime(work, (), backend="claude-print", executable=str(script), model="m", effort="low",
                     state_dir=tmp_path / "w")


def test_the_verifier_prompt_has_its_own_closing_text_and_the_implementer_prompt_is_unchanged(git_repo, tmp_path):
    from verantyx.agent_runtime import AgentRuntime

    work = make_linked_worktree(git_repo, tmp_path)
    script = script_in(tmp_path, "true\n")
    verifier = read_only_runtime(work, tmp_path, script)
    text = verifier._build_prompt("BRIEF")
    assert text.startswith("BRIEF") and "read-only verifier" in text
    assert "Runtime event protocol" not in text and "Write allowlist" not in text and "edit" not in text.lower().replace("edited", "")
    implementer = AgentRuntime(git_repo, ["src", "tests"], backend="claude-print", executable=str(script), model="m",
                               effort="low", state_dir=tmp_path / "impl")
    assert implementer._build_prompt("BRIEF") == (
        "BRIEF\n\nRuntime event protocol: write newline-delimited JSON events only. "
        "Use QUESTION {type,id,text,options?}, CLAIM {type,task,evidence}, "
        "DONE {type}, ERROR {type,message?}, or OTHER {type,text}. "
        "Do not include prose outside those events."
        "\nWrite allowlist (enforced after exit): src, tests. A change outside these paths rejects the whole session."
        "\nYour work: make the GOAL records of the current frame task true by editing files in "
        "the current directory, only within the write allowlist."
        "\nWhen you exit, the conductor runs the frame's acceptance commands itself in this "
        "directory; your own DONE or CLAIM events do not decide completion."
        "\nDo not run git commands that change history or references (commit, branch, reset, "
        "checkout); the conductor commits.")


# ------------------------------------------------------------------ refusals before anything starts
def _refusal_runs(base: Path) -> dict:
    """Every run here ends in a refusal before the implementer starts, so they share one pooled slot."""
    repo = new_repo(base / "shared-repo")      # a refusal never touches the repository, so the ten runs share one

    def go(name, settings, **kwargs):
        return light_execute(base / name, HONEST, frame=sum_frame(settings=settings), repo=repo, **kwargs)

    impl = IMPLEMENTER_SETTINGS
    return {
        "no_model": go("a", (*impl, "verifier_adapter: claude", "verifier_effort: low")),
        "no_effort": go("b", (*impl, "verifier_adapter: codex", "verifier_model: gpt-6-luna")),
        "none_and_model": go("c", (*impl, "verifier_adapter: none", "verifier_model: claude-sonnet-5-5")),
        "none_and_retries": go("d", (*impl, "verifier_adapter: none", "verification_retries: 1")),
        "model_without_adapter": go("e", (*impl, "verifier_model: claude-sonnet-5-5")),
        "retries_6_in_frame": go("f", (*impl, *VERIFIER_SETTINGS, "verification_retries: 6")),
        "retries_9_on_cli": light_execute(base / "g", HONEST, frame=sum_frame(), repo=repo, verification_retries=9),
        "adapter_gemini_on_cli": light_execute(base / "h", HONEST, frame=sum_frame(), repo=repo, verifier_adapter="gemini"),
        "timeout_0_on_cli": light_execute(base / "i", HONEST, frame=sum_frame(), repo=repo, verifier_timeout_seconds=0),
        "two_values_in_frame": go("j", (*impl, *VERIFIER_SETTINGS, "verifier_effort: high")),
    }


register("vset", {"refusals": _refusal_runs})
refusals = pool_fixture("vset")


def refused(run, reason):
    assert run.out["verdict"] == "REFUSED" and run.out["refusal"]["reason"] == reason, run.out["refusal"]
    assert run.of("AGENT_START_CALLED") == [], "the implementer must not be started for a refused setting"


def test_b4_f_a_verifier_without_a_model_or_effort_is_refused_before_the_implementer_starts(refusals):
    runs = refusals["refusals"]
    refused(runs["no_model"], "AGENT_SETTING_MISSING")
    assert "--verifier-model" in runs["no_model"].out["refusal"]["missing"]
    refused(runs["no_effort"], "AGENT_SETTING_MISSING")
    assert "--verifier-effort" in runs["no_effort"].out["refusal"]["missing"]


def test_b4_g_no_verifier_together_with_verifier_details_is_a_contradiction_not_a_choice(refusals):
    runs = refusals["refusals"]
    refused(runs["none_and_model"], "AGENT_SETTING_INVALID")
    refused(runs["none_and_retries"], "AGENT_SETTING_INVALID")


def test_verifier_details_without_an_adapter_are_refused_instead_of_guessing_one(refusals):
    refused(refusals["refusals"]["model_without_adapter"], "AGENT_SETTING_MISSING")


def test_a_bad_value_in_the_frame_or_on_the_command_line_is_refused(refusals):
    runs = refusals["refusals"]
    assert runs["retries_6_in_frame"].out["verdict"] == "REFUSED" and runs["retries_6_in_frame"].of("AGENT_START_CALLED") == []
    refused(runs["retries_9_on_cli"], "AGENT_SETTING_INVALID")
    refused(runs["adapter_gemini_on_cli"], "AGENT_SETTING_INVALID")
    refused(runs["timeout_0_on_cli"], "AGENT_SETTING_INVALID")


def test_the_two_frame_values_for_one_setting_are_refused(refusals):
    run = refusals["refusals"]["two_values_in_frame"]
    assert run.out["verdict"] == "REFUSED" and run.of("AGENT_START_CALLED") == []     # the frame parser refuses it


def test_the_settings_are_checked_in_a_dry_run_and_no_verifier_is_planned(git_repo, tmp_path, capsys, no_agent_process):
    bad = tmp_path / "bad.md"
    bad.write_text(sum_frame(settings=(*IMPLEMENTER_SETTINGS, "verifier_adapter: claude")), encoding="utf-8")
    code, out, _ = run_cli([str(x) for x in conduct_argv(bad, git_repo, "codex", "--dry-run", "--state-dir",
                                                         tmp_path / "s1")], capsys)
    assert (code, out["refusal"]["reason"]) == (2, "AGENT_SETTING_MISSING")
    good = tmp_path / "good.md"
    good.write_text(sum_frame(), encoding="utf-8")
    code, out, _ = run_cli([str(x) for x in conduct_argv(good, git_repo, "codex", "--dry-run", "--state-dir",
                                                         tmp_path / "s2")], capsys)
    assert (code, out["verdict"]) == (0, "DRY_RUN_PLANNED")
    types = [r["type"] for r in read_ledger(out["ledger"]) if r["run_id"] == out["run_id"]]
    assert not [t for t in types if t.startswith(("VERIFIER_", "VERIFICATION_"))]


def test_the_fake_adapter_and_dry_run_never_start_a_verifier(git_repo, tmp_path, capsys):
    frame = tmp_path / "frame.md"
    frame.write_text(sum_frame(), encoding="utf-8")
    code, out, _ = run_cli([str(x) for x in conduct_argv(frame, git_repo, "fake", "--state-dir", tmp_path / "s")], capsys)
    assert code in (0, 1)
    types = [r["type"] for r in read_ledger(out["ledger"]) if r["run_id"] == out["run_id"]]
    assert not [t for t in types if t.startswith(("VERIFIER_", "VERIFICATION_", "CANDIDATE"))]
    assert rows_of([r for r in read_ledger(out["ledger"]) if r["run_id"] == out["run_id"]], "CONDUCT_INVOKED")[0]["cli"][
        "require_verification"] is True


def test_the_toy_frames_are_ready_and_say_what_they_verify_with():
    from verantyx.project_frame import check_conduct_ready, load_conduct_frame

    root = Path(__file__).resolve().parents[1] / "docs" / "frames" / "toy"
    expected = {"greet": {"verifier_adapter": ("none",)},
                "sum_args": {"verifier_adapter": ("claude",), "verifier_model": ("claude-sonnet-5-5",),
                             "verifier_effort": ("low",), "verifier_timeout_seconds": ("600",),
                             "verification_retries": ("0",)},
                "mul_args_trap": {"verifier_adapter": ("claude",), "verifier_model": ("claude-sonnet-5-5",),
                                  "verifier_effort": ("low",), "verifier_timeout_seconds": ("600",),
                                  "verification_retries": ("1",)}}
    for name, settings in expected.items():
        frame = load_conduct_frame(root / f"{name}.md")
        assert check_conduct_ready(frame) is None
        assert {k: v for k, v in frame.agent_settings.items() if k.startswith("verif")} == settings
