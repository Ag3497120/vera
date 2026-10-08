#!/usr/bin/env python3
"""Compare train-only parallel/choice gold probes and reading coverage."""
from __future__ import annotations

import argparse
import collections
import json
import os
import runpy
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PHENOMENON = "並列と選択"
N = 150
GOLD_PROBE = Path("/Users/motonisihikoudai/vera-wiring/phase2/gold_probe.py")


def _off_value(base: str, *, disable_parallel: bool) -> str:
    disabled = {name.strip() for name in base.split(",") if name.strip()}
    if disable_parallel:
        disabled.add("gold_parallel")
    else:
        disabled.discard("gold_parallel")
    return ",".join(sorted(disabled))


def _metrics(result) -> dict[str, int]:
    return {name: int(result.get(name, 0))
            for name in ("correct", "wrong_overlap", "wrong_other", "abstain")}


def _probe(wdw, seed: int, disabled: str, *, diagnose: bool = False):
    previous = os.environ.get("VERA_CONSTRUCTIONS_OFF", "")
    os.environ["VERA_CONSTRUCTIONS_OFF"] = disabled
    reasons: collections.Counter[tuple[str, str, str]] = collections.Counter()
    try:
        if diagnose:
            import verantyx.one as one

            original = one.Vera.ask

            def observed(self, *args, **kwargs):
                result = original(self, *args, **kwargs)
                if result.get("verdict") != "ANSWER":
                    reasons[(result.get("verdict", ""), result.get("phase", ""),
                             result.get("reason", ""))] += 1
                return result

            one.Vera.ask = observed
        else:
            original = None
        try:
            counts, _ = wdw(argparse.Namespace(n=N, seed=seed, phenomenon=PHENOMENON))
        finally:
            if diagnose:
                one.Vera.ask = original
    finally:
        if previous:
            os.environ["VERA_CONSTRUCTIONS_OFF"] = previous
        else:
            os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
    return _metrics(counts.get(PHENOMENON, {})), reasons


def _coverage(disabled: str) -> int:
    env = os.environ.copy()
    env["VERA_CONSTRUCTIONS_OFF"] = disabled
    result = subprocess.run(
        [sys.executable, "-B", str(ROOT / "tools" / "read_coverage.py"),
         "--n", "1500", "--stride", "200"],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
        timeout=50,
    )
    payload = json.loads(result.stdout)
    value = payload.get("supported_sentences")
    if type(value) is not int:
        raise AssertionError("read_coverage.py omitted supported_sentences")
    return value


def main() -> int:
    original_off = os.environ.get("VERA_CONSTRUCTIONS_OFF", "")
    off = _off_value(original_off, disable_parallel=True)
    on = _off_value(original_off, disable_parallel=False)
    probe_ns = runpy.run_path(str(GOLD_PROBE), run_name="gold_probe_for_parallel_demo")
    wdw = probe_ns["wdw"]

    results: dict[int, tuple[dict[str, int], dict[str, int]]] = {}
    diagnosis = collections.Counter()
    for seed in (7, 101):
        before, reasons = _probe(wdw, seed, off, diagnose=(seed == 7))
        after, _ = _probe(wdw, seed, on)
        results[seed] = (before, after)
        if seed == 7:
            diagnosis = reasons
        print(f"seed={seed} off={before} on={after}")

    print("abstain reasons (seed=7, gold_parallel off):")
    for (verdict, phase, reason), count in sorted(diagnosis.items()):
        print(f"  {count}: {verdict} / {phase} / {reason}")

    coverage_off = _coverage(off)
    coverage_on = _coverage(on)
    print(f"supported_sentences off={coverage_off} on={coverage_on}")

    for seed, (before, after) in results.items():
        assert before["correct"] + before["wrong_overlap"] + before["wrong_other"] + before["abstain"] == N
        assert after["correct"] + after["wrong_overlap"] + after["wrong_other"] + after["abstain"] == N
        assert after["correct"] > before["correct"], f"correct did not rise on seed {seed}"
        assert after["wrong_other"] <= before["wrong_other"], f"wrong_other rose on seed {seed}"
        assert after["wrong_overlap"] <= before["wrong_overlap"], f"wrong_overlap rose on seed {seed}"
    assert coverage_on >= coverage_off, "supported_sentences fell with gold_parallel enabled"
    print("DEMO OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
