"""Shared helpers for the W2-a conduct-run tests (no tests of its own).

Real agents are never started: every test passes ``--codex-bin`` / ``--claude-bin`` pointing at a
shell script it wrote.  The guards of test_conduct_entry_support (verantyx comes from this tree; a
trap codex / claude on PATH that must never be started) apply through the star import.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from test_conduct_entry_support import *  # noqa: F401,F403
from test_conduct_entry_support import ROOT, read_ledger

PYTHON = sys.executable
GOOD_GREET = 'print("Hello, Vera!")'
BAD_GREET = 'print("Hello, Vera")'
# Slot text cannot hold ! or ? (the typed writer refuses them); the witness JSON can.
CHECK_CODE = ("import subprocess, sys; "
              "r = subprocess.run([sys.executable, 'greet.py', 'Vera'], capture_output=True, text=True); "
              "print(repr(r.stdout)); sys.exit(0 if r.stdout == 'Hello, Vera!\\n' else 1)")
C1_ARGV = [PYTHON, "greet.py", "Vera"]
C2_ARGV = [PYTHON, "-c", CHECK_CODE]
WRITE_GOOD = f"printf '%s\\n' '{GOOD_GREET}' > greet.py\n"
WRITE_BAD = f"printf '%s\\n' '{BAD_GREET}' > greet.py\n"


def witness(argv, expected=0):
    return {"kind": "command_exit", "command": argv, "expected_exit": expected}


def default_criteria():
    return [("Running greet.py with Vera exits with status zero", witness(C1_ARGV)),
            ("Running greet.py with Vera prints exactly the greeting line", witness(C2_ARGV))]


def frame_text(criteria=None, *, human=(), allowlist=("greet.py",), settings=("codex_model: gpt-6-luna",
                                                                               "codex_effort: low")):
    """A Markdown frame for the task ``Greeter``; ``criteria`` is [(text, witness dict | 'human-judged')]."""
    rows = []
    for number, (text, wit) in enumerate(list(criteria if criteria is not None else default_criteria()), 1):
        rows.append(f"C{number}: {text} | " + (wit if isinstance(wit, str) else json.dumps(wit)))
    base = len(rows)
    for number, text in enumerate(human, base + 1):
        rows.append(f"C{number}: {text} | human-judged")
    lines = ["[goal]", "project: Greeter", "statement: Create greet.py that prints a greeting",
             "[philosophy_invariants]", "I1: Keep the program in one small file",
             "[completion_criteria]", *rows,
             "[phases]", "P1: Write greet.py", "[phase_order]", "none: none",
             "[decisions]", "D1: goal authority => The human decides",
             "[vocabulary_aliases]", "none: none", "[escalation_conditions]", "none: none",
             "[protected_actions]", "none: none"]
    if allowlist is not None:
        lines += ["[write_allowlist]", *[f"W{n}: {p}" for n, p in enumerate(allowlist, 1)]]
    if settings:
        lines += ["[agent_settings]", *settings]
    return "\n".join(lines) + "\n"


def write_script(path: Path, body: str) -> Path:
    path.write_text("#!/bin/sh\ncat > /dev/null\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return path


def dead(pid: int, wait: float = 3.0) -> bool:
    """True when ``pid`` no longer runs (a zombie waiting to be reaped counts as dead)."""
    end = time.monotonic() + wait
    while True:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        stat = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True).stdout.strip()
        if stat == "" or stat.startswith("Z"):
            return True
        if time.monotonic() >= end:
            return False
        time.sleep(0.05)


def git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    return done.returncode, done.stdout


def repo_snapshot(repo: Path) -> dict[str, Any]:
    """Everything about the original repository the conductor must leave alone."""
    files = sorted(str(p.relative_to(repo)) for p in repo.rglob("*")
                   if p.is_file() and ".git" not in p.relative_to(repo).parts)
    return {"refs": git(repo, "for-each-ref", "--format=%(refname) %(objectname)"),
            "head": git(repo, "rev-parse", "HEAD"), "symbolic": git(repo, "symbolic-ref", "-q", "HEAD"),
            "status": git(repo, "status", "--porcelain=v1", "--untracked-files=all", "--ignored"),
            "files": files, "log_refs": git(repo, "rev-list", "--branches", "--tags", "--remotes"),
            "log_all": git(repo, "log", "--all", "--oneline")}   # --all also lists linked worktree HEADs


@dataclass
class Run:
    outcome: Any
    out: dict
    rows: list
    repo: Path
    state: Path
    pids: Path
    before: dict = field(default_factory=dict)
    after: dict = field(default_factory=dict)

    def of(self, kind):
        return [r for r in self.rows if r["type"] == kind]

    def one(self, kind):
        found = self.of(kind)
        assert len(found) == 1, (kind, [r["type"] for r in self.rows])
        return found[0]

    @property
    def types(self):
        return [r["type"] for r in self.rows]

    def runtime_rows(self):
        path = self.state / "runs" / self.out["run_id"] / "runtime" / "runtime.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def supervisor_pids(self):
        base = self.state / "runs" / self.out["run_id"] / "runtime" / "sessions"
        return [json.loads(p.read_text())["pid"] for p in base.glob("*/agent.pid.json")]

    def recorded_pids(self):
        return [int(p.read_text().strip()) for p in sorted(self.pids.glob("*")) if p.read_text().strip()]


def execute(base: Path, body: str, *, frame: str | None = None, adapter: str = "codex", **kwargs) -> Run:
    """Run ``conduct_entry`` with a scripted agent in a fresh repo; the script may use $PIDS."""
    from verantyx.conductor_run import conduct_entry

    base.mkdir(parents=True, exist_ok=True)
    repo, state, pids = base / "repo", base / "state", base / "pids"
    pids.mkdir()
    repo.mkdir()
    for args in (["init", "-q"], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "init"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    script = write_script(base / "agent.sh", body.replace("$PIDS", str(pids)))
    frame_path = base / "frame.md"
    frame_path.write_text(frame if frame is not None else frame_text(), encoding="utf-8")
    kwargs.setdefault("codex_bin" if adapter == "codex" else "claude_bin", str(script))
    kwargs.setdefault("state_dir", state)
    kwargs.setdefault("poll_interval", 0.02)   # the design default is 0.2 s; tests shorten only the wait
    before = repo_snapshot(repo)
    outcome = conduct_entry(frame_path, repo, adapter, **kwargs)
    after = repo_snapshot(repo)
    out = outcome.as_dict()
    rows = [r for r in read_ledger(out["ledger"]) if r["run_id"] == out["run_id"]] if out["ledger"] else []
    if out["ledger"]:
        state = Path(out["ledger"]).parent
    return Run(outcome, out, rows, repo, state, pids, before, after)


def assert_nothing_left(run: Run) -> None:
    """No supervisor, agent or grandchild survives, and the ledger says the group is gone."""
    check = run.one("AGENT_PROCESS_CHECK")
    assert check["group_alive"] is False and check["group_alive_after_retry"] is None
    leftovers = [pid for pid in run.supervisor_pids() + run.recorded_pids() if not dead(pid)]
    assert leftovers == []


# ---- scripted runs that only wait are started together, once, for every module that registered some
_SPECS: dict = {}
_RESULTS: dict = {}


def spec(body: str, frame: str | None = None, **kwargs):
    """A deferred ``execute`` (run later, in a thread, in its own directory)."""
    return lambda base: execute(base, body, frame=frame, **kwargs)


def register(prefix: str, specs: dict) -> None:
    for name, fn in specs.items():
        _SPECS[f"{prefix}:{name}"] = fn


def _start_all(tmp_path_factory) -> None:
    if _RESULTS:
        return
    from concurrent.futures import ThreadPoolExecutor

    bases = {key: tmp_path_factory.mktemp(key.replace(":", "-")[:24]) for key in _SPECS}
    with ThreadPoolExecutor(max_workers=min(8, max(1, len(_SPECS)))) as pool:   # the longest (5 s) run is registered first
        futures = {key: pool.submit(fn, bases[key]) for key, fn in _SPECS.items()}
    for key, future in futures.items():
        _RESULTS[key] = future.exception() or future.result()


class Pool:
    def __init__(self, prefix: str):
        self.prefix = prefix

    def __getitem__(self, name: str) -> Run:
        value = _RESULTS[f"{self.prefix}:{name}"]
        if isinstance(value, BaseException):
            raise value
        return value


def pool_fixture(prefix: str):
    @pytest.fixture(scope="module")
    def runs(tmp_path_factory):
        _start_all(tmp_path_factory)
        return Pool(prefix)
    return runs
