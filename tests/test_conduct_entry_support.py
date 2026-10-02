"""Shared fixtures and helpers for the conduct-entry tests (no tests of its own).

Three guards apply to every conduct-entry test module that star-imports this one:
* ``verantyx`` must be loaded from this checkout (the venv holds an unrelated editable
  ``verantyx``, which would make every test pass against the wrong code);
* a fake ``codex`` and ``claude`` sit first on PATH and leave a mark if ever started; every
  test ends by asserting no mark exists, so no test can have launched a real agent;
* ``no_agent_process`` makes any ``subprocess.Popen`` whose program is not ``git`` fail.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VERA_FRAME = ROOT / "docs" / "frames" / "vera_project_frame.md"
EXAMPLE_FRAMES = sorted((ROOT / "docs" / "frames" / "examples").glob("*.md"))
FIXED_CLOCK = lambda: "1970-01-01T00:00:00"  # noqa: E731


def _own_modules():
    import verantyx  # noqa: F401

    outside = []
    for name, module in list(sys.modules.items()):
        path = getattr(module, "__file__", None)
        if name.split(".")[0] == "verantyx" and path and not Path(path).resolve().is_relative_to(ROOT):
            outside.append((name, path))
    return outside


@pytest.fixture(autouse=True)
def verantyx_comes_from_this_tree():
    assert _own_modules() == []
    yield
    assert _own_modules() == []


@pytest.fixture(autouse=True)
def fake_agent_bins(tmp_path_factory, monkeypatch):
    """A fake codex and claude that record being started; the test must never start them."""
    bindir = tmp_path_factory.mktemp("fakebin")
    mark = bindir / "STARTED"
    for name in ("codex", "claude"):
        script = bindir / name
        script.write_text(f'#!/bin/sh\necho "{name} $@" >> "{mark}"\nexit 99\n')
        script.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ.get('PATH', '')}")
    yield mark
    assert not mark.exists(), "a test started a real codex or claude: " + mark.read_text()


@pytest.fixture
def no_agent_process(monkeypatch):
    """Fail on any Popen whose program is not git (dry-run must not start an agent)."""
    real = subprocess.Popen
    started: list[object] = []

    class Guard(real):  # type: ignore[misc, valid-type]
        def __init__(self, args, *a, **k):
            program = args if isinstance(args, (str, bytes, os.PathLike)) else args[0]
            if os.path.basename(os.fsdecode(program)) != "git":
                started.append(args)
                raise AssertionError(f"dry run tried to start a process: {args!r}")
            super().__init__(args, *a, **k)

    monkeypatch.setattr(subprocess, "Popen", Guard)
    yield started
    assert started == []


@pytest.fixture
def git_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    for args in (["init", "-q"], ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-q", "--allow-empty", "-m", "init"]):
        subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
    return repo


def run_cli(argv, capsys):
    """Call the real CLI in-process; return (exit code, parsed stdout JSON, stderr text)."""
    from verantyx import cli

    code = cli.main(argv)
    captured = capsys.readouterr()
    return code, json.loads(captured.out), captured.err


def conduct_argv(frame, repo, adapter, *extra):
    return ["conduct", "--frame", str(frame), "--repo", str(repo), "--adapter", adapter, *extra]


def read_ledger(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


def rows_of(rows, kind):
    return [row for row in rows if row["type"] == kind]


def compiled_records(frame_path, tmp_path):
    """Compile a Markdown frame with a fixed clock; returns the record list."""
    from verantyx.memory_frame import Memory
    from verantyx.project_frame import compile_frame, parse_frame

    spec = parse_frame(Path(frame_path).read_text(encoding="utf-8"), source=str(frame_path))
    return compile_frame(spec, Memory(str(tmp_path / "m-fixed.jsonl"), now=FIXED_CLOCK)).records


MINIMAL_FRAME = """\
[goal]
project: Tiny
statement: A tiny project
[philosophy_invariants]
I1: Keep it small
[completion_criteria]
C1: The check passes | {"kind":"command_exit","command":["true"],"expected_exit":0}
[phases]
P1: Do the work
[phase_order]
none: none
[decisions]
D1: goal authority => The human decides
[vocabulary_aliases]
none: none
[escalation_conditions]
none: none
[protected_actions]
none: none
"""
