#!/usr/bin/env python3
"""Offline diagnostic and acceptance demo for gold_caus_pass."""
from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = "/Users/motonisihikoudai/vera-wiring/env/bin/python"
GOLD_PROBE = "/Users/motonisihikoudai/vera-wiring/phase2/gold_probe.py"
RULE = "gold_caus_pass"
DIAGNOSIS_INPUTS = (
    "太郎は花子に濡れた野菜を食べさせられた。",
    "太郎は店員に濡れた布を棚の横に並べさせられた。",
    "僕は先輩に駅まで走らされた。",
)
AUTHORED_GOLD = (
    ("太郎は花子に濡れた野菜を食べさせられた。", "食べさせる",
     (("causee", "太郎"), ("agent", "花子に"), ("patient", "野菜"))),
    ("太郎は店員に濡れた布を棚の横に並べさせられた。", "並べさせる",
     (("causee", "太郎"), ("agent", "店員に"), ("patient", "布"), ("location", "棚の横"))),
    ("先生に濡れた作文を書かされた。", "書かす",
     (("agent", "先生に"), ("patient", "作文"))),
)


def _rule_env(disabled: bool) -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("VERA_CORPUS_ROOT", "/tmp/vera-empty-materials")
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = "."
    prior = [part.strip() for part in env.get("VERA_CONSTRUCTIONS_OFF", "").split(",")
             if part.strip() and part.strip() != RULE]
    if disabled:
        prior.append(RULE)
    if prior:
        env["VERA_CONSTRUCTIONS_OFF"] = ",".join(dict.fromkeys(prior))
    else:
        env.pop("VERA_CONSTRUCTIONS_OFF", None)
    return env


def _run(command: list[str], env: dict[str, str], deadline: float) -> str:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise RuntimeError("demo exceeded its 60 second budget")
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, text=True,
                            timeout=min(remaining, 35), check=False)
    if result.returncode:
        raise RuntimeError("command failed: " + " ".join(command) + "\n" + result.stderr[-2000:])
    return result.stdout


def _probe(seed: int, disabled: bool, deadline: float) -> dict[str, int]:
    output = _run([PYTHON, "-B", GOLD_PROBE, "wdw", "--phenomenon", "使役受け身",
                   "--n", "150", "--seed", str(seed)], _rule_env(disabled), deadline)
    match = re.search(r"(?m)^TOTAL (\{[^\n]*\}) seconds", output)
    if match is None:
        raise RuntimeError("gold probe did not print its aggregate TOTAL row")
    parsed = ast.literal_eval(match.group(1))
    return {key: int(parsed.get(key, 0)) for key in
            ("correct", "wrong_other", "wrong_overlap", "abstain")}


def _coverage(disabled: bool, deadline: float) -> int:
    output = _run([PYTHON, "-B", "tools/read_coverage.py"], _rule_env(disabled), deadline)
    try:
        import json
        result = json.loads(output)
        return int(result["supported_sentences"])
    except (ValueError, KeyError, TypeError) as exc:
        raise RuntimeError("read_coverage.py did not report supported_sentences") from exc


def _diagnosis() -> None:
    """Print native refusal reasons for small authored causative-passive witnesses."""
    from verantyx.semantic_reader import document_view

    env_name = "VERA_CONSTRUCTIONS_OFF"
    old = os.environ.get(env_name)
    off = [part.strip() for part in (old or "").split(",") if part.strip()]
    for name in (RULE, "diathesis"):
        if name not in off:
            off.append(name)
    os.environ[env_name] = ",".join(off)
    reasons: Counter[str] = Counter()
    try:
        for index, sentence in enumerate(DIAGNOSIS_INPUTS):
            view = document_view({"causpass_diagnosis_" + str(index): sentence})
            matched = [clause for clause in view.clauses
                       if "させられ" in clause.span.text or "され" in clause.span.text]
            for clause in matched:
                if clause.unsupported:
                    reasons.update(clause.unsupported)
                else:
                    reasons["native clause left unsupported by no direct reason"] += 1
    finally:
        if old is None:
            os.environ.pop(env_name, None)
        else:
            os.environ[env_name] = old
    print("authored causative-passive refusal reasons=" + repr(dict(sorted(reasons.items()))))


def _authored_gold() -> None:
    from dataclasses import replace

    from verantyx.constructions import gold_caus_pass
    from verantyx.semantic_reader import document_view
    from verantyx.semantic_verify import Rejected, license_clause

    env_name = "VERA_CONSTRUCTIONS_OFF"
    old = os.environ.get(env_name)
    off = [part.strip() for part in (old or "").split(",") if part.strip() and part.strip() != RULE]
    if off:
        os.environ[env_name] = ",".join(off)
    else:
        os.environ.pop(env_name, None)
    try:
        for index, (sentence, predicate, expected_roles) in enumerate(AUTHORED_GOLD):
            view = document_view({"causpass_gold_" + str(index): sentence})
            clauses = [clause for clause in view.clauses
                       if clause.rule == RULE and clause.predicate == predicate and not clause.unsupported]
            assert len(clauses) == 1, (predicate, [(c.rule, c.predicate, c.unsupported) for c in view.clauses])
            clause = clauses[0]
            actual = tuple((role.name, role.span.text) for role in clause.roles)
            assert actual == expected_roles, (actual, expected_roles)
            assert gold_caus_pass.licenses(clause, sentence)
            license_clause(clause, view)
            if clause.roles:
                changed = replace(clause, roles=(replace(clause.roles[0], name="patient"), *clause.roles[1:]))
                if changed.roles != clause.roles:
                    assert not gold_caus_pass.licenses(changed, sentence)
    finally:
        if old is None:
            os.environ.pop(env_name, None)
        else:
            os.environ[env_name] = old


def main() -> None:
    deadline = time.monotonic() + 55
    _diagnosis()
    _authored_gold()

    before = {}
    after = {}
    for seed in (7, 101):
        before[seed] = _probe(seed, True, deadline)
        after[seed] = _probe(seed, False, deadline)
        print("probe seed=%d off=%s on=%s" % (seed, before[seed], after[seed]))
        assert after[seed]["correct"] > before[seed]["correct"], (seed, before[seed], after[seed])
        assert after[seed]["wrong_other"] <= before[seed]["wrong_other"], (seed, before[seed], after[seed])
        assert after[seed]["wrong_overlap"] <= before[seed]["wrong_overlap"], (seed, before[seed], after[seed])

    coverage_before = _coverage(True, deadline)
    coverage_after = _coverage(False, deadline)
    print("supported_sentences off=%d on=%d" % (coverage_before, coverage_after))
    assert coverage_after >= coverage_before, (coverage_before, coverage_after)
    assert time.monotonic() < deadline, "demo exceeded its 60 second budget"
    print("DEMO OK")


if __name__ == "__main__":
    main()
