#!/usr/bin/env python3
"""Measure the double-negative reader against train gold and train leads."""
from __future__ import annotations

from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import random
import subprocess
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
PYTHON = "/Users/motonisihikoudai/vera-wiring/env/bin/python"
GOLD_PROBE = "/Users/motonisihikoudai/vera-wiring/phase2/gold_probe.py"
RULE = "gold_double_neg"
PHENOMENON = "二重否定"
METRICS = ("correct", "wrong_other", "wrong_overlap", "abstain")


def _environment(disabled: bool) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "VERA_CORPUS_ROOT": "/tmp/vera-empty-materials",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": ".",
        "VERA_CONSTRUCTIONS_OFF": RULE if disabled else "",
    })
    return env


def _gold(disabled: bool, seed: int, output_dir: str) -> dict[str, int]:
    target = Path(output_dir) / f"gold-{seed}-{'off' if disabled else 'on'}.json"
    run = subprocess.run(
        [PYTHON, "-B", GOLD_PROBE, "wdw", "--phenomenon", PHENOMENON,
         "--n", "150", "--seed", str(seed), "--json", str(target)],
        cwd=ROOT, env=_environment(disabled), check=True, capture_output=True,
        text=True, timeout=20,
    )
    result = json.loads(target.read_text(encoding="utf-8"))
    by = result.get("by", {})
    if PHENOMENON not in by:
        raise AssertionError("gold probe omitted the target phenomenon: " + run.stdout[-500:])
    return {name: int(by[PHENOMENON].get(name, 0)) for name in METRICS}


def _diagnose_train(seed: int = 7, limit: int = 150) -> dict[str, int]:
    """Count baseline source-reading refusals on sampled train WDW gold items."""
    corpus = Path(os.environ.get("VERA_CORPUS_DIR", Path.home() / "vera-codex-corpus"))
    train_file = corpus / "paraphrase_entail" / "train" / "records.jsonl"
    if not train_file.is_file() or train_file.is_symlink():
        raise FileNotFoundError("train gold records are unavailable at " + str(train_file))

    examples = []
    with train_file.open("r", encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if (item.get("split") == "train" and item.get("kind") == "who_did_what"
                    and item.get("phenomenon") == PHENOMENON
                    and isinstance(item.get("sentence"), str)):
                examples.append(item["sentence"])
    if not examples:
        raise AssertionError("no train WDW items found for " + PHENOMENON)
    selected = random.Random(seed).sample(examples, min(limit, len(examples)))

    from verantyx.semantic_reader import document_view

    was_set = "VERA_CONSTRUCTIONS_OFF" in os.environ
    prior = os.environ.get("VERA_CONSTRUCTIONS_OFF", "")
    os.environ["VERA_CONSTRUCTIONS_OFF"] = RULE
    try:
        sources = {f"gold-diagnosis-{seed}-{index}": sentence
                   for index, sentence in enumerate(selected)}
        view = document_view(sources)
    finally:
        if was_set:
            os.environ["VERA_CONSTRUCTIONS_OFF"] = prior
        else:
            os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)

    reasons = defaultdict(set)
    for item in view.unread:
        reasons[item.span.source].add(item.reason)
    for clause in view.clauses:
        for reason in clause.unsupported:
            reasons[clause.span.source].add(reason)
    counts = Counter(reason for values in reasons.values() for reason in values)
    print(f"ABSTAIN REASONS (train WDW {PHENOMENON}, seed={seed}, items={len(selected)}):")
    if not counts:
        print("  no source-reading refusals in this diagnosis sample")
    else:
        for reason, count in counts.most_common(10):
            print(f"  {reason}: {count}")
    return dict(counts)


def _coverage() -> tuple[dict, dict]:
    from tools import read_coverage

    n, stride = 1500, 200
    original_load = read_coverage.T.load
    documents = original_load(n, stride)
    read_coverage.T.load = lambda _n, _stride: documents
    had_disabled = "VERA_CONSTRUCTIONS_OFF" in os.environ
    previous_disabled = os.environ.get("VERA_CONSTRUCTIONS_OFF", "")
    try:
        os.environ["VERA_CONSTRUCTIONS_OFF"] = RULE
        off = read_coverage.measure(n, stride)
        os.environ["VERA_CONSTRUCTIONS_OFF"] = ""
        on = read_coverage.measure(n, stride)
    finally:
        read_coverage.T.load = original_load
        if had_disabled:
            os.environ["VERA_CONSTRUCTIONS_OFF"] = previous_disabled
        else:
            os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
    return off, on


def _constructed_checks() -> int:
    from dataclasses import replace
    from verantyx.constructions.gold_double_neg import licenses
    from verantyx.semantic_reader import document_view
    from verantyx.semantic_verify import license_clause

    os.environ["VERA_CONSTRUCTIONS_OFF"] = ""
    view = document_view({
        "double": "花子は資料Aを渡さなくない。",
        "past_double": "花子は資料Aを渡さないことはなかった。",
        "ordinary_negative": "花子は資料Aを渡さない。",
    })
    clause = next(item for item in view.clauses
                  if item.span.source == "double" and item.rule == RULE)
    assert (clause.predicate, clause.polarity, clause.modality, clause.time) == (
        "渡す", "+", "assert", "nonpast")
    assert {role.name: role.term for role in clause.roles} == {
        "agent": "花子", "patient": "資料A"}
    license_clause(clause, view)
    assert licenses(clause, view.sources["double"])
    assert not licenses(replace(clause, polarity="-"), view.sources["double"])

    past = next(item for item in view.clauses
                if item.span.source == "past_double" and item.rule == RULE)
    assert (past.predicate, past.polarity, past.modality, past.time) == (
        "渡す", "+", "assert", "past")
    assert {role.name: role.term for role in past.roles} == {
        "agent": "花子", "patient": "資料A"}
    license_clause(past, view)

    negative = next(item for item in view.clauses
                    if item.span.source == "ordinary_negative" and item.predicate == "渡す")
    assert negative.polarity == "-" and negative.rule != RULE
    license_clause(negative, view)
    return 3


def main() -> None:
    os.environ["VERA_CORPUS_ROOT"] = "/tmp/vera-empty-materials"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["PYTHONPATH"] = "."
    started = time.monotonic()
    _diagnose_train()
    with tempfile.TemporaryDirectory(prefix="gold-double-neg-") as temp:
        for seed in (7, 101):
            off = _gold(True, seed, temp)
            on = _gold(False, seed, temp)
            print(f"GOLD seed={seed} off={off} on={on}")
            assert on["correct"] > off["correct"], (seed, off, on)
            for metric in ("wrong_other", "wrong_overlap"):
                assert on[metric] <= off[metric], (seed, metric, off, on)

    coverage_off, coverage_on = _coverage()
    old_supported = coverage_off["supported_sentences"]
    new_supported = coverage_on["supported_sentences"]
    print(f"COVERAGE supported_sentences: {old_supported} -> {new_supported}")
    assert new_supported >= old_supported, (coverage_off, coverage_on)

    constructed = _constructed_checks()
    print(f"CHECKER licenses {constructed}/{constructed} constructed clauses")
    assert time.monotonic() - started < 60, "demo exceeded 60 seconds"
    print("DEMO OK")


if __name__ == "__main__":
    main()
