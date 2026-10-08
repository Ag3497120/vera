#!/usr/bin/env python3
"""Gold and Wikipedia coverage demo for the giving construction."""
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
PYTHON = "python"
GOLD_PROBE = "phase2/gold_probe.py"
START = time.monotonic()
DEMO_LIMIT = 58.0


def fail(message: str) -> None:
    raise SystemExit("DEMO FAIL: " + message)


def command_env(enabled: bool) -> dict[str, str]:
    result = os.environ.copy()
    result["VERA_CORPUS_ROOT"] = "/tmp/vera-empty-materials"
    result["PYTHONDONTWRITEBYTECODE"] = "1"
    result["PYTHONPATH"] = "."
    if enabled:
        result.pop("VERA_CONSTRUCTIONS_OFF", None)
    else:
        result["VERA_CONSTRUCTIONS_OFF"] = "giving"
    return result


def run_gold(enabled: bool) -> dict[str, int]:
    remaining = DEMO_LIMIT - (time.monotonic() - START)
    if remaining <= 1:
        fail("time budget exhausted before gold probe")
    result = subprocess.run(
        [PYTHON, "-B", GOLD_PROBE, "wdw", "--phenomenon", "授受", "--n", "150"],
        cwd=ROOT,
        env=command_env(enabled),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=remaining,
        check=False,
    )
    if result.returncode:
        fail("gold probe failed: " + result.stderr[-1000:])
    total_match = next((re.search(r"TOTAL\s+(\{.*?\})", line)
                        for line in result.stdout.splitlines() if line.startswith("TOTAL ")), None)
    if total_match is None:
        fail("gold probe did not report totals")
    try:
        return ast.literal_eval(total_match.group(1))
    except (ValueError, SyntaxError):
        fail("gold probe totals were not parseable")


def coverage(view, documents) -> dict[str, int]:
    supported = {(c.span.source, c.span.start) for c in view.clauses if not c.unsupported}
    sentences = sum(len([s for s in re.split(r"(?<=。)", text) if s.strip()])
                    for text in documents.values())
    return {"supported_sentences": len(supported), "sentences_approx": sentences}


def synthetic_licenses() -> tuple[int, int]:
    from verantyx.constructions import ConstructionContext
    from verantyx.constructions.giving import licenses, reads
    from verantyx.semantic_ir import Clause, Span, Variable

    cases = (
        ("太郎は花子に本をあげた。", {"agent": "太郎", "patient": "本", "recipient": "花子"}),
        ("花子は太郎から本をもらった。", {"agent": "太郎", "patient": "本", "recipient": "花子"}),
        ("太郎は花子に本をくれた。", {"agent": "太郎", "patient": "本", "recipient": "花子"}),
        ("花子は太郎から本をいただきました。", {"agent": "太郎", "patient": "本", "recipient": "花子"}),
        ("太郎は花子に本をさしあげました。", {"agent": "太郎", "patient": "本", "recipient": "花子"}),
    )
    licensed = 0
    for index, (sentence, expected) in enumerate(cases):
        source = "demo_" + str(index)
        span = Span(source, 0, len(sentence), sentence)
        context = ConstructionContext(sentence, span, (), source, ())
        reading = reads(context)
        if reading is None or len(reading.clauses) != 1:
            fail("constructed direct giving example did not produce one clause")
        clause = reading.clauses[0]
        actual = {role.name: role.term for role in clause.roles}
        if actual != expected:
            fail("constructed role gold mismatch: " + repr((sentence, actual, expected)))
        if not licenses(clause, sentence):
            fail("independent checker rejected a constructed giving clause")
        licensed += 1
    sentence = "太郎は花子に本を渡してあげた。"
    source = "demo_te_form"
    sentence_span = Span(source, 0, len(sentence), sentence)
    predicate_start = sentence.index("渡し")
    native = Clause(
        id="native_demo",
        event=Variable("event_native_demo", "event"),
        predicate="渡す",
        predicate_span=Span(source, predicate_start, predicate_start + 2, "渡し"),
        roles=(),
        span=sentence_span,
        body_span=sentence_span,
        time="past",
        rule="frame",
        unsupported=("synthetic native ambiguity",),
    )
    context = ConstructionContext(sentence, sentence_span, (), source, (native,))
    reading = reads(context)
    expected = {"agent": "太郎", "patient": "本", "recipient": "花子"}
    if reading is None or len(reading.clauses) != 1:
        fail("constructed te-form did not produce one clause")
    clause = reading.clauses[0]
    actual = {role.name: role.term for role in clause.roles}
    if actual != expected or not licenses(clause, sentence):
        fail("constructed te-form failed role or licensing check")
    licensed += 1
    return licensed, len(cases) + 1


def main() -> None:
    sys.path.insert(0, str(ROOT))
    from verantyx.semantic_reader import document_view
    from tools import read_coverage

    gold_off = run_gold(False)
    gold_on = run_gold(True)
    print("gold off", json.dumps(gold_off, ensure_ascii=False, sort_keys=True))
    print("gold enabled", json.dumps(gold_on, ensure_ascii=False, sort_keys=True))
    if gold_on.get("correct", 0) <= gold_off.get("correct", 0):
        fail("gold correct did not rise")
    if gold_on.get("wrong_other", 0) > gold_off.get("wrong_other", 0):
        fail("gold wrong_other rose")

    remaining = DEMO_LIMIT - (time.monotonic() - START)
    if remaining <= 1:
        fail("time budget exhausted before Wikipedia coverage")
    documents = read_coverage.T.load(1500, 200)
    os.environ["VERA_CONSTRUCTIONS_OFF"] = "giving"
    off_view = document_view(documents)
    off_coverage = coverage(off_view, documents)
    os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
    on_view = document_view(documents)
    on_coverage = coverage(on_view, documents)
    print("Wikipedia coverage", json.dumps({"off": off_coverage, "enabled": on_coverage},
                                             ensure_ascii=False, sort_keys=True))
    if on_coverage["supported_sentences"] < off_coverage["supported_sentences"]:
        fail("Wikipedia supported_sentences fell")

    disabled_ids = {c.id for c in off_view.clauses}
    new_clauses = [c for c in on_view.clauses if c.rule == "giving" and c.id not in disabled_ids]
    from verantyx.constructions.giving import licenses
    corpus_licensed = 0
    for clause in new_clauses:
        source = documents.get(clause.span.source)
        if source is not None and licenses(clause, source):
            corpus_licensed += 1
    demo_licensed, demo_total = synthetic_licenses()
    total = len(new_clauses) + demo_total
    passed = corpus_licensed + demo_licensed
    print("checker licensed", f"{passed}/{total}",
          f"(Wikipedia {corpus_licensed}/{len(new_clauses)}; constructed {demo_licensed}/{demo_total})")
    if corpus_licensed != len(new_clauses) or demo_licensed != demo_total:
        fail("independent checker did not license every new clause")
    print("DEMO OK")


if __name__ == "__main__":
    main()
