"""Gold-probe and reading-coverage gate for the temporal construction."""
from __future__ import annotations

import ast
import argparse
import contextlib
import json
import io
import os
import runpy
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = "/Users/motonisihikoudai/vera-wiring/env/bin/python"
GOLD_PROBE = "/Users/motonisihikoudai/vera-wiring/phase2/gold_probe.py"
PHENOMENON = "時間の順序"
RULE = "gold_temporal"
SEEDS = (7, 101)


def _env(disabled: bool) -> dict[str, str]:
    env = os.environ.copy()
    env["VERA_CORPUS_ROOT"] = "/tmp/vera-empty-materials"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(ROOT)
    names = {name.strip() for name in env.get("VERA_CONSTRUCTIONS_OFF", "").split(",")
             if name.strip()}
    if disabled:
        names.add(RULE)
    else:
        names.discard(RULE)
    if names:
        env["VERA_CONSTRUCTIONS_OFF"] = ",".join(sorted(names))
    else:
        env.pop("VERA_CONSTRUCTIONS_OFF", None)
    return env


def _run(command: list[str], env: dict[str, str]) -> str:
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                            text=True, timeout=55, check=False)
    if result.returncode:
        raise RuntimeError("command failed: " + Path(command[-1]).name)
    return result.stdout


def _probe(seed: int, disabled: bool, n: int = 150) -> dict[str, int]:
    output = _run([
        PYTHON, "-B", GOLD_PROBE, "wdw", "--phenomenon", PHENOMENON,
        "--n", str(n), "--seed", str(seed),
    ], _env(disabled))
    for line in output.splitlines():
        if line.startswith("TOTAL "):
            payload = line[len("TOTAL "):].rsplit(" seconds", 1)[0].strip()
            counts = ast.literal_eval(payload)
            return {key: int(counts.get(key, 0))
                    for key in ("correct", "wrong_other", "wrong_overlap", "abstain")}
    raise RuntimeError("gold probe did not report totals")


def _diagnose_abstentions() -> Counter[str]:
    reasons: Counter[str] = Counter()
    env = _env(disabled=True)
    prior = {key: os.environ.get(key) for key in
             ("VERA_CORPUS_ROOT", "PYTHONDONTWRITEBYTECODE", "PYTHONPATH", "VERA_CONSTRUCTIONS_OFF")}
    os.environ.update({key: env[key] for key in
                       ("VERA_CORPUS_ROOT", "PYTHONDONTWRITEBYTECODE", "PYTHONPATH")})
    os.environ["VERA_CONSTRUCTIONS_OFF"] = env["VERA_CONSTRUCTIONS_OFF"]
    import verantyx.one as one

    original = one.Vera

    class Observed:
        @classmethod
        def from_texts(cls, docs, **kwargs):
            return ObservedInstance(original.from_texts(docs, **kwargs))

    class ObservedInstance:
        def __init__(self, vera):
            self.vera = vera

        def ask(self, question, **kwargs):
            answer = self.vera.ask(question, **kwargs)
            if answer.get("kind") == "unknown":
                phase = str(answer.get("phase") or "unknown")
                reason = str(answer.get("reason") or answer.get("verdict") or "typed refusal")
                reasons[f"{phase}: {reason}"] += 1
            return answer

        def close(self):
            return self.vera.close()

    one.Vera = Observed
    try:
        probe = runpy.run_path(GOLD_PROBE, run_name="gold_temporal_probe")
        args = argparse.Namespace(n=150, seed=7, phenomenon=PHENOMENON, json=None)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            totals, _ = probe["wdw"](args)
        counts = next((value for key, value in totals.items()
                       if key.startswith(PHENOMENON)), {})
        if sum(reasons.values()) != int(counts.get("abstain", 0)):
            raise RuntimeError("gold abstention reasons did not match the sampled count")
    finally:
        one.Vera = original
        for key, value in prior.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    for reason, count in sorted(reasons.items()):
        print(f"ABSTAIN DIAG {reason} count={count}")
    if not reasons:
        raise RuntimeError("gold probe returned no typed abstention reasons")
    return reasons


def _coverage(disabled: bool) -> int:
    output = _run([PYTHON, "-B", "tools/read_coverage.py"], _env(disabled))
    try:
        result = json.loads(output)
    except json.JSONDecodeError as exc:
        raise RuntimeError("read_coverage.py did not return JSON") from exc
    return int(result["supported_sentences"])


def main() -> int:
    diagnosis = _diagnose_abstentions()
    before: dict[int, dict[str, int]] = {}
    after: dict[int, dict[str, int]] = {}
    for seed in SEEDS:
        before[seed] = _probe(seed, disabled=True)
        after[seed] = _probe(seed, disabled=False)
        for label, counts in (("off", before[seed]), ("on", after[seed])):
            print("GOLD", f"seed={seed}", f"rule={label}",
                  *(f"{key}={counts[key]}" for key in
                    ("correct", "wrong_other", "wrong_overlap", "abstain")))

    coverage_off = _coverage(disabled=True)
    coverage_on = _coverage(disabled=False)
    print(f"COVERAGE rule=off supported_sentences={coverage_off}")
    print(f"COVERAGE rule=on supported_sentences={coverage_on}")

    passed = bool(diagnosis)
    for seed in SEEDS:
        passed = passed and after[seed]["correct"] > before[seed]["correct"]
        passed = passed and after[seed]["wrong_other"] <= before[seed]["wrong_other"]
        passed = passed and after[seed]["wrong_overlap"] <= before[seed]["wrong_overlap"]
    passed = passed and coverage_on >= coverage_off
    if not passed:
        print("DEMO GATE FAILED", file=sys.stderr)
        return 1
    print("DEMO OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
