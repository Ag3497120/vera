"""Shared helpers for the W2-b conduct-verification tests (no tests of its own).

Real agents are never started.  The implementer and the verifier are shell scripts the test writes;
the verifier script reads the prompt (it needs the nonce, so it does not use W2-a's ``write_script``,
which throws the prompt away).  The guards of test_conduct_entry_support apply through the star import.
"""
from __future__ import annotations

import atexit
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from test_conduct_entry_support import *  # noqa: F401,F403
from test_conduct_entry_support import ROOT, read_ledger
from test_conduct_run_support import (Run, dead, execute, git, pool_fixture, register,  # noqa: F401
                                      repo_snapshot, write_script)

PY = sys.executable
SUM_C1_CODE = ("import subprocess, sys; "
               "r = subprocess.run([sys.executable, 'sum_args.py', '1', '2', '3'], capture_output=True, text=True); "
               "print(repr(r.stdout)); sys.exit(0 if r.stdout.strip() == '6' else 1)")
SUM_C2_CODE = ("import subprocess, sys; "
               "r = subprocess.run([sys.executable, 'sum_args.py'], capture_output=True, text=True); "
               "print(repr(r.stdout)); sys.exit(0 if r.stdout.strip() == '0' else 1)")
C1_ARGV = [PY, "-c", SUM_C1_CODE]
C2_ARGV = [PY, "-c", SUM_C2_CODE]
HONEST = "printf '%s\\n' 'import sys' 'print(sum(int(a) for a in sys.argv[1:]))' > sum_args.py\n"
HARDCODED = "printf '%s\\n' 'print(6)' > sum_args.py\n"
VERIFIER_SETTINGS = ("verifier_adapter: claude", "verifier_model: claude-sonnet-5-5", "verifier_effort: low")
IMPLEMENTER_SETTINGS = ("codex_model: gpt-6-luna", "codex_effort: low")
# The same settings given as arguments instead of frame rows: every row of [agent_settings] is a record that the
# implementer's brief asks the memory about (Python work that the pooled runs cannot do in parallel), so only the runs
# that test the frame's own settings carry them in the frame.
IMPL_ARGS = {"model": "gpt-6-luna", "effort": "low"}
VERIFIER_ARGS = {"verifier_adapter": "claude", "verifier_model": "claude-sonnet-5-5", "verifier_effort": "low"}
LIMIT_CLAUDE = "You've hit your session limit"

CHECK_4_5 = {"argv": [PY, "sum_args.py", "4", "5"], "expect_exit": 0, "expect_stdout": "9"}
CHECK_NO_ARGS = {"argv": [PY, "sum_args.py"], "expect_exit": 0, "expect_stdout": "0"}


def sum_frame(*, two: bool = True, human: tuple[str, ...] = (), settings=(*IMPLEMENTER_SETTINGS, *VERIFIER_SETTINGS),
              allowlist=("sum_args.py",), quick: bool = False) -> str:
    """A Markdown frame for task SumArgs.  ``two``: both acceptance commands; otherwise only C1 (the
    one a hard-coded ``print(6)`` also passes).  ``quick``: the one acceptance command is only "the file is not
    empty" (one cheap program under the sandbox instead of two Python processes), for the runs whose test is about
    what happens after the acceptance and never about the acceptance itself."""
    rows = ["C1: The command python sum_args.py 1 2 3 prints 6 | " +
            json.dumps({"kind": "command_exit", "command": C1_ARGV, "expected_exit": 0})]
    if quick:
        rows = ["C1: The file sum_args.py is not empty | " +
                json.dumps({"kind": "command_exit", "command": ["/bin/test", "-s", "sum_args.py"], "expected_exit": 0})]
        two = False
    if two:
        rows.append("C2: The command python sum_args.py with no arguments prints 0 | " +
                    json.dumps({"kind": "command_exit", "command": C2_ARGV, "expected_exit": 0}))
    for number, text in enumerate(human, len(rows) + 1):
        rows.append(f"C{number}: {text} | human-judged")
    lines = ["[goal]", "project: SumArgs",
             "statement: Create sum_args.py that prints the sum of its integer arguments and 0 for none",
             "[philosophy_invariants]", "I1: Keep the program in one small file named sum_args.py",
             "[completion_criteria]", *rows, "[phases]", "P1: Write sum_args.py", "[phase_order]", "none: none",
             "[decisions]", "D1: goal authority => The human decides", "[vocabulary_aliases]", "none: none",
             "[escalation_conditions]", "none: none", "[protected_actions]", "none: none"]
    if allowlist is not None:
        lines += ["[write_allowlist]", *[f"W{n}: {p}" for n, p in enumerate(allowlist, 1)]]
    if settings:
        lines += ["[agent_settings]", *settings]
    return "\n".join(lines) + "\n"


