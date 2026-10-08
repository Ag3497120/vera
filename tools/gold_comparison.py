"""Train-only gold comparison probe and construction acceptance demo."""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import runpy
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GOLD_PROBE = Path("/Users/motonisihikoudai/vera-wiring/phase2/gold_probe.py")
PYTHON = Path("/Users/motonisihikoudai/vera-wiring/env/bin/python")


@contextlib.contextmanager
def _construction_disabled(disabled):
    key = "VERA_CONSTRUCTIONS_OFF"
    existed = key in os.environ
    previous = os.environ.get(key, "")
    names = {name.strip() for name in previous.split(",") if name.strip()}
    if disabled:
        names.add("gold_comparison")
    else:
        names.discard("gold_comparison")
    if names:
        os.environ[key] = ",".join(sorted(names))
    else:
        os.environ.pop(key, None)
    try:
        yield
    finally:
        if existed:
            os.environ[key] = previous
        else:
            os.environ.pop(key, None)


def _counts(probe, seed, disabled):
    with _construction_disabled(disabled):
        stats, _ = probe["wdw"](argparse.Namespace(
            n=150, seed=seed, phenomenon="比較"))
    counts = stats.get("比較", Counter())
    return {name: int(counts.get(name, 0)) for name in
            ("correct", "wrong_overlap", "wrong_other", "abstain")}


def _coverage(disabled):
    env = dict(os.environ)
    env["VERA_CORPUS_ROOT"] = "/tmp/vera-empty-materials"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = "."
    with _construction_disabled(disabled):
        env["VERA_CONSTRUCTIONS_OFF"] = os.environ.get(
            "VERA_CONSTRUCTIONS_OFF", "")
        if not env["VERA_CONSTRUCTIONS_OFF"]:
            env.pop("VERA_CONSTRUCTIONS_OFF")
        result = subprocess.run(
            [str(PYTHON), "-B", "tools/read_coverage.py"],
            cwd=ROOT,
            env=env,
            check=True,
            text=True,
            capture_output=True,
            timeout=50,
        )
    return json.loads(result.stdout)["supported_sentences"]


def _diagnose(probe):
    from verantyx.one import Vera

    with _construction_disabled(True):
        groups = probe["sample"](
            probe["load"]("paraphrase_entail", "who_did_what"),
            "phenomenon", 150, 7)
        rows = groups.get("比較", ())
        reasons = Counter()
        for row in rows:
            if row.get("split") != "train":
                raise AssertionError("gold comparison diagnosis must be train-only")
            vera = Vera.from_texts({"d": row["sentence"]}, mode="semantic")
            try:
                result = vera.ask(row["question"])
            finally:
                vera.close()
            if result.get("verdict") != "ANSWER":
                reasons[result.get("reason") or result.get("verdict") or "unknown"] += 1
    print("seed=7 abstain reasons:")
    for reason, count in sorted(reasons.items()):
        print(f"  {reason}: {count}")


def main():
    if not GOLD_PROBE.is_file():
        raise AssertionError("gold probe is unavailable")
    probe = runpy.run_path(str(GOLD_PROBE), run_name="gold_probe_api")
    measurements = {}
    for seed in (7, 101):
        off = _counts(probe, seed, True)
        on = _counts(probe, seed, False)
        measurements[seed] = (off, on)
        for state, counts in (("off", off), ("on", on)):
            print(
                f"seed={seed} gold_comparison={state} "
                f"correct={counts['correct']} "
                f"wrong_overlap={counts['wrong_overlap']} "
                f"wrong_other={counts['wrong_other']} "
                f"abstain={counts['abstain']}"
            )

    for seed, (off, on) in measurements.items():
        if on["correct"] <= off["correct"]:
            raise AssertionError(f"gold correct did not rise at seed {seed}")
        if on["wrong_other"] > off["wrong_other"]:
            raise AssertionError(f"wrong_other rose at seed {seed}")
        if on["wrong_overlap"] > off["wrong_overlap"]:
            raise AssertionError(f"wrong_overlap rose at seed {seed}")

    _diagnose(probe)
    coverage_off = _coverage(True)
    coverage_on = _coverage(False)
    print(f"supported_sentences off={coverage_off} on={coverage_on}")
    if coverage_on < coverage_off:
        raise AssertionError("reading coverage fell")
    print("DEMO OK")


if __name__ == "__main__":
    main()
