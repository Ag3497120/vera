#!/usr/bin/env python3
"""Offline gold-probe demo for the passive source construction."""
from __future__ import annotations

import json
import os
import runpy
import subprocess
import sys
import tempfile
from collections import Counter
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path("/Users/motonisihikoudai/vera-wiring/env/bin/python")
GOLD_PROBE = Path("/Users/motonisihikoudai/vera-wiring/phase2/gold_probe.py")


def _environment(disabled: bool) -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("VERA_CORPUS_ROOT", "/tmp/vera-empty-materials")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = "."
    env["VERA_CONSTRUCTIONS_OFF"] = "gold_passive" if disabled else ""
    return env


def _probe(seed: int, disabled: bool, output: Path) -> dict[str, int]:
    command = [str(PYTHON), "-B", str(GOLD_PROBE), "wdw", "--phenomenon", "受け身",
               "--n", "150", "--seed", str(seed), "--json", str(output)]
    subprocess.run(command, cwd=ROOT, env=_environment(disabled), check=True,
                   capture_output=True, text=True, timeout=25)
    data = json.loads(output.read_text(encoding="utf-8"))
    stats = data["by"]["受け身"]
    return {name: int(stats.get(name, 0))
            for name in ("correct", "wrong_other", "wrong_overlap", "abstain")}


def _coverage(disabled: bool, output: Path) -> int:
    command = [str(PYTHON), "-B", "tools/read_coverage.py", "--n", "1500",
               "--stride", "200", "--json", str(output)]
    subprocess.run(command, cwd=ROOT, env=_environment(disabled), check=True,
                   capture_output=True, text=True, timeout=40)
    return int(json.loads(output.read_text(encoding="utf-8"))["supported_sentences"])


def _diagnose_gold_abstains(seed: int, output: Path) -> None:
    """Count typed reasons on the probe's sampled train items, without writing them."""
    rows = []
    last_result = None
    path = str(GOLD_PROBE)
    old_argv = sys.argv
    old_off = os.environ.get("VERA_CONSTRUCTIONS_OFF")

    def trace(frame, event, arg):
        nonlocal last_result
        if (frame.f_code.co_filename != path or frame.f_code.co_name != "wdw"
                or event != "line"):
            return trace
        row = frame.f_locals.get("r")
        result = frame.f_locals.get("res")
        if (not isinstance(row, dict) or not isinstance(result, dict)
                or result is last_result):
            return trace
        last_result = result
        if (row.get("phenomenon") == "受け身" and row.get("split") == "train"
                and str(result.get("verdict", "")).startswith("UNKNOWN")):
            rows.append((row.get("sentence", ""), row.get("question", ""),
                         result.get("verdict", "UNKNOWN"),
                         result.get("reason", "unspecified")))
        return trace

    try:
        os.environ["VERA_CONSTRUCTIONS_OFF"] = "gold_passive"
        sys.argv = [path, "wdw", "--phenomenon", "受け身", "--n", "150",
                    "--seed", str(seed), "--json", str(output)]
        sys.settrace(trace)
        with redirect_stdout(StringIO()):
            runpy.run_path(path, run_name="__main__")
    finally:
        sys.settrace(None)
        sys.argv = old_argv
        if old_off is None:
            os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
        else:
            os.environ["VERA_CONSTRUCTIONS_OFF"] = old_off
    reasons = Counter((verdict, reason) for _, _, verdict, reason in rows)
    print(f"gold 受け身 abstain reasons seed {seed}: {dict(reasons)}")
    examples = {}
    for sentence, question, verdict, reason in rows:
        examples.setdefault((verdict, reason), (sentence, question))
    for (verdict, reason), (sentence, question) in sorted(examples.items()):
        print(f"  {verdict} / {reason}: {sentence} :: {question}")


def _constructed_diagnosis() -> None:
    from verantyx.semantic_reader import document_view
    from verantyx.semantic_verify import license_clause

    # This source and its expected role values are authored here as a small,
    # independent example; no probe-corpus sentence is embedded in the script.
    sentence = "乾いた砂に覆われた丘。"
    expected_agent, expected_patient = "乾いた砂", "丘"
    previous = os.environ.get("VERA_CONSTRUCTIONS_OFF")
    try:
        os.environ["VERA_CONSTRUCTIONS_OFF"] = "gold_passive"
        before = document_view({"passive-demo": sentence})
        reasons = sorted({reason for clause in before.clauses for reason in clause.unsupported}
                         | {item.reason for item in before.unread})
        print("constructed passive diagnosis: " +
              (", ".join(reasons) if reasons else "no typed refusal on the source sentence"))

        os.environ["VERA_CONSTRUCTIONS_OFF"] = ""
        after = document_view({"passive-demo": sentence})
        clause = next((item for item in after.clauses if item.rule == "gold_passive"), None)
        assert clause is not None
        assert {role.name: role.term for role in clause.roles}["agent"] == expected_agent
        assert {role.name: role.term for role in clause.roles}["patient"] == expected_patient
        license_clause(clause, after)
    finally:
        if previous is None:
            os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
        else:
            os.environ["VERA_CONSTRUCTIONS_OFF"] = previous


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="vera-passive-diagnosis-") as directory:
        _diagnose_gold_abstains(7, Path(directory) / "diagnosis.json")
    _constructed_diagnosis()
    with tempfile.TemporaryDirectory(prefix="vera-gold-passive-") as directory:
        temp = Path(directory)
        for seed in (7, 101):
            off = _probe(seed, True, temp / f"seed-{seed}-off.json")
            on = _probe(seed, False, temp / f"seed-{seed}-on.json")
            print(f"seed {seed} off {off}")
            print(f"seed {seed} on  {on}")
            assert on["correct"] > off["correct"]
            assert on["wrong_other"] <= off["wrong_other"]
            assert on["wrong_overlap"] <= off["wrong_overlap"]

        coverage_off = _coverage(True, temp / "coverage-off.json")
        coverage_on = _coverage(False, temp / "coverage-on.json")
        print(f"supported_sentences off={coverage_off} on={coverage_on}")
        assert coverage_on >= coverage_off
    print("DEMO OK")


if __name__ == "__main__":
    main()
