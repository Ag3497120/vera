"""Diagnose and gate the reason construction against the approved train probe."""
from __future__ import annotations

import ast
import contextlib
import io
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
from collections import Counter


ROOT = Path(__file__).resolve().parents[1]
PYTHON = "/Users/motonisihikoudai/vera-wiring/env/bin/python"
GOLD_PROBE = "/Users/motonisihikoudai/vera-wiring/phase2/gold_probe.py"
PHENOMENON = "理由"
N = 150


def _probe(seed: int, disabled: bool) -> tuple[dict[str, int], Counter[str]]:
    from verantyx.one import Vera

    prior_off = os.environ.get("VERA_CONSTRUCTIONS_OFF")
    prior_argv = sys.argv
    prior_ask = Vera.ask
    os.environ["VERA_CONSTRUCTIONS_OFF"] = "gold_reason" if disabled else ""
    calls = 0
    reasons: Counter[str] = Counter()

    def traced_ask(self, *args, **kwargs):
        nonlocal calls
        result = prior_ask(self, *args, **kwargs)
        calls += 1
        if isinstance(result, dict) and result.get("verdict") != "ANSWER":
            reason = result.get("reason")
            if isinstance(reason, str) and reason:
                reasons[reason] += 1
        return result

    Vera.ask = traced_ask
    argv = [GOLD_PROBE, "wdw", "--phenomenon", PHENOMENON,
            "--n", str(N), "--seed", str(seed)]
    output = io.StringIO()
    try:
        sys.argv = argv
        with contextlib.redirect_stdout(output):
            runpy.run_path(GOLD_PROBE, run_name="__main__")
    finally:
        Vera.ask = prior_ask
        sys.argv = prior_argv
        if prior_off is None:
            os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
        else:
            os.environ["VERA_CONSTRUCTIONS_OFF"] = prior_off

    if calls != N:
        raise AssertionError(f"gold probe made {calls} ask calls, expected {N}")
    match = re.search(r"^TOTAL\s+(\{.*\})\s+seconds\s+\d+\s*$",
                      output.getvalue(), re.MULTILINE)
    if match is None:
        raise AssertionError("gold probe did not print its totals")
    counts = ast.literal_eval(match.group(1))
    if not isinstance(counts, dict) or sum(counts.values()) != N:
        raise AssertionError("gold probe totals do not sum to the requested sample")
    return {str(key): int(value) for key, value in counts.items()}, reasons


def _coverage(disabled: bool) -> int:
    env = os.environ.copy()
    env.update({
        "VERA_CORPUS_ROOT": "/tmp/vera-empty-materials",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": ".",
        "VERA_CONSTRUCTIONS_OFF": "gold_reason" if disabled else "",
    })
    completed = subprocess.run(
        [PYTHON, "-B", "tools/read_coverage.py", "--n", "1500", "--stride", "200"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=45, check=True,
    )
    result = json.loads(completed.stdout)
    supported = result.get("supported_sentences")
    if type(supported) is not int:
        raise AssertionError("read_coverage did not report supported_sentences")
    return supported


def _count(counts: dict[str, int], key: str) -> int:
    return counts.get(key, 0)


def _print_counts(seed: int, state: str, counts: dict[str, int]) -> None:
    print(f"seed={seed} {state}: correct={_count(counts, 'correct')} "
          f"wrong_overlap={_count(counts, 'wrong_overlap')} "
          f"wrong_other={_count(counts, 'wrong_other')} "
          f"abstain={_count(counts, 'abstain')}")


def main() -> None:
    os.chdir(ROOT)
    os.environ["VERA_CORPUS_ROOT"] = "/tmp/vera-empty-materials"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["PYTHONPATH"] = "."

    before7, reasons = _probe(7, True)
    after7, _ = _probe(7, False)
    before101, _ = _probe(101, True)
    after101, _ = _probe(101, False)
    coverage_before = _coverage(True)
    coverage_after = _coverage(False)

    print("ABSTAIN REASONS seed=7, gold_reason off:")
    for reason, count in sorted(reasons.items()):
        print(f"  {reason}: {count}")
    _print_counts(7, "off", before7)
    _print_counts(7, "on", after7)
    _print_counts(101, "off", before101)
    _print_counts(101, "on", after101)
    print(f"supported_sentences off={coverage_before} on={coverage_after}")

    for seed, before, after in ((7, before7, after7), (101, before101, after101)):
        assert _count(after, "correct") > _count(before, "correct"), \
            f"correct did not rise on seed {seed}"
        assert _count(after, "wrong_other") <= _count(before, "wrong_other"), \
            f"wrong_other rose on seed {seed}"
        assert _count(after, "wrong_overlap") <= _count(before, "wrong_overlap"), \
            f"wrong_overlap rose on seed {seed}"
    assert coverage_after >= coverage_before, "supported sentence coverage fell"
    print("DEMO OK")


if __name__ == "__main__":
    main()
