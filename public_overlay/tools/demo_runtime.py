"""Exercise the process boundary, scope rejection, timeout and recovery path."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from verantyx.agent_runtime import AgentRuntime


def _run(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, check=True)
    return result.stdout.strip()


def _repository(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    _run("git", "init", "-q", os.fspath(repo))
    _run("git", "-C", os.fspath(repo), "config", "user.name", "Runtime Demo")
    _run("git", "-C", os.fspath(repo), "config", "user.email", "runtime-demo@example.invalid")
    (repo / "safe.txt").write_text("safe-before\n", encoding="utf-8")
    (repo / "outside.txt").write_text("outside-before\n", encoding="utf-8")
    _run("git", "-C", os.fspath(repo), "add", "--", "safe.txt", "outside.txt")
    _run("git", "-C", os.fspath(repo), "commit", "-qm", "demo base")
    return repo


def _fake_codex(path: Path) -> Path:
    executable = path / "codex"
    executable.write_text(
        "#!/bin/sh\n"
        "project=''\n"
        "brief=''\n"
        "while [ \"$#\" -gt 0 ]; do\n"
        "  if [ \"$1\" = '-C' ]; then project=$2; shift 2; continue; fi\n"
        "  if [ \"$1\" = '--' ]; then shift; brief=${1-}; break; fi\n"
        "  shift\n"
        "done\n"
        "case \"$brief\" in\n"
        "  *RECOVER*) printf x >> \"$FAKE_COUNTER\"; sleep 0.6; printf '%s\\n' '{\"type\":\"DONE\"}' ;;\n"
        "  *HANG*) sleep 20 ;;\n"
        "  *) printf 'safe-after\\n' > \"$project/safe.txt\"; "
        "printf 'outside-attempt\\n' > \"$project/outside.txt\"; "
        "printf '%s\\n' '{\"type\":\"DONE\"}' ;;\n"
        "esac\n",
        encoding="utf-8",
    )
    executable.chmod(0o700)
    return executable


def _events(runtime: AgentRuntime, handle: object, timeout: float = 8.0) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        events.extend(runtime.poll(handle))
        if getattr(handle, "finalized") and not getattr(handle, "pending"):
            break
    assert getattr(handle, "finalized"), "runtime did not reach a terminal state"
    return events


def _group_gone(pgid: int) -> bool:
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return True
    except PermissionError:
        return False
    except OSError:
        return True
    return False


def _assert_group_gone(pgid: int) -> None:
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and not _group_gone(pgid):
        time.sleep(0.02)
    assert _group_gone(pgid), f"process group {pgid} survived the run"


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="vera-runtime-demo-") as temporary:
        root = Path(temporary)
        repo = _repository(root)
        executable = _fake_codex(root)

        scope_runtime = AgentRuntime(
            repo, ["safe.txt"], backend="codex", executable=os.fspath(executable),
            state_dir=root / "scope-state", timeout_seconds=3,
        )
        scope_handle = scope_runtime.start("Current frame task: scope-check\nTry one allowed and one forbidden edit.")
        scope_events = _events(scope_runtime, scope_handle)
        assert [event.get("type") for event in scope_events] == ["ERROR"]
        assert "outside.txt" in str(scope_events[0].get("message", ""))
        assert (repo / "safe.txt").read_text(encoding="utf-8") == "safe-before\n"
        assert (repo / "outside.txt").read_text(encoding="utf-8") == "outside-before\n"
        assert not scope_handle.worktree.exists()
        assert any(row.get("type") == "SESSION_REJECTED" for row in scope_runtime.session_rows())
        _assert_group_gone(scope_handle.pid)
        scope_runtime.stop(scope_handle)

        timeout_runtime = AgentRuntime(
            repo, ["safe.txt"], backend="codex", executable=os.fspath(executable),
            state_dir=root / "timeout-state", timeout_seconds=0.3,
        )
        timeout_handle = timeout_runtime.start("Current frame task: timeout-check\nHANG")
        timeout_events = _events(timeout_runtime, timeout_handle)
        assert [event.get("type") for event in timeout_events] == ["ERROR"]
        assert "timed out" in str(timeout_events[0].get("message", ""))
        assert any(row.get("type") == "SESSION_TIMED_OUT" for row in timeout_runtime.session_rows())
        assert not timeout_handle.worktree.exists()
        _assert_group_gone(timeout_handle.pid)
        timeout_runtime.stop(timeout_handle)

        recovery_state = root / "recovery-state"
        counter = root / "agent-start-count"
        driver = (
            "import os; from verantyx.agent_runtime import AgentRuntime; "
            f"runtime=AgentRuntime({os.fspath(repo)!r}, ['safe.txt'], backend='codex', "
            f"executable={os.fspath(executable)!r}, state_dir={os.fspath(recovery_state)!r}, "
            "timeout_seconds=3); "
            "runtime.start('Current frame task: recover-check\\nRECOVER'); os._exit(0)"
        )
        child_env = os.environ.copy()
        child_env["FAKE_COUNTER"] = os.fspath(counter)
        subprocess.run([sys.executable, "-c", driver], cwd=Path.cwd(), env=child_env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True, timeout=10)

        runtime = AgentRuntime(
            repo, ["safe.txt"], backend="codex", executable=os.fspath(executable),
            state_dir=recovery_state, timeout_seconds=3,
            env={"FAKE_COUNTER": os.fspath(counter)},
        )
        rows = runtime.session_rows()
        started = [row for row in rows if row.get("type") == "PROCESS_STARTED"]
        assert len(started) == 1
        original_pid = int(started[0]["pid"])
        recovered = runtime.recover("driver-run", "recover-check", 0)
        assert recovered.recovered and recovered.pid == original_pid
        recovery_events = _events(runtime, recovered)
        assert [event.get("type") for event in recovery_events] == ["DONE"]
        assert counter.read_text(encoding="utf-8") == "x"
        after = runtime.session_rows()
        assert len([row for row in after if row.get("type") == "PROCESS_STARTED"]) == 1
        assert len([row for row in after if row.get("type") == "SESSION_ADOPTED"]) == 1
        _assert_group_gone(recovered.pid)
        runtime.stop(recovered)

    print("DEMO OK")


if __name__ == "__main__":
    main()
