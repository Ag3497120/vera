#!/usr/bin/env python3
"""Gold and Wikipedia coverage demo for the negation construction."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = "/Users/motonisihikoudai/vera-wiring/env/bin/python"
GOLD_PROBE = "/Users/motonisihikoudai/vera-wiring/phase2/gold_probe.py"
PHENOMENA = ("否定", "二重否定")


def _environment(disabled: bool) -> dict[str, str]:
    env = os.environ.copy()
    env.update({
        "VERA_CORPUS_ROOT": "/tmp/vera-empty-materials",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": ".",
        "VERA_CONSTRUCTIONS_OFF": "negation" if disabled else "",
    })
    return env


def _gold(disabled: bool, output_dir: str) -> dict:
    target = Path(output_dir) / ("gold-off.json" if disabled else "gold-on.json")
    run = subprocess.run(
        [PYTHON, "-B", GOLD_PROBE, "wdw", "--phenomenon", "否定", "--n", "150",
         "--json", str(target)],
        cwd=ROOT, env=_environment(disabled), check=True, capture_output=True,
        text=True, timeout=25,
    )
    result = json.loads(target.read_text(encoding="utf-8"))
    by = result.get("by", {})
    if not all(name in by for name in PHENOMENA):
        raise AssertionError("gold probe omitted a target phenomenon: " + run.stdout[-500:])
    return {name: by[name] for name in PHENOMENA}


def _coverage_and_new_clauses():
    from tools import read_coverage

    n, stride = 1500, 200
    original_load = read_coverage.T.load
    original_view = read_coverage.document_view
    documents = original_load(n, stride)
    captured = []

    def cached_load(_n, _stride):
        return documents

    def capture_view(values):
        view = original_view(values)
        captured.append(view)
        return view

    read_coverage.T.load = cached_load
    read_coverage.document_view = capture_view
    try:
        os.environ["VERA_CONSTRUCTIONS_OFF"] = "negation"
        off = read_coverage.measure(n, stride)
        off_view = captured[-1]
        os.environ["VERA_CONSTRUCTIONS_OFF"] = ""
        on = read_coverage.measure(n, stride)
        on_view = captured[-1]
    finally:
        read_coverage.T.load = original_load
        read_coverage.document_view = original_view

    old_ids = {clause.id for clause in off_view.clauses}
    new = [clause for clause in on_view.clauses
           if clause.rule == "negation" and clause.id not in old_ids]
    from verantyx.semantic_verify import Rejected, license_clause

    licensed = 0
    for clause in new:
        try:
            license_clause(clause, on_view)
        except Rejected:
            continue
        licensed += 1
    return off, on, new, licensed


def _constructed_input_checks():
    from verantyx.semantic_reader import document_view
    from verantyx.semantic_verify import license_clause

    documents = {
        "negative": "花子は資料Aを渡さなかった。",
        "double": "花子は資料Aを渡さなくはない。",
        "multi": "花子は資料Aを集めたが、太郎は資料Bを運ばなかった。",
        "positive": "花子は資料Aを渡した。",
    }
    os.environ["VERA_CONSTRUCTIONS_OFF"] = ""
    view = document_view(documents)
    ordinary = next(c for c in view.clauses if c.span.source == "negative" and c.predicate == "渡す")
    assert ordinary.polarity == "-"
    assert {role.name: role.term for role in ordinary.roles} == {"agent": "花子", "patient": "資料A"}
    license_clause(ordinary, view)

    double = next(c for c in view.clauses if c.span.source == "double" and c.rule == "negation")
    assert double.predicate == "渡す"
    assert double.polarity == "+"
    assert double.modality == "affirmative_by_double_negation"
    assert {role.name: role.term for role in double.roles} == {"agent": "花子", "patient": "資料A"}
    license_clause(double, view)

    multi = next(c for c in view.clauses if c.span.source == "multi" and c.rule == "negation")
    assert multi.predicate == "運ぶ"
    assert multi.polarity == "-"
    assert {role.name: role.term for role in multi.roles} == {"agent": "太郎", "patient": "資料B"}
    license_clause(multi, view)

    positive = next(c for c in view.clauses if c.span.source == "positive" and c.predicate == "渡す")
    assert positive.polarity == "+"
    assert positive.rule != "negation"
    return 2


def main() -> None:
    os.environ["VERA_CORPUS_ROOT"] = "/tmp/vera-empty-materials"
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ["PYTHONPATH"] = "."
    with tempfile.TemporaryDirectory(prefix="cov-negation-") as temp:
        gold_off = _gold(True, temp)
        gold_on = _gold(False, temp)

    sample_licensed = _constructed_input_checks()
    correct_off = sum(gold_off[name].get("correct", 0) for name in PHENOMENA)
    correct_on = sum(gold_on[name].get("correct", 0) for name in PHENOMENA)
    wrong_off = sum(gold_off[name].get("wrong_other", 0) for name in PHENOMENA)
    wrong_on = sum(gold_on[name].get("wrong_other", 0) for name in PHENOMENA)
    coverage_off, coverage_on, new_clauses, licensed = _coverage_and_new_clauses()
    print("GOLD off:", json.dumps(gold_off, ensure_ascii=False, sort_keys=True))
    print("GOLD on: ", json.dumps(gold_on, ensure_ascii=False, sort_keys=True))
    print("COVERAGE off:", json.dumps(coverage_off, ensure_ascii=False, sort_keys=True))
    print("COVERAGE on: ", json.dumps(coverage_on, ensure_ascii=False, sort_keys=True))
    print("CHECKER licenses", licensed, "/", len(new_clauses),
          "new train-lead clauses and", sample_licensed, "/", sample_licensed,
          "constructed-input clauses")

    assert correct_on > correct_off, (gold_off, gold_on)
    assert wrong_on <= wrong_off, (gold_off, gold_on)
    assert coverage_on["supported_sentences"] >= coverage_off["supported_sentences"]
    assert licensed == len(new_clauses)
    print("GOLD totals: correct", correct_off, "->", correct_on,
          "wrong_other", wrong_off, "->", wrong_on)
    print("DEMO OK")


if __name__ == "__main__":
    main()