BARE = sum_frame(settings=())                  # both acceptance commands, no [agent_settings]
BARE_ONE = sum_frame(two=False, settings=())    # only C1 (a hard-coded print(6) passes it too)
QUICK = sum_frame(settings=(), quick=True)
BY_ARGS = {"frame": BARE, **IMPL_ARGS, **VERIFIER_ARGS}
QUICK_ARGS = {"frame": QUICK, **IMPL_ARGS, **VERIFIER_ARGS}
BY_ARGS_ONE = {"frame": BARE_ONE, **IMPL_ARGS, **VERIFIER_ARGS}


# ---------------------------------------------------------------- verdicts and verifier scripts
def verdict(result: str, *, checks=(), findings=(), reason: str = "") -> dict[str, Any]:
    value: dict[str, Any] = {"result": result, "checks": list(checks), "findings": list(findings)}
    if reason:
        value["reason"] = reason
    return value


def finding(perspective: str, claim: str, check: dict | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {"perspective": perspective, "claim": claim}
    if check is not None:
        value["check"] = check
    return value


PASS_GOOD = verdict("PASS", checks=[CHECK_4_5, CHECK_NO_ARGS])
FAIL_HARDCODED = verdict("FAIL", findings=[finding("HARDCODED_ACCEPTANCE", "sum_args.py prints a constant", CHECK_4_5)],
                         reason="the program ignores its arguments")


def _verdict_file(path: Path, value: dict, index: int) -> str:
    """Write the verdict JSON to a file next to the script; the script reads it (no shell quoting of the JSON)."""
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    assert "\n" not in text
    target = path.with_name(f"{path.stem}-verdict-{index}.json")
    target.write_text(text, encoding="utf-8")
    assert "'" not in str(target)
    return f"$(cat '{target}')"


_NONCE_LINES = (
    "prompt=$(cat)\n"
    "nonce=$(printf '%s\\n' \"$prompt\" | sed -n 's/^Verdict nonce: \\([0-9a-f]\\{32\\}\\)$/\\1/p' | head -1)\n")
_FIND_OUT = 'while [ $# -gt 0 ]; do [ "$1" = "-o" ] && out=$2; shift; done\n'


def verifier_script(path: Path, *, rules=(), default: dict | None = None, flavour: str = "claude",
                    first: str = "", pre: str = "", post: str = "", raw: str | None = None) -> Path:
    """A fake verifier.  ``rules``: [(needle found in the prompt, verdict dict)], first match wins.

    ``flavour``: ``claude`` answers on standard output; ``codex`` writes the answer to the file after ``-o``.
    ``raw`` is a shell fragment that replaces the answer (``$nonce`` is available).
    ``first`` runs before anything else (before the prompt is read): a script that records its pid there is
    recorded even when a loaded machine makes the process start slowly (``pre`` runs after the nonce lines).
    """
    body = "#!/bin/sh\n" + first + (_FIND_OUT if flavour == "codex" else "") + _NONCE_LINES + pre
    if raw is not None:
        answer = raw
    else:
        branches = []
        for index, (needle, value) in enumerate(rules):
            assert "'" not in needle
            branches.append(f"if printf '%s' \"$prompt\" | grep -qF '{needle}'; then answer=\"{_verdict_file(path, value, index)}\"; el")
        fallback = f'answer="{_verdict_file(path, default or PASS_GOOD, 99)}"'
        chain = ("".join(branches) + "se " + fallback + "; fi\n") if branches else fallback + "\n"
        sink = ('printf \'some prose\\nVERA_VERDICT %s %s\\n\' "$nonce" "$answer"\n' if flavour == "claude" else
                'printf \'some prose\\nVERA_VERDICT %s %s\\n\' "$nonce" "$answer" > "$out"\n')
        answer = chain + sink
    path.write_text(body + answer + post, encoding="utf-8")
    path.chmod(0o755)
    return path


# ---------------------------------------------------------------- a cheaper way to start a scripted run
# Every spawned process counts when the whole suite runs (the pool below shares the machine with W2-a's runs), so
# these runs copy one prepared repository instead of running ``git init`` and ``git commit`` each time, and take the
# before/after snapshot of the original repository only when the test asserts it (``snapshots=True``).
_TEMPLATE_LOCK = threading.Lock()
_TEMPLATE: list[Path] = []


def make_repo(path: Path) -> Path:
    path.mkdir(parents=True)
    for args in (["init", "-q"], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "init"]):
        subprocess.run(["git", "-C", str(path), *args], check=True, capture_output=True)
    return path


