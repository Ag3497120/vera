"""Run external project agents in disposable Git worktrees.

The runtime is an orchestration adapter, not an answer producer. Agent output
is parsed through ``agent_adapter`` and stays untrusted. A terminal ``DONE``
event is released only after the child exits and the complete worktree diff
passes the declared path allowlist.
"""
from __future__ import annotations

import json
import fcntl
import math
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import agent_adapter
from .agent_adapter import AgentEvent, CodexExecAdapter


RUNTIME_SCHEMA = "agent-runtime-v1"
DEFAULT_TIMEOUT_SECONDS = 300.0
DEFAULT_OUTPUT_LIMIT = 65536
DEFAULT_DIFF_LIMIT = 5 * 1024 * 1024
_TASK_LINE = re.compile(r"^Current frame task:\s*(.*?)\s*$", re.M)
_TERMINAL_EVENTS = frozenset({
    "SESSION_ACCEPTED", "SESSION_REJECTED", "SESSION_PROCESS_FAILED",
    "SESSION_OUTPUT_LIMIT", "SESSION_TIMED_OUT", "SESSION_CANCELLED",
    "SESSION_INTERRUPTED", "SESSION_START_FAILED",
})


class RuntimeError(ValueError):
    """The durable runtime journal or process identity cannot be trusted."""


