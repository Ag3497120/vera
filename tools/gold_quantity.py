"""Gold-probe and structural demo for the quantity source construction."""
from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
from collections import Counter


ROOT = os.getcwd()
PYTHON = sys.executable
PROBE = "/Users/motonisihikoudai/vera-wiring/phase2/gold_probe.py"
RULE = "gold_quantity"
PHENOMENON = "数量"


def _env(enabled: bool) -> dict[str, str]:
    env = os.environ.copy()
    env["VERA_CORPUS_ROOT"] = "/tmp/vera-empty-materials"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = "."
    disabled = {part.strip() for part in env.get("VERA_CONSTRUCTIONS_OFF", "").split(",")
                if part.strip()}
    if enabled:
        disabled.discard(RULE)
    else:
        disabled.add(RULE)
    if disabled:
        env["VERA_CONSTRUCTIONS_OFF"] = ",".join(sorted(disabled))
    else:
        env.pop("VERA_CONSTRUCTIONS_OFF", None)
    return env


def _probe(seed: int, enabled: bool) -> Counter[str]:
    completed = subprocess.run(
        [PYTHON, "-B", PROBE, "wdw", "--phenomenon", PHENOMENON,
         "--n", "150", "--seed", str(seed)],
        cwd=ROOT, env=_env(enabled), text=True, capture_output=True, check=True,
        timeout=30,
    )
    for line in completed.stdout.splitlines():
        match = re.search(r"\{[^{}]*\}", line)
        if line.strip().startswith(PHENOMENON) and match:
            values = ast.literal_eval(match.group(0))
            return Counter({str(key): int(value) for key, value in values.items()})
    raise RuntimeError("gold probe did not report the quantity row")


def _coverage(enabled: bool) -> int:
    completed = subprocess.run(
        [PYTHON, "-B", "tools/read_coverage.py", "--n", "1500", "--stride", "200"],
        cwd=ROOT, env=_env(enabled), text=True, capture_output=True, check=True,
        timeout=30,
    )
    result = json.loads(completed.stdout)
    return int(result["supported_sentences"])


def _show(seed: int, state: str, counts: Counter[str]) -> None:
    overlap = counts["wrong_overlap"]
    other = counts["wrong_other"]
    print(f"seed={seed} {state}: correct={counts['correct']} wrong={overlap + other} "
          f"wrong_overlap={overlap} wrong_other={other} abstain={counts['abstain']}")


def _diagnose_constructed_input() -> dict:
    from verantyx.one import Vera

    source = "りんごを三個買った。"
    question = "何を買った？"
    expected = ("りんご",)
    previous = os.environ.get("VERA_CONSTRUCTIONS_OFF")
    disabled = {part.strip() for part in (previous or "").split(",") if part.strip()}
    disabled.add(RULE)
    os.environ["VERA_CONSTRUCTIONS_OFF"] = ",".join(sorted(disabled))
    try:
        refused = Vera.from_texts({"quantity_demo": source}, mode="semantic")
        try:
            baseline = refused.ask(question)
        finally:
            refused.close()
    finally:
        if previous is None:
            os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
        else:
            os.environ["VERA_CONSTRUCTIONS_OFF"] = previous

    if baseline.get("kind") != "unknown":
        raise AssertionError("constructed baseline was expected to abstain")
    reason = str(baseline.get("reason", "unknown abstention"))
    assert reason == "unrepresented source content", reason
    print(f"diagnosis constructed quantity input: abstain_reason={reason}")

    answered = Vera.from_texts({"quantity_demo": source}, mode="semantic")
    try:
        result = answered.ask(question)
    finally:
        answered.close()
    assert result.get("verdict") == "ANSWER", result
    assert tuple(result.get("values", ())) == expected, result
    return result


def main() -> None:
    before: dict[int, Counter[str]] = {}
    after: dict[int, Counter[str]] = {}
    for seed in (7, 101):
        before[seed] = _probe(seed, enabled=False)
        after[seed] = _probe(seed, enabled=True)
        _show(seed, "off", before[seed])
        _show(seed, "on", after[seed])
        assert after[seed]["correct"] > before[seed]["correct"], seed
        assert after[seed]["wrong_other"] <= before[seed]["wrong_other"], seed
        assert after[seed]["wrong_overlap"] <= before[seed]["wrong_overlap"], seed

    coverage_off = _coverage(enabled=False)
    coverage_on = _coverage(enabled=True)
    print(f"supported_sentences off={coverage_off} on={coverage_on}")
    assert coverage_on >= coverage_off

    _diagnose_constructed_input()
    print("DEMO OK")


if __name__ == "__main__":
    main()