def new_repo(path: Path) -> Path:
    """A fresh git repository with one empty commit (a copy of a template made once per test session)."""
    with _TEMPLATE_LOCK:
        if not _TEMPLATE:
            root = Path(tempfile.mkdtemp(prefix="w2b-template-"))
            atexit.register(shutil.rmtree, root, True)
            _TEMPLATE.append(make_repo(root / "repo"))
    shutil.copytree(_TEMPLATE[0], path, symlinks=True)
    return path


def slim_snapshot(repo: Path) -> dict[str, Any]:
    """What a conductor must leave alone in the original repository: refs, HEAD and branch, the working tree."""
    files = sorted(str(p.relative_to(repo)) for p in repo.rglob("*")
                   if p.is_file() and ".git" not in p.relative_to(repo).parts)
    return {"refs": git(repo, "for-each-ref", "--format=%(refname) %(objectname)"),
            "head_branch_status": git(repo, "status", "--porcelain=v2", "--branch", "--untracked-files=all", "--ignored"),
            "files": files}


def light_execute(base: Path, impl_body: str, *, frame: str, adapter: str = "codex", snapshots: bool = False,
                  repo: Path | None = None, **kwargs) -> Run:
    """``execute`` of W2-a without its two full snapshots; ``repo`` lets runs that never touch it share one."""
    from verantyx.conductor_run import conduct_entry

    base.mkdir(parents=True, exist_ok=True)
    state, pids = base / "state", base / "pids"
    pids.mkdir()
    repo = repo if repo is not None else new_repo(base / "repo")
    script = write_script(base / "agent.sh", impl_body.replace("$PIDS", str(pids)))
    frame_path = base / "frame.md"
    frame_path.write_text(frame, encoding="utf-8")
    kwargs.setdefault("codex_bin" if adapter == "codex" else "claude_bin", str(script))
    kwargs.setdefault("state_dir", state)
    kwargs.setdefault("poll_interval", 0.02)
    before = slim_snapshot(repo) if snapshots else {}
    outcome = conduct_entry(frame_path, repo, adapter, **kwargs)
    after = slim_snapshot(repo) if snapshots else {}
    out = outcome.as_dict()
    rows = [r for r in read_ledger(out["ledger"]) if r["run_id"] == out["run_id"]] if out["ledger"] else []
    if out["ledger"]:
        state = Path(out["ledger"]).parent
    return Run(outcome, out, rows, repo, state, pids, before, after)


def verify_execute(base: Path, impl_body: str, *, rules=(), default: dict | None = None, frame: str | None = None,
                   first: str = "", pre: str = "", post: str = "", raw: str | None = None, **kwargs) -> Run:
    """``light_execute`` with a scripted implementer (codex) and a scripted claude verifier."""
    base.mkdir(parents=True, exist_ok=True)
    pids = base / "pids"
    script = verifier_script(base / "verifier.sh", rules=rules, default=default, flavour="claude",
                             first=first.replace("$PIDS", str(pids)), pre=pre.replace("$PIDS", str(pids)), post=post.replace("$PIDS", str(pids)),
                             raw=raw.replace("$PIDS", str(pids)) if raw is not None else None)
    kwargs.setdefault("claude_bin", str(script))
    return light_execute(base, impl_body, frame=frame if frame is not None else sum_frame(), adapter="codex", **kwargs)


def vspec(impl_body: str, **kwargs):
    """A deferred ``verify_execute`` for the shared pool."""
    return lambda base: verify_execute(base, impl_body, **kwargs)


COUNTED = ('n=$(cat $PIDS/count 2>/dev/null || echo 0)\necho $((n+1)) > $PIDS/count\n')


def attempt_dependent(first: str, later: str) -> str:
    """An implementer script that does ``first`` the first time it is started and ``later`` after that."""
    return COUNTED + f'if [ "$n" = 0 ]; then\n{first}else\n{later}fi\n'


# ---------------------------------------------------------------- reading what a run left behind
def verify_dir(run: Run, attempt: int = 1) -> Path:
    return run.state / "runs" / run.out["run_id"] / f"verify-{attempt}"


