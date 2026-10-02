"""W2-a: the conductor waits for a real agent process to end, runs the frame's acceptance commands
itself, and returns a typed outcome.  Agents here are shell scripts; nothing real is started."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from test_conduct_entry_support import *  # noqa: F401,F403  (autouse guards + fixtures)
from test_conduct_entry_support import ROOT, read_ledger
from test_conduct_run_support import (BAD_GREET, GOOD_GREET, WRITE_BAD, WRITE_GOOD, assert_nothing_left,
                                      default_criteria, dead, execute, frame_text, git, pool_fixture, register,
                                      repo_snapshot, spec, witness, write_script)

LIMIT_CODEX = "You’ve hit your usage limit. Try again later."
LIMIT_CLAUDE = "You've hit your session limit"
RECORD_PIDS = 'echo $$ > $PIDS/agent\nsleep 300 &\necho $! > $PIDS/grandchild\n'
CLAUDE = {"adapter": "claude", "model": "claude-sonnet-5-5", "effort": "low"}

# name: (script body, frame text or None, extra arguments, expected outcome)
SCENARIOS = {
    "S1_runs_long_then_finishes": ("sleep 5\n" + WRITE_GOOD, None, {}, "COMPLETE"),
    "S2_finishes_at_once_human_judgment_left": (
        WRITE_GOOD, frame_text(human=("A person finds the greeting friendly",)), {}, "HUMAN_JUDGMENT_PENDING"),
    "S3_exits_abnormally": (RECORD_PIDS + WRITE_GOOD + "exit 3\n", None, {}, "AGENT_FAILED"),
    "S4_usage_limit_codex_wording": (f'echo "{LIMIT_CODEX}"\nexit 1\n', None, {}, "AGENT_LIMIT_REACHED"),
    "S4_usage_limit_claude_wording": (
        f'echo "{LIMIT_CLAUDE}"\nexit 1\n',
        frame_text(settings=("claude_model: claude-sonnet-5-5", "claude_effort: low")), CLAUDE, "AGENT_LIMIT_REACHED"),
    "S5_exceeds_the_time_limit": (RECORD_PIDS + "sleep 60\n", None, {"agent_timeout_seconds": 2}, "TIMED_OUT"),
    "S6_writes_outside_the_allowlist": (WRITE_GOOD + "echo x > outside.txt\n", None, {}, "ALLOWLIST_VIOLATION"),
    "S7_claims_done_but_acceptance_fails": (
        WRITE_BAD + 'echo \'{"type":"DONE"}\'\necho "完了しました"\n'
        'echo \'{"type":"CLAIM","task":"Greeter","evidence":["greet.py"]}\'\n', None, {}, "ACCEPTANCE_FAILED"),
}
assert len({v[3] for v in SCENARIOS.values()}) == 7

# Extra runs used by the controls and the R4 detections (name: (body, frame, kwargs)).
EXTRAS = {
    "control_complete_at_once": (WRITE_GOOD, None, {}),
    "control_limit_sentence_but_worked": (f'echo "{LIMIT_CODEX}"\n' + WRITE_GOOD, None, {}),
    "limit_sentence_and_no_work": (f'echo "{LIMIT_CLAUDE}"\n', None, {}),
    "output_over_the_limit": (RECORD_PIDS + "yes 'some prose line' | head -c 20000\nsleep 30\n", None,
                              {"agent_output_limit": 2000}),
    "prose_lines": ("".join('echo "line %d of prose"\n' % n for n in range(250)) + WRITE_GOOD, None, {}),
    "agent_commits": (WRITE_GOOD + "git -c user.name=a -c user.email=a@a.invalid add greet.py\n"
                      "git -c user.name=a -c user.email=a@a.invalid commit -q -m sneaky\n", None, {}),
    "agent_moves_a_ref": (WRITE_GOOD + 'git -C "$(git rev-parse --git-common-dir)/.." branch evil\n', None, {}),
    "state_inside_the_repo": (WRITE_GOOD, None, {"state_dir": None}),
}


register("run", {name: spec(body, frame, **kwargs) for name, (body, frame, kwargs) in
                 {**{k: (v[0], v[1], v[2]) for k, v in SCENARIOS.items()}, **EXTRAS}.items()})
runs = pool_fixture("run")   # every scripted run above, started together with the other modules' runs


# ------------------------------------------------------------------ R1
def test_r1_a_five_second_agent_is_awaited_and_the_conductor_runs_the_acceptance_itself(runs):
    run = runs["S1_runs_long_then_finishes"]
    exited = run.one("AGENT_EXITED")
    print(f"R1 elapsed_seconds={exited['elapsed_seconds']}")
    assert run.out["outcome"] == "COMPLETE" and run.out["verdict"] == "RUN_COMPLETE"
    assert exited["elapsed_seconds"] >= 5.0          # the old path stopped the agent after 0.58 s
    assert exited["runtime_terminal"] == "SESSION_ACCEPTED" and exited["exit_code"] == 0
    assert all(r["type"] != "SESSION_CANCELLED" for r in run.runtime_rows())
    commands = run.of("ACCEPTANCE_COMMAND")
    assert [c["status"] for c in commands] == ["PASS", "PASS"]
    assert commands[0]["stdout"] == "Hello, Vera!\n" and commands[0]["sandbox"] == "sandbox-exec"
    assert run.types == [
        "CONDUCT_INVOKED", "FRAME_READ", "FRAME_COMPILED", "RUN_LIMITS", "REPO_GUARD", "AGENT_START_CALLED",
        "LAUNCH_PLANNED", "AGENT_START_RETURNED", "AGENT_WAITING", "AGENT_EXITED", "AGENT_PROCESS_CHECK",
        "REPO_GUARD", "SANDBOX_CHECK", "ACCEPTANCE_COMMAND", "ACCEPTANCE_COMMAND", "ACCEPTANCE_SIDE_EFFECTS",
        "COMMIT", "RUN_FINISHED"]
    assert [r["seq"] for r in read_ledger(run.out["ledger"])] == list(range(len(run.types)))


# ------------------------------------------------------------------ R2
@pytest.mark.parametrize("name", list(SCENARIOS))
def test_r2_each_scenario_ends_in_its_own_type_and_leaves_no_process(name, runs):
    run = runs[name]
    expected = SCENARIOS[name][3]
    assert run.out["outcome"] == expected, run.one("RUN_FINISHED")
    assert run.out["verdict"] == ("RUN_COMPLETE" if expected == "COMPLETE" else "RUN_INCOMPLETE")
    assert run.one("RUN_FINISHED")["outcome"] == expected
    assert_nothing_left(run)
    exited = run.one("AGENT_EXITED")
    if expected == "AGENT_FAILED":
        assert exited["exit_code"] == 3 and run.out["blocking"]["kind"] == "AGENT_FAILED"
    if expected == "TIMED_OUT":
        # The supervisor kills itself at the deadline; this must read as a time-out, not as exit -9.
        assert exited["runtime_terminal"] == "SESSION_TIMED_OUT" and exited["guard_deadline_used"] is False
    if expected == "AGENT_LIMIT_REACHED":
        assert exited["limit_text_seen"] is True and exited["exit_code"] == 1
    if expected == "ACCEPTANCE_FAILED":
        assert [c["status"] for c in run.of("ACCEPTANCE_COMMAND")] == ["PASS", "FAIL"]
        assert len(run.out["blocking"]["failed_criteria"]) == 1
    if expected in ("ALLOWLIST_VIOLATION", "ACCEPTANCE_FAILED", "AGENT_FAILED", "TIMED_OUT", "AGENT_LIMIT_REACHED"):
        assert run.of("COMMIT") == []


def test_r2_the_seven_scenarios_have_seven_different_types():
    assert len({v[3] for v in SCENARIOS.values()}) == 7


def test_r2_control_an_agent_that_ends_at_once_and_does_well_is_complete(runs):
    run = runs["control_complete_at_once"]
    assert run.out["outcome"] == "COMPLETE" and len(run.of("COMMIT")) == 1
    assert_nothing_left(run)


def test_r2_control_a_usage_limit_sentence_is_not_a_limit_when_the_agent_exited_zero_and_worked(runs):
    run = runs["control_limit_sentence_but_worked"]
    exited = run.one("AGENT_EXITED")
    assert exited["limit_text_seen"] is True and exited["exit_code"] == 0
    assert run.out["outcome"] == "COMPLETE"


def test_r2_the_usage_limit_with_no_work_and_exit_zero_is_still_the_limit(runs):
    assert runs["limit_sentence_and_no_work"].out["outcome"] == "AGENT_LIMIT_REACHED"


def test_r2_a_missing_executable_is_a_typed_start_failure(tmp_path):
    run = execute(tmp_path, "true\n", codex_bin=str(tmp_path / "no-such-codex"))
    assert run.out["outcome"] == "AGENT_START_FAILED" and run.of("AGENT_START_CALLED") == []
    assert run.one("AGENT_START_FAILED")["error"] == "ExecutableNotFound"


def test_r2_output_over_the_limit_is_its_own_type_and_the_group_is_gone(runs):
    run = runs["output_over_the_limit"]
    assert run.out["outcome"] == "OUTPUT_LIMIT"
    assert_nothing_left(run)


def test_r2_prose_lines_are_not_questions_and_do_not_end_the_run(runs):
    run = runs["prose_lines"]
    assert run.out["outcome"] == "COMPLETE"
    assert run.one("AGENT_EXITED")["events_seen"] == {"OTHER": 250}   # more than the old 100-event ceiling, all ignored


def test_r2_signals_are_only_taken_over_in_the_main_thread_and_the_ledger_says_so(runs):
    # the pooled runs were started from worker threads: no handler was installed, and nothing pretends one was
    assert runs["control_complete_at_once"].one("AGENT_WAITING")["signal_handlers"] is False


def test_r2_the_conductors_own_deadline_stops_an_agent_that_the_runtime_deadline_did_not(tmp_path, monkeypatch):
    from verantyx import conductor_run

    monkeypatch.setattr(conductor_run, "GUARD_GRACE_SECONDS", -1000.0)   # the guard is already past at the start
    run = execute(tmp_path, RECORD_PIDS + "sleep 60\n", agent_timeout_seconds=600)
    exited = run.one("AGENT_EXITED")
    assert run.out["outcome"] == "TIMED_OUT" and exited["guard_deadline_used"] is True
    assert exited["runtime_terminal"] == "SESSION_CANCELLED"
    assert_nothing_left(run)


def test_r2_the_agent_prompt_tells_it_that_the_conductor_decides(runs):
    prompt = runs["control_complete_at_once"].one("LAUNCH_PLANNED")["prompt"]
    for sentence in ("Your work: make the GOAL records of the current frame task true",
                     "the conductor runs the frame's acceptance commands itself in this directory",
                     "Do not run git commands that change history or references"):
        assert sentence in prompt


# ------------------------------------------------------------------ R4
def test_r4_a_complete_run_commits_only_inside_the_worktree_and_leaves_the_repository_alone(runs):
    run = runs["S1_runs_long_then_finishes"]
    # refs, HEAD, symbolic HEAD, status (with ignored), files and the commits reachable from refs are unchanged;
    # only `log --all` (which also lists linked worktree HEADs) gains the conductor's commit.
    assert {k: v for k, v in run.before.items() if k != "log_all"} == {k: v for k, v in run.after.items() if k != "log_all"}
    commit = run.one("COMMIT")
    worktree = Path(commit["worktree"])
    base = run.one("LAUNCH_PLANNED")["base_commit"]
    assert commit["parent"] == base and commit["paths"] == ["greet.py"]
    assert git(worktree, "rev-parse", "HEAD")[1].strip() == commit["sha"]
    assert git(worktree, "rev-parse", "HEAD~1")[1].strip() == base
    assert git(run.repo, "branch", "--contains", commit["sha"])[1].strip() == ""
    assert git(worktree, "show", "--name-only", "--format=", "HEAD")[1].split() == ["greet.py"]
    assert run.one("RUN_FINISHED")["worktree_kept"] is True
    assert not (run.repo / "greet.py").exists()


def test_r4_an_agent_that_writes_outside_the_allowlist_fails_and_nothing_is_committed(runs):
    run = runs["S6_writes_outside_the_allowlist"]
    assert run.out["outcome"] == "ALLOWLIST_VIOLATION"
    assert run.before == run.after
    assert run.of("COMMIT") == [] and run.of("COMMIT_SKIPPED") == [] and run.of("ACCEPTANCE_COMMAND") == []
    assert "outside.txt" in run.one("AGENT_EXITED")["terminal_message"]
    assert not any(Path(r["worktree"]).exists() for r in run.of("AGENT_WAITING"))   # the worktree is gone
    assert git(run.repo, "log", "--all", "--oneline")[1] == run.before["log_all"][1]


def test_r4_an_agent_that_commits_in_its_worktree_is_detected(runs):
    run = runs["agent_commits"]
    assert run.out["outcome"] == "AGENT_COMMITTED"
    assert run.of("COMMIT") == [] and run.before == run.after


def test_r4_an_agent_that_moves_a_ref_of_the_original_repository_is_detected(runs):
    run = runs["agent_moves_a_ref"]
    assert run.out["outcome"] == "REPO_CHANGED"
    guard = run.of("REPO_GUARD")
    assert [g["when"] for g in guard] == ["before", "after"] and guard[1]["changed"] is True
    assert "refs/heads/evil" in guard[1]["refs"] and "refs/heads/evil" not in guard[0]["refs"]
    assert run.of("COMMIT") == []


def test_r4_the_state_directory_inside_the_repository_is_not_a_repository_change(runs):
    run = runs["state_inside_the_repo"]
    assert run.out["outcome"] == "COMPLETE"
    assert str(run.state) == str(run.repo / ".verantyx-conduct") or str(run.state).endswith("/repo/.verantyx-conduct")


# ------------------------------------------------------------------ STOP
def _wait_for_row(ledger_dir_getter, kind, timeout=20.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        path = ledger_dir_getter()
        if path.exists():
            for line in path.read_text().splitlines():
                row = json.loads(line)
                if row["type"] == kind:
                    return row
        time.sleep(0.05)
    raise AssertionError(f"no {kind} row appeared")


def test_r2_a_stop_file_stops_the_agent_and_its_children(tmp_path):
    state = tmp_path / "state"

    def stopper():
        row = _wait_for_row(lambda: state / "ledger.jsonl", "AGENT_WAITING")
        Path(row["stop_file"]).write_text("stop\n")

    thread = threading.Thread(target=stopper, daemon=True)
    thread.start()
    started = time.monotonic()
    run = execute(tmp_path, RECORD_PIDS + "sleep 120\n")
    thread.join(5)
    assert run.out["outcome"] == "STOPPED" and run.one("AGENT_EXITED")["stop_source"] == "file"
    assert run.one("AGENT_WAITING")["signal_handlers"] is True      # called from the main thread
    assert time.monotonic() - started < 30
    assert_nothing_left(run)
    assert run.of("COMMIT") == []


def test_r2_sigterm_to_the_conductor_stops_the_agent_and_its_children(tmp_path):
    state = tmp_path / "state"
    repo = tmp_path / "repo"
    repo.mkdir()
    pids = tmp_path / "pids"
    pids.mkdir()
    for args in (["init", "-q"], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "i"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    script = write_script(tmp_path / "agent.sh", RECORD_PIDS.replace("$PIDS", str(pids)) + "sleep 120\n")
    frame = tmp_path / "f.md"
    frame.write_text(frame_text(), encoding="utf-8")
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.Popen([sys.executable, "-m", "verantyx.cli", "conduct", "--frame", str(frame), "--repo", str(repo),
                             "--adapter", "codex", "--codex-bin", str(script), "--state-dir", str(state)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    try:
        _wait_for_row(lambda: state / "ledger.jsonl", "AGENT_WAITING")
        time.sleep(0.3)
        proc.send_signal(signal.SIGTERM)
        stdout, stderr = proc.communicate(timeout=30)
    finally:
        if proc.poll() is None:
            proc.kill()
    out = json.loads(stdout)
    assert (proc.returncode, out["outcome"], out["verdict"]) == (1, "STOPPED", "RUN_INCOMPLETE"), stderr
    rows = [r for r in read_ledger(out["ledger"]) if r["run_id"] == out["run_id"]]
    assert [r for r in rows if r["type"] == "AGENT_EXITED"][0]["stop_source"] == "signal"
    pid_files = sorted(state.glob("runs/*/runtime/sessions/*/agent.pid.json"))
    leftovers = [int(p.read_text()) for p in pids.glob("*")] + [json.loads(f.read_text())["pid"] for f in pid_files]
    assert leftovers and all(dead(pid) for pid in leftovers)
