#!/usr/bin/env python3
"""Gold and train-lead gate for the comparison construction."""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
GOLD_PROBE = Path("phase2/gold_probe.py")
sys.path.insert(0, str(ROOT))


def _env(enabled: bool) -> dict[str, str]:
    env = os.environ.copy()
    env["VERA_CORPUS_ROOT"] = "/tmp/vera-empty-materials"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = "." + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    if enabled:
        env.pop("VERA_CONSTRUCTIONS_OFF", None)
    else:
        env["VERA_CONSTRUCTIONS_OFF"] = "comparison"
    return env


def _run(label: str, args: list[str], enabled: bool, deadline: float) -> str:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError("comparison demo exceeded its 55 second budget")
    result = subprocess.run(args, cwd=ROOT, env=_env(enabled), capture_output=True,
                           text=True, timeout=remaining, check=False)
    if result.returncode:
        raise RuntimeError(f"{label} failed ({result.returncode})\n{result.stdout}\n{result.stderr}")
    print(f"[{label}]")
    print(result.stdout.rstrip())
    if result.stderr.strip():
        print(result.stderr.rstrip(), file=sys.stderr)
    return result.stdout


def _gold_counts(output: str) -> dict[str, int]:
    for line in output.splitlines():
        match = re.match(r"^比較\s+(\{.*\})\s*$", line)
        if match:
            counts = ast.literal_eval(match.group(1))
            if isinstance(counts, dict) and all(type(v) is int for v in counts.values()):
                return counts
    raise AssertionError("gold probe did not report the 比較 counts")


def _coverage(output: str) -> int:
    value = json.loads(output)
    count = value.get("supported_sentences")
    if type(count) is not int:
        raise AssertionError("read_coverage did not report supported_sentences")
    return count


def _checker_demo() -> tuple[int, int]:
    os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
    from verantyx.constructions import ConstructionContext, enabled
    from verantyx.semantic_ir import Span
    from verantyx.semantic_reader import document_view

    sentence = "花子は太郎より早く赤い箱を運んだ。"
    view = document_view({"comparison_demo": sentence})
    clauses = [clause for clause in view.clauses if clause.rule == "comparison"]
    construction = next((item for item in enabled() if item.name == "comparison"), None)
    if construction is None or not clauses:
        raise AssertionError("constructed comparison did not produce clauses")

    expected_event = any(
        clause.predicate == "運ぶ"
        and any(role.name == "agent" and role.term == "花子" for role in clause.roles)
        and any(role.name == "patient" and role.term == "赤い箱" for role in clause.roles)
        for clause in clauses
    )
    expected_relation = any(
        clause.predicate == "comparison"
        and any(role.name == "entity" and role.term == "花子" for role in clause.roles)
        and any(role.name == "standard" and role.term == "太郎" for role in clause.roles)
        and any(role.name == "dimension" and role.term == "time" for role in clause.roles)
        and any(role.name == "direction" and role.term == "earlier" for role in clause.roles)
        for clause in clauses
    )
    if not expected_event or not expected_relation:
        raise AssertionError("constructed input did not preserve its event and comparison gold")

    negative = "赤山は青山ほど背が高くない。"
    negative_view = document_view({"negative_demo": negative})
    negative_clauses = [c for c in negative_view.clauses if c.rule == "comparison"]
    if not any(any(r.name == "direction" and r.term == "less" for r in c.roles)
               and any(r.name == "standard" and r.term == "青山" for r in c.roles)
               for c in negative_clauses):
        raise AssertionError("constructed negative comparison did not preserve its direction")

    superlative = "赤山は青県で最も高い山である。"
    context = ConstructionContext(superlative, Span("superlative_demo", 0,
                                                     len(superlative), superlative),
                                  (), "superlative_demo", ())
    superlative_reading = construction.reads(context)
    superlative_clauses = superlative_reading.clauses if superlative_reading else ()
    if not any(any(r.name == "standard" and r.term == "山" for r in c.roles)
               and any(r.name == "scope" and r.term == "青県" for r in c.roles)
               and any(r.name == "direction" and r.term == "greatest" for r in c.roles)
               for c in superlative_clauses):
        raise AssertionError("constructed superlative did not preserve its set and direction")

    all_clauses = clauses + negative_clauses + list(superlative_clauses)
    sources = dict(view.sources)
    sources.update(negative_view.sources)
    sources["superlative_demo"] = superlative
    licensed = sum(
        not clause.unsupported
        and construction.licenses(clause, sources[clause.span.source])
        for clause in all_clauses
    )
    if licensed != len(all_clauses):
        raise AssertionError(f"checker licensed {licensed}/{len(all_clauses)} new clauses")
    return licensed, len(all_clauses)


def main() -> None:
    deadline = time.monotonic() + 55
    interpreter = sys.executable
    gold_args = [interpreter, "-B", str(GOLD_PROBE), "wdw", "--phenomenon", "比較", "--n", "150"]
    coverage_args = [interpreter, "-B", "tools/read_coverage.py", "--n", "1500", "--stride", "200"]

    gold_off = _gold_counts(_run("gold comparison off", gold_args, False, deadline))
    gold_on = _gold_counts(_run("gold comparison enabled", gold_args, True, deadline))
    coverage_off = _coverage(_run("coverage comparison off", coverage_args, False, deadline))
    coverage_on = _coverage(_run("coverage comparison enabled", coverage_args, True, deadline))
    licensed, new_clauses = _checker_demo()
    print(f"checker comparison clauses: {licensed}/{new_clauses}")

    assert gold_on.get("correct", 0) > gold_off.get("correct", 0), (gold_off, gold_on)
    assert gold_on.get("wrong_other", 0) <= gold_off.get("wrong_other", 0), (gold_off, gold_on)
    assert coverage_on >= coverage_off, (coverage_off, coverage_on)
    assert new_clauses > 0 and licensed == new_clauses, (licensed, new_clauses)
    if time.monotonic() > deadline:
        raise TimeoutError("comparison demo exceeded its 55 second budget")
    print("DEMO OK")


if __name__ == "__main__":
    main()