def verifier_prompts(run: Run, attempt: int = 1) -> list[str]:
    return [p.read_text(encoding="utf-8") for p in sorted((verify_dir(run, attempt) / "sessions").glob("*/prompt.txt"))]


def implementer_prompts(run: Run) -> list[str]:
    base = run.state / "runs" / run.out["run_id"] / "runtime" / "sessions"
    rows = [r for r in run.runtime_rows() if r["type"] == "SESSION_CREATED"]
    return [(base / r["session_id"] / "prompt.txt").read_text(encoding="utf-8") for r in rows]


def verifier_supervisor_pids(run: Run, attempt: int = 1) -> list[int]:
    return [json.loads(p.read_text())["pid"] for p in (verify_dir(run, attempt) / "sessions").glob("*/agent.pid.json")]


def worktree_lines(run: Run) -> list[str]:
    return [line for line in git(run.repo, "worktree", "list")[1].splitlines() if line.strip()]


def untrusted_data(brief: str) -> dict:
    match = re.search(r"^UNTRUSTED_DATA_JSON: (.*)$", brief, re.M)
    assert match, "the brief has no UNTRUSTED_DATA_JSON line"
    return json.loads(match.group(1))


def same_original_repository(run: Run) -> bool:
    assert run.before and run.after, "this run was started without snapshots=True"
    return run.before == run.after


# ---------------------------------------------------------------- runs started through the real command line
@dataclass
class CliRun:
    """A ``python -m verantyx.cli conduct`` run in its own process (so it can share the pool and need not
    capture output): the exit code, the JSON on stdout, stderr and the ledger rows of the run."""

    code: int
    out: dict
    err: str
    rows: list
    repo: Path
    state: Path

    def of(self, kind):
        return [r for r in self.rows if r["type"] == kind]

    def one(self, kind):
        found = self.of(kind)
        assert len(found) == 1, (kind, [r["type"] for r in self.rows])
        return found[0]

    @property
    def types(self):
        return [r["type"] for r in self.rows]


def cli_run(base: Path, impl_body: str, *, frame: str, args=(), verifier_default: dict | None = PASS_GOOD) -> CliRun:
    """Write the frame and the two scripts, run the real CLI as a child process, read the ledger."""
    base.mkdir(parents=True, exist_ok=True)
    repo = new_repo(base / "repo")
    impl = base / "impl.sh"
    impl.write_text("#!/bin/sh\ncat > /dev/null\n" + impl_body, encoding="utf-8")
    impl.chmod(0o755)
    verifier = verifier_script(base / "verifier.sh", default=verifier_default)
    frame_path = base / "frame.md"
    frame_path.write_text(frame, encoding="utf-8")
    argv = [sys.executable, "-m", "verantyx.cli", "conduct", "--frame", str(frame_path), "--repo", str(repo),
            "--adapter", "codex", "--codex-bin", str(impl), "--claude-bin", str(verifier),
            "--state-dir", str(base / "state"), *[str(a) for a in args]]
    env = {**os.environ, "PYTHONPATH": str(ROOT), "PYTHONDONTWRITEBYTECODE": "1"}
    done = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=180)
    out = json.loads(done.stdout)
    rows = [r for r in read_ledger(out["ledger"]) if r["run_id"] == out["run_id"]] if out.get("ledger") else []
    return CliRun(done.returncode, out, done.stderr, rows, repo, base / "state")


def cli_spec(impl_body: str, **kwargs):
    return lambda base: cli_run(base, impl_body, **kwargs)


def execute_with_failing_sandbox_check(base: Path) -> Run:
    """A normal verified run whose sandbox self-check fails for the verifier's re-runs only.

    The patch decides by the run's own directory, so the other runs of the shared pool (which call the same
    function at the same time) get the real self-check."""
    from unittest import mock

    from verantyx import conductor_run

    real = conductor_run._sandbox_selfcheck
    mine = os.path.realpath(base)

    def failing(worktree, tmp_dir):
        if "rerun-tmp" in str(tmp_dir) and os.path.realpath(tmp_dir).startswith(mine + os.sep):
            return {"ok": False, "error": "SANDBOX_SELFCHECK_FAILED", "sandbox": "injected"}
        return real(worktree, tmp_dir)

    with mock.patch.object(conductor_run, "_sandbox_selfcheck", failing):
        return verify_execute(base, HONEST, default=PASS_GOOD, **QUICK_ARGS)
