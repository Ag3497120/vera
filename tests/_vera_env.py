"""Named external resources the suite may need, and the one way to report their absence.

A test that cannot run because a resource is missing is classified, not
silently skipped: its skip reason starts with ``ENV_MISSING[<resource>]`` and
the session summary lists every such skip grouped by resource. A machine that
has the resource runs the test.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

PREFIX = "ENV_MISSING"


def _home_projects(*parts: str) -> Path:
    return Path.home().joinpath("Projects", *parts)


def _node() -> bool:
    return shutil.which("node") is not None


def _node_jitless_quiet() -> bool:
    node = shutil.which("node")
    if node is None:
        return False
    try:
        done = subprocess.run([node, "--jitless", "--no-warnings", "-e", "console.log(1)"],
                              capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0 and done.stderr == ""


def _fugashi() -> bool:
    try:
        import fugashi
        fugashi.Tagger()
    except Exception:
        return False
    return True


def round5_dev_fixtures_path() -> Path:
    override = os.environ.get("VERA_ROUND5_DEV_FIXTURES")
    return Path(override) if override else _home_projects("vera-round5-dev", "fixtures.jsonl")


def sealed1_dir() -> Path:
    override = os.environ.get("VERA_JA_SEALED1_DIR")
    return Path(override) if override else _home_projects("vera-ja-sealed1")


def _sealed1() -> bool:
    data = sealed1_dir()
    return len(list(data.glob("doc_*.json"))) == 10 and len(list(data.glob("ab_*.json"))) == 6


def eval_fixture_dirs(names: list[str]) -> list[Path]:
    directories: list[Path] = []
    for name in names:
        if "*" in name:
            directories.extend(_home_projects().glob(name))
        else:
            directories.append(_home_projects(name))
    return directories


def _eval_fixtures() -> bool:
    listed = (Path(__file__).resolve().parents[1] / "tools" / "eval_dirs.txt").read_text(encoding="utf-8").splitlines()
    names = [line.strip() for line in listed if line.strip() and not line.startswith("#")]
    return any(d.exists() for d in eval_fixture_dirs(names))


# name -> (availability probe, what is needed and which tests use it)
RESOURCES = {
    "fugashi": (_fugashi, "fugashi + unidic-lite importable (Japanese tokenizer; the semantic stack needs it)"),
    "node": (_node, "`node` on PATH (JavaScript execution in test_contract_lower, test_round4)"),
    "node_jitless_quiet": (_node_jitless_quiet,
                           "`node` on PATH whose `--jitless --no-warnings` run writes nothing to stderr "
                           "(the contract_lower tests treat any stderr as failure; this machine's node warns about --expose_wasm)"),
    "round5_dev_fixtures": (lambda: round5_dev_fixtures_path().is_file(),
                            "$VERA_ROUND5_DEV_FIXTURES or ~/Projects/vera-round5-dev/fixtures.jsonl"),
    "ja_sealed1_dev_fixtures": (_sealed1, "$VERA_JA_SEALED1_DIR or ~/Projects/vera-ja-sealed1 with 10 doc_* and 6 ab_* files"),
    "eval_fixtures": (_eval_fixtures, "any directory listed in tools/eval_dirs.txt under ~/Projects"),
    "sandbox_integration": (lambda: os.environ.get("VERA_SANDBOX_INTEGRATION") == "1",
                            "VERA_SANDBOX_INTEGRATION=1 on macOS with a root-owned sandbox worker"),
}


def available(name: str) -> bool:
    return RESOURCES[name][0]()


def reason(name: str) -> str:
    return f"{PREFIX}[{name}]: {RESOURCES[name][1]}"


def require(name: str) -> None:
    if not available(name):
        pytest.skip(reason(name))
