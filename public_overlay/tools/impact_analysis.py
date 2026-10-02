"""Print tests/demos selected by Python import impact."""

from __future__ import annotations

import argparse
import importlib.util
import shlex
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
IMPACT_PATH = REPO_ROOT / "verantyx" / "impact.py"
IMPACT_SPEC = importlib.util.spec_from_file_location("_vera_impact_analysis", IMPACT_PATH)
if IMPACT_SPEC is None or IMPACT_SPEC.loader is None:
    raise RuntimeError(f"cannot load impact analyzer: {IMPACT_PATH}")
IMPACT_MODULE = importlib.util.module_from_spec(IMPACT_SPEC)
sys.modules[IMPACT_SPEC.name] = IMPACT_MODULE
IMPACT_SPEC.loader.exec_module(IMPACT_MODULE)
analyze_impact = IMPACT_MODULE.analyze_impact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--changed", nargs="+", required=True, metavar="PATH")
    parser.add_argument("--repo", default=".", metavar="DIR")
    parser.add_argument("--select-cmd", action="store_true", help="print a pytest command for affected tests")
    parser.add_argument("--why", action="store_true", help="include each affected path's shortest import chain")
    args = parser.parse_args(argv)

    report = analyze_impact(args.changed, args.repo)
    if args.select_cmd:
        selected_tests = report.tests
        command = [sys.executable, "-m", "pytest", *selected_tests]
        print(shlex.join(command))
    elif args.why:
        for item in report.affected:
            print(item.explain())
    else:
        for path in report.paths:
            print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
