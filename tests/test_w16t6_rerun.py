"""W16-t6 / T6-4: `--rerun` runs only the allowed forms (docs/ATTEST.md section 3). A refused command is never started."""
import os
import re
import sys
from pathlib import Path

import pytest

from verantyx import attest
from verantyx.attest import TESTIMONY, Verifier, check_command

T = "def test_a():\n    assert True\n"


@pytest.fixture
def tree(tmp_path, monkeypatch):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "x.py").write_text(T)
    (tmp_path / "pytest.ini").write_text("")
    outside = tmp_path.parent / (tmp_path.name + "_outside")
    outside.mkdir()
    (outside / "evil.py").write_text(T)
    os.symlink(str(outside / "evil.py"), str(tmp_path / "tests" / "link.py"))
    os.symlink(str(outside), str(tmp_path / "tests" / "dirlink"))
    calls = []

    def fake(argv, cwd, timeout, env=None):
        calls.append((list(argv), cwd, timeout, env))
        return 0, b"", b""
    monkeypatch.setattr(attest, "_spawn", fake)
    return tmp_path, calls


REFUSED = [
    "pytest tests/x.py; rm -rf /", "pytest $(echo x)", "pytest tests/x.py `id`", "pytest tests/x.py | cat", "pytest tests/x.py && ls", "pytest tests/x.py > /tmp/o", "pytest tests/x.py\nrm a",
    "bash -c 'pytest tests/x.py'", "sh tests/x.py", "env A=1 pytest tests/x.py", "A=1 pytest tests/x.py", "python -c 'import os'", "python -m pip install x",
    "python -m verantyx.cli forget foo", "/bin/pytest tests/x.py", "/usr/bin/python -m pytest tests/x.py", "pytest -p evil tests/x.py", "pytest -c /tmp/x.ini tests/x.py",
    "pytest --rootdir=/ tests/x.py", "pytest --rootdir / tests/x.py", "pytest ../outside/test_x.py", "pytest /abs/outside.py", "pytest tests/../../x.py", "pytest tests/link.py",
    "pytest tests/dirlink/evil.py", "pytest --pyargs os", "python3 -m pytest -p pytester tests/x.py", "pytest -o addopts=-x tests/x.py", "pytest --import-mode=importlib tests/x.py",
    "pytest --basetemp /tmp tests/x.py", "pytest --confcutdir / tests/x.py", "pytest", "pytest -q", "pytest tests/x.txt", "pytest tests", "pytest pkg/test_x.py",
    "pytest -k '-x' tests/x.py", "pytest -k 'a;b' tests/x.py", "python -m pytest\ttests/x.py\r", "python3.11 -m unittest tests/x.py", "python -m pytest -p no:evil tests/x.py", "",
    "pytest -pno:cacheprovider tests/x.py", "pytest --co tests/x.py",
]


@pytest.mark.parametrize("cmd", REFUSED)
def test_refused_forms_never_reach_spawn(tree, cmd):
    root, calls = tree
    assert check_command(cmd, str(root))[0] is None
    for rerun in (True,):
        f = Verifier(str(root), rerun=rerun).exit_fact(cmd, 0) if cmd.strip() else None
        if f is not None:
            assert f["mark"] == TESTIMONY and f["reason"] in ("COMMAND_NOT_ALLOWED", "NO_COMMAND")
    assert calls == []


def test_allowed_forms_become_a_fixed_argv_without_a_shell(tree):
    root, calls = tree
    for cmd in ("pytest -q tests/x.py", "python -m pytest -q -x tests/x.py", "python3 -m pytest tests/x.py::test_a", "python3.11 -m pytest -q -k 'a or b' tests/x.py",
                "pytest --collect-only -q tests/x.py -p no:cacheprovider"):
        argv, why = check_command(cmd, str(root))
        assert argv is not None, (cmd, why)
        assert argv[:3] == [sys.executable, "-m", "pytest"] and argv[-2:] == ["-p", "no:cacheprovider"]
    f = Verifier(str(root), rerun=True).exit_fact("python -m pytest -q tests/x.py", 0)
    assert f["mark"] == "RECORD"
    assert len(calls) == 1
    argv, cwd, timeout, env = calls[0]
    assert argv == [sys.executable, "-m", "pytest", "-q", "tests/x.py", "-p", "no:cacheprovider"]
    assert cwd == os.path.realpath(str(root)) and timeout == attest.DEFAULT_TIMEOUT
    assert env["PYTHONPATH"] == os.path.realpath(str(root)) and env["PYTHONDONTWRITEBYTECODE"] == "1"


def test_same_command_is_run_once_per_attest(tree):
    root, calls = tree
    v = Verifier(str(root), rerun=True)
    v.exit_fact("pytest -q tests/x.py", 0)
    v.exit_fact("pytest -q tests/x.py", 0)
    assert len(calls) == 1


def test_without_rerun_nothing_is_started(tree):
    root, calls = tree
    f = Verifier(str(root)).exit_fact("pytest -q tests/x.py", 0)
    assert f["reason"] == "NO_EVENT" and calls == []


def test_timeout_is_a_reason_not_a_crash(tree, monkeypatch):
    root, calls = tree
    monkeypatch.setattr(attest, "_spawn", lambda *a, **k: (None, b"", b"timeout"))
    f = Verifier(str(root), rerun=True).exit_fact("pytest -q tests/x.py", 0)
    assert (f["mark"], f["reason"]) == (TESTIMONY, "RERUN_TIMEOUT")


def test_git_is_read_only(tree):
    root, calls = tree
    v = Verifier(str(root))
    for sub in ("commit", "checkout", "reset", "add", "clean", "push", "config"):
        with pytest.raises(ValueError):
            v._git(sub, "x")
    assert calls == []


def test_static_one_process_start_and_no_shell():
    src = Path(attest.__file__).read_text(encoding="utf-8")
    assert len(re.findall(r"subprocess\.", src)) == 1
    assert "shell=False" in src and "shell=True" not in src
    for bad in ("os.system", "os.popen", "os.exec", "os.spawn", "pty."):
        assert bad not in src
    assert src.count("_spawn(") >= 2 and len(re.findall(r"def _spawn\(", src)) == 1
