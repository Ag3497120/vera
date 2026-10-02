"""Small, isolated checks for static and dynamic import impact selection."""

from __future__ import annotations

import subprocess
import importlib.util
import sys
import tempfile
from pathlib import Path

IMPACT_PATH = Path(__file__).resolve().parent.parent / "verantyx" / "impact.py"
IMPACT_SPEC = importlib.util.spec_from_file_location("_vera_demo_impact", IMPACT_PATH)
if IMPACT_SPEC is None or IMPACT_SPEC.loader is None:
    raise RuntimeError(f"cannot load impact analyzer: {IMPACT_PATH}")
IMPACT_MODULE = importlib.util.module_from_spec(IMPACT_SPEC)
sys.modules[IMPACT_SPEC.name] = IMPACT_MODULE
IMPACT_SPEC.loader.exec_module(IMPACT_MODULE)
analyze_impact = IMPACT_MODULE.analyze_impact


def _write(root: Path, relative: str, source: str = "") -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _assert_equal(actual: object, expected: object) -> int:
    assert actual == expected, f"expected {expected!r}, got {actual!r}"
    return 1


def main() -> None:
    assertions = 0
    with tempfile.TemporaryDirectory(prefix="vera-impact-") as temporary:
        repo = Path(temporary)
        _write(repo, "app/__init__.py")
        _write(repo, "app/core.py", "VALUE = 1\n")
        _write(repo, "app/mid.py", "import app.core\n")
        _write(repo, "app/wrapper.py", "import app.mid\n")
        _write(repo, "app/cycle_a.py", "import app.cycle_b\n")
        _write(repo, "app/cycle_b.py", "import app.cycle_a\nimport app.core\n")
        _write(repo, "app/plugin.py", "PLUGIN = True\n")
        _write(
            repo,
            "app/loader.py",
            'from importlib import import_module as load\nload("app." + "plugin")\n',
        )
        _write(repo, "app/legacy_loader.py", '__import__("app." + "plugin")\n')
        _write(repo, "app/discover.py", "from pkgutil import iter_modules as discover_modules\nlist(discover_modules(__path__))\n")
        _write(repo, "app/independent.py", "VALUE = 2\n")
        _write(repo, "tests/__init__.py")
        _write(repo, "tests/test_direct.py", "import app.core\n")
        _write(repo, "tests/test_transitive.py", "import app.wrapper\n")
        _write(repo, "tests/test_cycle.py", "import app.cycle_a\n")
        _write(repo, "tests/test_dynamic.py", "import app.loader\n")
        _write(repo, "tests/test_builtin_dynamic.py", "import app.legacy_loader\n")
        _write(repo, "tests/test_unresolved.py", "import app.discover\n")
        _write(repo, "tools/demo_chain.py", "import app.cycle_b\n")
        _write(repo, "tools/demo_independent.py", "import app.independent\n")

        core = analyze_impact(["app/core.py"], repo)
        expected_core = (
            "tests/test_cycle.py",
            "tests/test_direct.py",
            "tests/test_transitive.py",
            "tests/test_unresolved.py",
            "tools/demo_chain.py",
        )
        assertions += _assert_equal(core.paths, expected_core)
        assertions += _assert_equal(core.tests, expected_core[:4])
        assertions += _assert_equal(core.demos, expected_core[4:])

        by_path = {item.path: item for item in core.affected}
        assertions += _assert_equal(by_path["tests/test_direct.py"].chain, ("tests/test_direct.py", "app/core.py"))
        assertions += _assert_equal(
            by_path["tests/test_transitive.py"].chain,
            ("tests/test_transitive.py", "app/wrapper.py", "app/mid.py", "app/core.py"),
        )
        assertions += _assert_equal(
            by_path["tests/test_cycle.py"].chain,
            ("tests/test_cycle.py", "app/cycle_a.py", "app/cycle_b.py", "app/core.py"),
        )
        assertions += _assert_equal(
            by_path["tests/test_unresolved.py"].reasons,
            ("import", "UNRESOLVED"),
        )
        assertions += _assert_equal("tests/test_dynamic.py" in core.paths, False)
        assertions += _assert_equal("tools/demo_independent.py" in core.paths, False)

        plugin = analyze_impact(["app/plugin.py"], repo)
        assertions += _assert_equal(
            plugin.paths,
            ("tests/test_builtin_dynamic.py", "tests/test_dynamic.py", "tests/test_unresolved.py"),
        )
        plugin_by_path = {item.path: item for item in plugin.affected}
        assertions += _assert_equal(
            plugin_by_path["tests/test_dynamic.py"].chain,
            ("tests/test_dynamic.py", "app/loader.py", "app/plugin.py"),
        )
        assertions += _assert_equal(
            plugin_by_path["tests/test_dynamic.py"].reasons,
            ("import", "dynamic import"),
        )
        assertions += _assert_equal(
            plugin_by_path["tests/test_builtin_dynamic.py"].chain,
            ("tests/test_builtin_dynamic.py", "app/legacy_loader.py", "app/plugin.py"),
        )
        assertions += _assert_equal(
            plugin_by_path["tests/test_builtin_dynamic.py"].reasons,
            ("import", "dynamic import"),
        )

        cli = Path(__file__).with_name("impact_analysis.py")
        listing = subprocess.run(
            [sys.executable, str(cli), "--changed", "app/core.py", "--repo", str(repo)],
            check=True,
            capture_output=True,
            text=True,
        )
        assertions += _assert_equal(tuple(listing.stdout.splitlines()), expected_core)

        command = subprocess.run(
            [sys.executable, str(cli), "--changed", "app/core.py", "--repo", str(repo), "--select-cmd"],
            check=True,
            capture_output=True,
            text=True,
        )
        expected_command = " ".join(
            [
                sys.executable,
                "-m",
                "pytest",
                "tests/test_cycle.py",
                "tests/test_direct.py",
                "tests/test_transitive.py",
                "tests/test_unresolved.py",
            ]
        )
        assertions += _assert_equal(command.stdout.strip(), expected_command)

        unresolved_file = repo / "app/new_or_deleted.py"
        assertions += _assert_equal(
            analyze_impact(["app/new_or_deleted.py"], repo).paths,
            tuple(sorted(path for path in (
                "tests/test_cycle.py",
                "tests/test_direct.py",
                "tests/test_builtin_dynamic.py",
                "tests/test_dynamic.py",
                "tests/test_transitive.py",
                "tests/test_unresolved.py",
                "tools/demo_chain.py",
                "tools/demo_independent.py",
            ))),
        )
        assertions += _assert_equal(unresolved_file.exists(), False)
        assert assertions == 18, f"unexpected assertion count: {assertions}"
    print("DEMO OK")


if __name__ == "__main__":
    main()