def _finite_positive(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a positive finite number")
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError(f"{name} must be a positive finite number")
    return result


def _git(repo: Path, *args: str, timeout: float = 30.0) -> bytes:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    result = subprocess.run(
        ["git", "-C", os.fspath(repo), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        timeout=timeout,
        check=False,
    )
    if result.returncode:
        message = result.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(message[:512] or f"git command failed: {args[0]}")
    return result.stdout


def _git_root(repo: str | os.PathLike[str]) -> Path:
    requested = Path(repo).expanduser().resolve()
    root = Path(os.fsdecode(_git(requested, "rev-parse", "--show-toplevel")).strip()).resolve()
    return root


def _git_common_dir(root: Path) -> Path:
    common = Path(os.fsdecode(_git(root, "rev-parse", "--git-common-dir")).strip())
    return common.resolve() if common.is_absolute() else (root / common).resolve()


def _clean_relative_path(value: Any, *, allow_root: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError("allowlist paths must be strings")
    path = value.strip().replace("\\", "/")
    if not path and allow_root:
        return "."
    if (not path or path.startswith("/") or re.match(r"^[A-Za-z]:", path) or
            "\x00" in path or any(part in {"", ".", ".."} for part in path.split("/"))):
        raise ValueError("allowlist contains an unsafe relative path")
    if path == ".git" or path.startswith(".git/"):
        raise ValueError("the Git metadata directory cannot be allowlisted")
    return path.rstrip("/")


def normalize_allowlist(paths: Sequence[str]) -> tuple[str, ...]:
    if isinstance(paths, (str, bytes)) or not isinstance(paths, Sequence):
        raise ValueError("allowed_paths must be a sequence of relative paths")
    cleaned = sorted({_clean_relative_path(path) for path in paths})
    if not cleaned:
        raise ValueError("write allowlist must contain at least one path")
    return tuple(cleaned)


def _allowed_path(path: str, allowlist: Sequence[str]) -> bool:
    return any(path == allowed or path.startswith(allowed + "/") for allowed in allowlist)


def _status_paths(root: Path) -> tuple[str, ...]:
    raw = _git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignored=matching")
    tokens = raw.split(b"\0")
    result: set[str] = set()
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if not token:
            continue
        if len(token) < 4 or token[2:3] != b" ":
            raise RuntimeError("git returned malformed worktree status")
        status = token[:2]
        path = os.fsdecode(token[3:]).rstrip("/")
        result.add(path.replace(os.sep, "/"))
        if b"R" in status or b"C" in status:
            if index >= len(tokens) or not tokens[index]:
                raise RuntimeError("git returned an incomplete rename status")
            result.add(os.fsdecode(tokens[index]).replace(os.sep, "/"))
            index += 1
    return tuple(sorted(result))


def _pid_token(pid: int) -> str:
    try:
        return f"pgid:{pid}" if os.getpgid(pid) == pid else ""
    except OSError:
        return ""


def _pid_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _same_process(pid: int, token: str, lock_path: Path) -> bool:
    if not token or token != f"pgid:{pid}" or not _pid_exists(pid):
        return False
    try:
        if os.getpgid(pid) != pid:
            return False
        fd = os.open(lock_path, os.O_RDWR)
    except OSError:
        return False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def _append_json(path: Path, value: Mapping[str, Any]) -> None:
    data = (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        try:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX)
        except ImportError:  # pragma: no cover - the runtime targets POSIX hosts
            pass
        view = memoryview(data)
        while view:
            count = os.write(fd, view)
            view = view[count:]
        os.fsync(fd)
    finally:
        os.close(fd)


def _atomic_json(path: Path, value: Mapping[str, Any]) -> None:
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    data = json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False).encode("utf-8")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(temporary, path)


_SUPERVISOR = r'''import fcntl, json, os, select, signal, subprocess, sys, time
session = sys.argv[1]
with open(os.path.join(session, "command.json"), "r", encoding="utf-8") as stream:
    config = json.load(stream)
lock_fd = os.open(config["lock"], os.O_RDWR)
fcntl.flock(lock_fd, fcntl.LOCK_EX)
signal.signal(signal.SIGTERM, lambda *_: None)
fifo_fd = os.open(config["fifo"], os.O_RDWR | os.O_NONBLOCK)
child = subprocess.Popen(config["command"], cwd=config["cwd"], stdin=fifo_fd,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        close_fds=True, env=os.environ.copy())
os.close(fifo_fd)
out_fd = os.open(config["output"], os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
total = 0
limit = config["output_limit"]
overflow = False
try:
    while True:
        if time.time() >= config["deadline_wall"]:
            try:
                os.killpg(os.getpgrp(), signal.SIGTERM)
                time.sleep(0.2)
                os.killpg(os.getpgrp(), signal.SIGKILL)
            except OSError:
                pass
            sys.exit(124)
        ready, _, _ = select.select([child.stdout], [], [], 0.1)
        if ready:
            chunk = os.read(child.stdout.fileno(), min(8192, limit - total + 1))
            if not chunk:
                break
            accepted = chunk[:max(0, limit - total)]
            if accepted:
                os.write(out_fd, accepted)
                os.fsync(out_fd)
                total += len(accepted)
            if len(accepted) != len(chunk):
                overflow = True
                try:
                    os.killpg(os.getpgrp(), signal.SIGTERM)
                    time.sleep(0.2)
                    os.killpg(os.getpgrp(), signal.SIGKILL)
                except OSError:
                    pass
                sys.exit(75)
        elif child.poll() is not None:
            break
    code = child.wait()
finally:
    try:
        child.stdout.close()
    except Exception:
        pass
    os.close(out_fd)
status = {"exit_code": int(code), "output_limit": bool(overflow)}
temporary = config["status"] + ".tmp"
with open(temporary, "w", encoding="utf-8") as stream:
    json.dump(status, stream, sort_keys=True, separators=(",", ":"))
    stream.flush()
    os.fsync(stream.fileno())
os.replace(temporary, config["status"])
sys.exit(75 if overflow else code)
'''


@dataclass(eq=False)
class RuntimeHandle:
    session_id: str
    task_id: str
    session_dir: Path
    worktree: Path
    pid: int
    pid_token: str
    process: subprocess.Popen[bytes] | None
    fifo_fd: int
    started_wall: float
    deadline_wall: float
    allowlist: tuple[str, ...]
    output_offset: int = 0
    line_buffer: bytes = b""
    replay_skip: int = 0
    pending: list[AgentEvent] = field(default_factory=list)
    held_terminal: list[AgentEvent] = field(default_factory=list)
    finalized: bool = False
    final_kind: str = ""
    final_message: str = ""
    replay_finished: bool = False
    recovered: bool = False
    stopped: bool = False
    lock: Any = field(default_factory=threading.RLock)


class AgentRuntime:
    """A bounded ``AgentAdapter`` backed by a real isolated child process.

    ``codex`` invokes the command assembled by :class:`CodexExecAdapter`, with
    its sandbox set to workspace write for the private worktree. The sandbox's
    default network policy remains in force; no network-enabling option is
    added. ``command:<exe>`` invokes the executable directly without a shell.
    """

    def __init__(
        self,
        repo: str | os.PathLike[str],
        allowed_paths: Sequence[str],
        *,
        backend: str = "codex",
        executable: str = "codex",
        state_dir: str | os.PathLike[str] | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        output_limit: int = DEFAULT_OUTPUT_LIMIT,
        diff_limit: int = DEFAULT_DIFF_LIMIT,
        poll_interval: float = 0.02,
        env: Mapping[str, str] | None = None,
    ):
        self.repo = _git_root(repo)
        self.allowed_paths = normalize_allowlist(allowed_paths)
        if backend not in {"codex", "command"}:
            raise ValueError("backend must be codex or command")
        self.backend = backend
        self.executable = executable
        self.timeout_seconds = _finite_positive(timeout_seconds, "timeout_seconds")
        for name, value in (("output_limit", output_limit), ("diff_limit", diff_limit)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        self.output_limit = output_limit
        self.diff_limit = diff_limit
        self.poll_interval = _finite_positive(poll_interval, "poll_interval")
        if not hasattr(os, "mkfifo") or os.name != "posix":
            raise RuntimeError("the agent runtime requires POSIX process groups and FIFOs")
        common_dir = _git_common_dir(self.repo)
        self.state_dir = Path(state_dir).expanduser().resolve() if state_dir is not None else common_dir / "verantyx-agent-runtime"
        self.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            self.state_dir.chmod(0o700)
        except OSError:
            pass
        self.sessions_dir = self.state_dir / "sessions"
        self.sessions_dir.mkdir(mode=0o700, exist_ok=True)
        self.log_path = self.state_dir / "runtime.jsonl"
        self.base_env = os.environ.copy()
        if env:
            for key, value in env.items():
                if not isinstance(key, str) or not isinstance(value, str) or "\x00" in key + value:
                    raise ValueError("runtime environment values must be text")
                self.base_env[key] = value
        self.base_env["GIT_TERMINAL_PROMPT"] = "0"
        self.base_env["GIT_OPTIONAL_LOCKS"] = "0"
        self._rows = self._load_log()
        self._seq = len(self._rows)
        self.handles: dict[str, RuntimeHandle] = {}

    def _load_log(self) -> list[dict[str, Any]]:
        if not self.log_path.exists():
            return []
        raw = self.log_path.read_bytes()
        if raw and not raw.endswith(b"\n"):
            raise RuntimeError("runtime log ends with an incomplete event")
        rows: list[dict[str, Any]] = []
        try:
            for line in raw.splitlines():
                row = json.loads(line)
                if (not isinstance(row, dict) or row.get("schema") != RUNTIME_SCHEMA or
                        type(row.get("seq")) is not int or row["seq"] != len(rows) or
                        not isinstance(row.get("type"), str) or
                        not isinstance(row.get("session_id"), str)):
                    raise RuntimeError("runtime log contains an invalid event")
                rows.append(row)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError) as exc:
            raise RuntimeError("runtime log contains malformed JSON") from exc
        return rows

    def _append(self, session_id: str, kind: str, **fields: Any) -> dict[str, Any]:
        row = {"schema": RUNTIME_SCHEMA, "seq": self._seq, "session_id": session_id,
               "type": kind, "time": time.time(), **fields}
        _append_json(self.log_path, row)
        self._rows.append(row)
        self._seq += 1
        return row

    def _command(self, worktree: Path, brief: str) -> list[str]:
        if self.backend == "codex":
            adapter = CodexExecAdapter(
                executable=self.executable,
                project_dir=worktree,
                timeout_seconds=self.timeout_seconds,
            )
            command = adapter.build_command(brief)
            sandbox_index = command.index("-s") + 1
            command[sandbox_index] = "workspace-write"
            return command
        executable = shlex.split(self.executable)
        if not executable:
            raise ValueError("command executable must not be empty")
        return [*executable, "--", brief]

    def start(self, brief: str) -> RuntimeHandle:
        if not isinstance(brief, str) or len(brief) > agent_adapter.MAX_BRIEF_CHARS:
            raise ValueError("brief must be bounded text")
        match = _TASK_LINE.search(brief)
        task_id = match.group(1).strip() if match else "agent-task"
        if not task_id:
            task_id = "agent-task"
        session_id = uuid.uuid4().hex
        session_dir = self.sessions_dir / session_id
        session_dir.mkdir(mode=0o700)
        worktree = session_dir / "worktree"
        self._append(session_id, "SESSION_CREATED", task_id=task_id,
                     repo=os.fspath(self.repo), allowlist=list(self.allowed_paths),
                     base_commit=os.fsdecode(_git(self.repo, "rev-parse", "HEAD")).strip())
        process: subprocess.Popen[bytes] | None = None
        fifo_fd = -1
        try:
            _git(self.repo, "worktree", "add", "--detach", os.fspath(worktree),
                 os.fsdecode(_git(self.repo, "rev-parse", "HEAD")).strip(), timeout=60)
            self._append(session_id, "WORKTREE_CREATED", worktree=os.fspath(worktree))
            prompt = (
                brief + "\n\nRuntime event protocol: write newline-delimited JSON events only. "
                "Use QUESTION {type,id,text,options?}, CLAIM {type,task,evidence}, "
                "DONE {type}, ERROR {type,message?}, or OTHER {type,text}. "
                "Do not include prose outside those events."
            )
            command = self._command(worktree, prompt)
            fifo = session_dir / "agent.stdin"
            lock_path = session_dir / "agent.lock"
            output = session_dir / "agent.output"
            status_path = session_dir / "agent.status.json"
            os.mkfifo(fifo, 0o600)
            lock_path.touch(mode=0o600)
            fifo_fd = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
            started_wall = time.time()
            deadline_wall = started_wall + self.timeout_seconds
            config = {"command": command, "cwd": os.fspath(worktree), "fifo": os.fspath(fifo),
                      "lock": os.fspath(lock_path),
                      "output": os.fspath(output), "status": os.fspath(status_path),
                      "output_limit": self.output_limit, "deadline_wall": deadline_wall}
            _atomic_json(session_dir / "command.json", config)
            process = subprocess.Popen(
                [sys.executable, "-c", _SUPERVISOR, os.fspath(session_dir)],
                cwd=os.fspath(worktree), env=self.base_env,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                close_fds=True, start_new_session=True,
            )
            token = _pid_token(process.pid)
            identity_deadline = time.monotonic() + 2.0
            while token and not _same_process(process.pid, token, lock_path):
                if status_path.exists() or process.poll() is not None:
                    break
                if time.monotonic() >= identity_deadline:
                    raise RuntimeError("agent supervisor did not establish its pid identity")
                time.sleep(0.01)
            pid_row = {"schema": RUNTIME_SCHEMA, "session_id": session_id,
                       "pid": process.pid, "pgid": process.pid, "pid_token": token,
                       "task_id": task_id, "repo": os.fspath(self.repo),
                       "worktree": os.fspath(worktree), "started_wall": started_wall,
                       "deadline_wall": deadline_wall,
                       "allowlist": list(self.allowed_paths)}
            _atomic_json(session_dir / "agent.pid.json", pid_row)
            self._append(session_id, "PROCESS_STARTED", pid=process.pid, pgid=process.pid,
                         pid_token=token, started_wall=started_wall,
                         deadline_wall=deadline_wall, command_sha256=__import__("hashlib").sha256(
                             json.dumps(command, ensure_ascii=False).encode("utf-8")).hexdigest())
            handle = RuntimeHandle(session_id, task_id, session_dir, worktree, process.pid,
                                   token, process, fifo_fd, started_wall, deadline_wall,
                                   self.allowed_paths)
            self.handles[session_id] = handle
            return handle
        except Exception as exc:
            if process is not None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            if fifo_fd >= 0:
                try:
                    os.close(fifo_fd)
                except OSError:
                    pass
            try:
                self._remove_worktree(worktree)
            except Exception:
                pass
            self._append(session_id, "SESSION_START_FAILED", reason=type(exc).__name__)
            raise

    def _process_running(self, handle: RuntimeHandle) -> bool:
        if handle.process is not None:
            return handle.process.poll() is None
        if self._status(handle) is not None:
            return False
        return _same_process(handle.pid, handle.pid_token, handle.session_dir / "agent.lock")

    def _status(self, handle: RuntimeHandle) -> dict[str, Any] | None:
        path = handle.session_dir / "agent.status.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(value, dict) or type(value.get("exit_code")) is not int:
            return None
        return value

    def _terminate_group(self, handle: RuntimeHandle) -> None:
        try:
            os.killpg(handle.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except OSError:
            pass
        deadline = time.monotonic() + 0.25
        while time.monotonic() < deadline and self._process_running(handle):
            time.sleep(0.01)
        try:
            os.killpg(handle.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError:
            pass
        if handle.process is not None:
            try:
                handle.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass

    def _kill_remaining_group(self, handle: RuntimeHandle) -> None:
        """Reap descendants that outlived a normally exited supervisor."""
        try:
            os.killpg(handle.pid, signal.SIGTERM)
        except (ProcessLookupError, OSError):
            return
        time.sleep(0.05)
        try:
            os.killpg(handle.pid, signal.SIGKILL)
        except (ProcessLookupError, OSError):
            pass

    def _read_output(self, handle: RuntimeHandle) -> None:
        output = handle.session_dir / "agent.output"
        try:
            with output.open("rb") as stream:
                stream.seek(handle.output_offset)
                data = stream.read(self.output_limit + 1 - handle.output_offset)
        except FileNotFoundError:
            data = b""
        if data:
            handle.output_offset += len(data)
            handle.line_buffer += data
            while b"\n" in handle.line_buffer:
                line, handle.line_buffer = handle.line_buffer.split(b"\n", 1)
                self._parse_output_line(handle, line + b"\n")
        if handle.output_offset > self.output_limit:
            self._fail(handle, "agent output exceeded the size limit", "SESSION_OUTPUT_LIMIT")

    def _parse_output_line(self, handle: RuntimeHandle, line: bytes) -> None:
        if handle.stopped:
            return
        events = agent_adapter.parse_agent_output(line, max_output_chars=max(1, len(line)))
        for event in events:
            if event.get("type") == "DONE" or handle.held_terminal:
                handle.held_terminal.append(event)
            else:
                self._emit(handle, event)

    def _emit(self, handle: RuntimeHandle, event: AgentEvent) -> None:
        if handle.replay_skip:
            handle.replay_skip -= 1
            return
        handle.pending.append(event)

    def _finish_output(self, handle: RuntimeHandle) -> None:
        if handle.line_buffer:
            self._parse_output_line(handle, handle.line_buffer)
            handle.line_buffer = b""

    def _changed_paths(self, handle: RuntimeHandle) -> tuple[str, ...]:
        changed = _status_paths(handle.worktree)
        unsafe = []
        for path in changed:
            try:
                clean = _clean_relative_path(path)
            except ValueError:
                unsafe.append(path)
                continue
            full = handle.worktree / clean
            try:
                if full.is_symlink():
                    unsafe.append(path + " (symlink)")
                    continue
            except OSError:
                unsafe.append(path)
                continue
            if not _allowed_path(clean, handle.allowlist):
                unsafe.append(path)
        if unsafe:
            raise PermissionError("write allowlist violation: " + ", ".join(unsafe[:16]))
        return changed

    def _remove_worktree(self, path: Path) -> None:
        if not path.exists():
            return
        try:
            _git(self.repo, "worktree", "remove", "--force", os.fspath(path), timeout=30)
        except Exception:
            shutil.rmtree(path, ignore_errors=True)
            try:
                _git(self.repo, "worktree", "prune", timeout=30)
            except Exception:
                pass

    def _save_artifact(self, handle: RuntimeHandle, changed: Sequence[str]) -> str:
        patch = handle.session_dir / "artifact.patch"
        if not changed:
            patch.write_bytes(b"")
            return __import__("hashlib").sha256(b"").hexdigest()
        _git(handle.worktree, "add", "--all", "--", ".", timeout=30)
        with patch.open("wb") as stream:
            subprocess.run(
                ["git", "-C", os.fspath(handle.worktree), "diff", "--cached", "--binary",
                 "--no-ext-diff", "HEAD"],
                stdout=stream, stderr=subprocess.PIPE, check=True, timeout=30,
                env={**self.base_env, "GIT_TERMINAL_PROMPT": "0"},
            )
            stream.flush()
            os.fsync(stream.fileno())
        if patch.stat().st_size > self.diff_limit:
            raise OverflowError("approved diff exceeded the artifact size limit")
        return __import__("hashlib").sha256(patch.read_bytes()).hexdigest()

    def _close_fifo(self, handle: RuntimeHandle) -> None:
        if handle.fifo_fd >= 0:
            try:
                os.close(handle.fifo_fd)
            except OSError:
                pass
            handle.fifo_fd = -1

    def _record_terminal(self, handle: RuntimeHandle, kind: str, message: str = "",
                         **fields: Any) -> None:
        handle.finalized = True
        handle.final_kind = kind
        handle.final_message = message[:512]
        self._append(handle.session_id, kind, message=handle.final_message, **fields)
        self._close_fifo(handle)

    def _fail(self, handle: RuntimeHandle, reason: str, kind: str = "SESSION_FAILED") -> None:
        if handle.finalized:
            return
        self._terminate_group(handle)
        self._record_terminal(handle, kind, reason)
        self._remove_worktree(handle.worktree)
        handle.held_terminal.clear()
        self._finish_buffer_as_error(handle, reason)

    def _finish_buffer_as_error(self, handle: RuntimeHandle, reason: str) -> None:
        handle.held_terminal.clear()
        if not handle.replay_finished:
            self._emit(handle, {"type": "ERROR", "message": reason[:512]})
            handle.replay_finished = True

    def _finalize_process(self, handle: RuntimeHandle) -> None:
        if handle.finalized:
            return
        self._finish_output(handle)
        status = self._status(handle)
        if status is None:
            if handle.process is not None:
                try:
                    code = handle.process.wait(timeout=0)
                except subprocess.TimeoutExpired:
                    return
            else:
                code = -1
            status = {"exit_code": code, "output_limit": False}
        if status.get("output_limit") or handle.output_offset >= self.output_limit:
            self._kill_remaining_group(handle)
            reason = "agent output exceeded the size limit"
            self._record_terminal(handle, "SESSION_OUTPUT_LIMIT", reason,
                                  exit_code=status["exit_code"])
            self._remove_worktree(handle.worktree)
            self._finish_buffer_as_error(handle, reason)
            return
        if status["exit_code"] != 0:
            self._kill_remaining_group(handle)
            reason = f"agent process exited with status {status['exit_code']}"
            self._record_terminal(handle, "SESSION_PROCESS_FAILED", reason,
                                  exit_code=status["exit_code"])
            self._remove_worktree(handle.worktree)
            self._finish_buffer_as_error(handle, reason)
            return
        try:
            changed = self._changed_paths(handle)
            digest = self._save_artifact(handle, changed)
        except PermissionError as exc:
            reason = str(exc)[:512]
            self._kill_remaining_group(handle)
            self._record_terminal(handle, "SESSION_REJECTED", reason)
            self._remove_worktree(handle.worktree)
            self._finish_buffer_as_error(handle, reason)
            return
        except (OverflowError, OSError, subprocess.SubprocessError, RuntimeError) as exc:
            reason = f"worktree diff check failed: {type(exc).__name__}"
            self._kill_remaining_group(handle)
            try:
                (handle.session_dir / "artifact.patch").unlink()
            except OSError:
                pass
            self._record_terminal(handle, "SESSION_REJECTED", reason)
            self._remove_worktree(handle.worktree)
            self._finish_buffer_as_error(handle, reason)
            return
        self._kill_remaining_group(handle)
        self._record_terminal(handle, "SESSION_ACCEPTED", artifact_sha256=digest,
                              artifact_path=os.fspath(handle.session_dir / "artifact.patch"),
                              changed_paths=list(changed), exit_code=status["exit_code"])
        self._remove_worktree(handle.worktree)
        handle.pending.extend(self._take_held(handle))
        handle.replay_finished = True

    def _take_held(self, handle: RuntimeHandle) -> list[AgentEvent]:
        held = handle.held_terminal
        handle.held_terminal = []
        events: list[AgentEvent] = []
        for event in held:
            if handle.replay_skip:
                handle.replay_skip -= 1
            else:
                events.append(event)
        return events

    def _replay_terminal(self, handle: RuntimeHandle, row: Mapping[str, Any]) -> None:
        if handle.replay_finished:
            return
        kind = str(row.get("type", ""))
        if kind == "SESSION_ACCEPTED":
            handle.pending.extend(self._take_held(handle))
        else:
            handle.held_terminal.clear()
            message = str(row.get("message", "agent runtime ended without a trusted result"))
            self._emit(handle, {"type": "ERROR", "message": message[:512]})
        handle.replay_finished = True

    def _last_session_rows(self) -> dict[str, list[dict[str, Any]]]:
        by_session: dict[str, list[dict[str, Any]]] = {}
        for row in self._rows:
            by_session.setdefault(row["session_id"], []).append(row)
        return by_session

    def recover(self, run_id: str, task_id: str, cursor: int) -> RuntimeHandle:
        if not isinstance(run_id, str) or not run_id or not isinstance(task_id, str) or not task_id:
            raise ValueError("recovery needs a run id and task id")
        if isinstance(cursor, bool) or not isinstance(cursor, int) or cursor < 0:
            raise ValueError("recovery cursor must be a nonnegative integer")
        # Refresh the append-only journal after a previous driver process.
        self._rows = self._load_log()
        self._seq = len(self._rows)
        candidates: list[tuple[int, list[dict[str, Any]]]] = []
        for rows in self._last_session_rows().values():
            created = next((row for row in rows if row.get("type") == "SESSION_CREATED"), None)
            was_stopped = any(row.get("type") == "ADAPTER_STOPPED" for row in rows)
            if (created and not was_stopped and created.get("task_id") == task_id and
                    created.get("repo") == os.fspath(self.repo)):
                candidates.append((rows[-1]["seq"], rows))
        candidates.sort(key=lambda item: item[0], reverse=True)
        if not candidates:
            raise RuntimeError("no durable agent session matches the interrupted task")
        _, rows = candidates[0]
        created = next(row for row in rows if row.get("type") == "SESSION_CREATED")
        started = next((row for row in rows if row.get("type") == "PROCESS_STARTED"), None)
        if started is None:
            raise RuntimeError("agent session has no durable process identity")
        terminal = next((row for row in reversed(rows)
                         if row.get("type") in _TERMINAL_EVENTS), None)
        session_id = str(created["session_id"])
        session_dir = self.sessions_dir / session_id
        try:
            pid_file = json.loads((session_dir / "agent.pid.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError("agent pid file cannot be replayed") from exc
        if (pid_file.get("schema") != RUNTIME_SCHEMA or pid_file.get("session_id") != session_id or
                pid_file.get("repo") != os.fspath(self.repo) or pid_file.get("task_id") != task_id or
                pid_file.get("allowlist") != list(self.allowed_paths)):
            raise RuntimeError("agent pid file does not match this runtime")
        worktree = Path(str(pid_file.get("worktree", "")))
        if terminal is None:
            pid = pid_file.get("pid")
            token = pid_file.get("pid_token")
            status_path = session_dir / "agent.status.json"
            status_ready = False
            try:
                status_value = json.loads(status_path.read_text(encoding="utf-8"))
                status_ready = isinstance(status_value, dict) and type(status_value.get("exit_code")) is int
            except (OSError, json.JSONDecodeError):
                pass
            if (type(pid) is not int or not isinstance(token, str) or
                    (not status_ready and not _same_process(pid, token, session_dir / "agent.lock"))):
                if not status_ready and time.time() >= float(pid_file.get("deadline_wall", 0)):
                    self._append(session_id, "SESSION_TIMED_OUT",
                                 message="agent process exceeded its hard timeout")
                    self._remove_worktree(worktree)
                    raise RuntimeError("the saved agent exceeded its hard timeout")
                self._append(session_id, "SESSION_INTERRUPTED",
                             message="the saved agent process identity is no longer live")
                self._remove_worktree(worktree)
                raise RuntimeError("the saved agent process is no longer running")
        else:
            pid = int(pid_file["pid"])
            token = str(pid_file.get("pid_token", ""))
        fifo = session_dir / "agent.stdin"
        try:
            fifo_fd = os.open(fifo, os.O_RDWR | os.O_NONBLOCK)
        except OSError:
            fifo_fd = -1
        handle = RuntimeHandle(
            session_id=session_id, task_id=task_id, session_dir=session_dir,
            worktree=worktree, pid=pid, pid_token=token, process=None, fifo_fd=fifo_fd,
            started_wall=float(pid_file["started_wall"]), deadline_wall=float(pid_file["deadline_wall"]),
            allowlist=self.allowed_paths, replay_skip=cursor, recovered=True,
            finalized=terminal is not None,
            final_kind=str(terminal.get("type", "")) if terminal else "",
            final_message=str(terminal.get("message", "")) if terminal else "",
        )
        self._append(session_id, "SESSION_ADOPTED", driver_run_id=run_id, cursor=cursor,
                     pid=pid, pid_token=token)
        if terminal is not None:
            # Rebuild the event stream from the durable capped output log.
            handle.output_offset = 0
            self._read_output(handle)
            self._finish_output(handle)
            self._replay_terminal(handle, terminal)
        self.handles[session_id] = handle
        return handle

    def poll(self, handle: RuntimeHandle) -> list[AgentEvent]:
        if not isinstance(handle, RuntimeHandle) or handle.session_id not in self.handles and not handle.recovered:
            raise TypeError("handle was not created by this runtime")
        with handle.lock:
            if handle.pending:
                result = handle.pending[:]
                handle.pending.clear()
                return result
            if handle.finalized:
                return []
            if time.time() >= handle.deadline_wall:
                self._fail(handle, "agent execution timed out", "SESSION_TIMED_OUT")
            elif (handle.session_dir / "agent.output").exists() and (handle.session_dir / "agent.output").stat().st_size > self.output_limit:
                self._fail(handle, "agent output exceeded the size limit", "SESSION_OUTPUT_LIMIT")
            else:
                self._read_output(handle)
                if not handle.finalized and not self._process_running(handle):
                    self._finalize_process(handle)
                elif not handle.finalized and handle.process is not None and handle.process.poll() is not None:
                    self._finalize_process(handle)
            if handle.pending:
                result = handle.pending[:]
                handle.pending.clear()
                return result
            if not handle.finalized:
                time.sleep(min(self.poll_interval, max(0.001, handle.deadline_wall - time.time())))
                self._read_output(handle)
                if not self._process_running(handle):
                    self._finalize_process(handle)
            if handle.pending:
                result = handle.pending[:]
                handle.pending.clear()
                return result
            return []

    def send(self, handle: RuntimeHandle, text: str) -> None:
        if not isinstance(handle, RuntimeHandle):
            raise TypeError("handle was not created by this runtime")
        if not isinstance(text, str) or len(text) > agent_adapter.MAX_LINE_CHARS:
            raise ValueError("message must be bounded text")
        with handle.lock:
            if handle.finalized or handle.fifo_fd < 0:
                return
            try:
                data = (text + "\n").encode("utf-8")
                os.write(handle.fifo_fd, data)
            except (BrokenPipeError, BlockingIOError, OSError):
                # Replies are best effort; they never alter the accepted frame.
                return

    def stop(self, handle: RuntimeHandle) -> None:
        if not isinstance(handle, RuntimeHandle):
            raise TypeError("handle was not created by this runtime")
        with handle.lock:
            if handle.stopped:
                return
            handle.stopped = True
            if not handle.finalized:
                self._terminate_group(handle)
                self._record_terminal(handle, "SESSION_CANCELLED",
                                      "agent process was stopped before validation")
                self._remove_worktree(handle.worktree)
                handle.pending.clear()
                handle.held_terminal.clear()
            else:
                self._close_fifo(handle)
            self._append(handle.session_id, "ADAPTER_STOPPED", recovered=handle.recovered)

    def session_rows(self) -> list[dict[str, Any]]:
        """Return a copy of the validated journal rows for an operator or demo."""
        return [dict(row) for row in self._rows]


AgentRuntimeAdapter = AgentRuntime

__all__ = ["AgentRuntime", "AgentRuntimeAdapter", "RuntimeHandle", "RuntimeError",
           "normalize_allowlist"]
