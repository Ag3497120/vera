#!/usr/bin/env python3
"""Check that nothing named verantyx* is loaded from outside this tree (G1 / G2 of W0-1).

  --import   import verantyx, then require every sys.modules entry named verantyx[.*] with a __file__
             to live under the tree root; modules with no __file__ (namespace packages) are listed
             as NO_FILE and treated as violations unless their __path__ entries are all in the tree.
  --collect  run `pytest --collect-only -q -p no:cacheprovider tests` in this process, report the
             collected count and collection errors, then apply the same check to sys.modules.

Exit 0 only when every check passes. The tree root is the parent of tools/ (this file's location),
never the current directory.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _inside(path: str) -> bool:
    try:
        Path(path).resolve().relative_to(ROOT)
    except ValueError:
        return False
    return True


def violations() -> list[str]:
    bad: list[str] = []
    for name, module in sorted(sys.modules.items()):
        if name.split(".")[0] != "verantyx":
            continue
        file = getattr(module, "__file__", None)
        if file:
            if not _inside(file):
                bad.append(f"{name} -> {file}")
            continue
        search = list(getattr(module, "__path__", []) or [])
        if not search:
            bad.append(f"{name} -> NO_FILE (no __file__, no __path__)")
        elif not all(_inside(p) for p in search):
            bad.append(f"{name} -> NAMESPACE_PATH {search}")
    return bad


def check_import() -> int:
    import verantyx  # noqa: F401

    bad = violations()
    count = sum(1 for name in sys.modules if name.split(".")[0] == "verantyx")
    print(f"tree root: {ROOT}")
    print(f"verantyx.__file__: {verantyx.__file__}")
    print(f"verantyx modules loaded: {count}")
    print(f"violations: {bad}")
    return 1 if bad else 0


def check_collect() -> int:
    import pytest

    class Counter:
        collected = 0
        errors = 0

        def pytest_collection_modifyitems(self, items):
            Counter.collected = len(items)

        def pytest_collectreport(self, report):
            if report.failed:
                Counter.errors += 1

    code = pytest.main(["--collect-only", "-q", "-p", "no:cacheprovider", str(ROOT / "tests")], plugins=[Counter()])
    bad = violations()
    count = sum(1 for name in sys.modules if name.split(".")[0] == "verantyx")
    print(f"tree root: {ROOT}")
    print(f"pytest.main return code: {int(code)}")
    print(f"collected items: {Counter.collected}")
    print(f"collection errors: {Counter.errors}")
    print(f"verantyx modules loaded after collection: {count}")
    print(f"violations: {bad}")
    return 1 if (int(code) != 0 or Counter.errors or bad) else 0


def main(argv: list[str]) -> int:
    if argv[1:] == ["--import"]:
        return check_import()
    if argv[1:] == ["--collect"]:
        return check_collect()
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
