"""W2-b: the runtime's supervisor must not lose a verdict that the child wrote just before it exited.

The supervisor reads the child's output through a pipe.  A loaded machine can make the child print its last
bytes and exit between the supervisor's ``select`` (which saw nothing) and its ``poll`` (which sees the exit).
That used to end the loop with the bytes still in the pipe: an empty ``agent.output`` and exit code 0, which the
conductor reads as "the verifier gave no verdict".  The test makes that window certain instead of waiting for a
busy machine: the supervisor's first ``select`` is replaced by one that sleeps while the child runs to its end.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time

from test_conduct_entry_support import *  # noqa: F401,F403  (autouse guards + fixtures)
from test_conduct_run_support import WRITE_GOOD, execute
from verantyx import agent_runtime
from verantyx.agent_runtime import _SUPERVISOR

_WRAPPER = '''import select, sys, time
_real = select.select
_calls = []
def _slow_first(r, w, x, t=None):
    _calls.append(1)
    if len(_calls) == 1:
        time.sleep(1.0)            # the child prints and exits meanwhile
        return [], [], []          # ...and this select reports "nothing to read"
    return _real(r, w, x, t)
select.select = _slow_first
exec(compile(SOURCE, "<supervisor>", "exec"))
'''


def run_supervisor(tmp_path, shell_text: str, *, wrapped: bool) -> tuple[str, dict]:
    session = tmp_path / ("wrapped" if wrapped else "plain")
    session.mkdir()
    (session / "stdin.txt").write_text("", encoding="utf-8")
    (session / "agent.lock").write_text("", encoding="utf-8")
    (session / "command.json").write_text(json.dumps({
        "lock": str(session / "agent.lock"), "stdin_path": str(session / "stdin.txt"),
        "command": ["/bin/sh", "-c", shell_text], "cwd": str(session), "output": str(session / "agent.output"),
        "output_limit": 100000, "deadline_wall": time.time() + 60, "status": str(session / "agent.status.json")}),
        encoding="utf-8")
    code = ("SOURCE = " + repr(_SUPERVISOR) + "\n" + _WRAPPER) if wrapped else _SUPERVISOR
    done = subprocess.run([sys.executable, "-c", code, str(session)], capture_output=True, text=True, timeout=30)
    assert done.returncode == 0, done.stderr
    return (session / "agent.output").read_text(encoding="utf-8"), json.loads((session / "agent.status.json").read_text())


def test_the_supervisor_keeps_output_that_arrives_between_its_select_and_its_poll(tmp_path):
    output, status = run_supervisor(tmp_path, "echo VERA_VERDICT written-just-before-exit", wrapped=True)
    assert output == "VERA_VERDICT written-just-before-exit\n" and status == {"exit_code": 0, "output_limit": False}


def test_the_supervisor_still_ends_when_a_grandchild_keeps_the_pipe_open_and_silent(tmp_path):
    started = time.monotonic()
    output, status = run_supervisor(tmp_path, "echo first; sleep 3 &", wrapped=False)
    assert output == "first\n" and status["exit_code"] == 0
    assert time.monotonic() - started < 2.5        # it did not wait for the grandchild's sleep to end


def test_the_runtime_reads_the_output_once_more_when_it_finds_the_process_gone(tmp_path, monkeypatch):
    """The polling thread reads ``agent.output`` and only afterwards asks whether the process is still running.
    A loaded machine can stop the thread between the two while the agent prints and exits; the lines written in
    that gap used to be dropped when the run was finalized.  Here the question is answered late on purpose: it
    waits until the supervisor has written its status, so every line is already on disk when it is asked."""
    original = agent_runtime.AgentRuntime._process_running

    def late(self, handle):
        status = handle.session_dir / "agent.status.json"
        deadline = time.time() + 20
        while not status.exists() and time.time() < deadline:
            time.sleep(0.01)
        time.sleep(0.3)
        return original(self, handle)

    monkeypatch.setattr(agent_runtime.AgentRuntime, "_process_running", late)
    run = execute(tmp_path, "".join('echo "line %d of prose"\n' % n for n in range(40)) + WRITE_GOOD)
    assert run.out["outcome"] == "COMPLETE"
    assert run.one("AGENT_EXITED")["events_seen"] == {"OTHER": 40}
