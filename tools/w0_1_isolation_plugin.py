"""pytest plugin: after the whole session, list every verantyx* module loaded from outside this tree.

Use:  PYTHONPATH=<tree>:<tree>/tools python -m pytest -p w0_1_isolation_plugin ...
It only reports (a line `W0-1 ISOLATION: ...` in the terminal summary); it never changes a result.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _outside(module) -> list[str]:
    file = getattr(module, "__file__", None)
    paths = [file] if file else list(getattr(module, "__path__", []) or [])
    return [p for p in paths if not Path(p).resolve().is_relative_to(ROOT)] or ([] if paths else ["<no __file__/__path__>"])


def pytest_terminal_summary(terminalreporter):
    bad = {name: _outside(m) for name, m in sorted(sys.modules.items()) if name.split(".")[0] == "verantyx"}
    bad = {n: p for n, p in bad.items() if p}
    count = sum(1 for n in sys.modules if n.split(".")[0] == "verantyx")
    terminalreporter.section("W0-1 isolation")
    terminalreporter.write_line(f"W0-1 ISOLATION: verantyx modules loaded in this session: {count}; outside the tree: {len(bad)} {bad}")
