#!/usr/bin/env python3
"""Measure and precision-audit the paren_gloss construction on train leads."""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tools")

import round5a_route_tune as T
from verantyx.semantic_ir import data
from verantyx.semantic_reader import document_view
from verantyx import semantic_realize, semantic_verify


N = 1500
STRIDE = 200
RULE = "paren_gloss"


def _off_setting(value: str, disabled: bool) -> str:
    parts = [part.strip() for part in value.split(",") if part.strip()]
    if disabled and RULE not in parts:
        parts.append(RULE)
    elif not disabled:
        parts = [part for part in parts if part != RULE]
    return ",".join(parts)


def _view(docs: dict[str, str], disabled: bool, original: str) -> object:
    setting = _off_setting(original, disabled)
    if setting:
        os.environ["VERA_CONSTRUCTIONS_OFF"] = setting
    else:
        os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
    return document_view(docs)


def _supported(view: object) -> set[tuple[str, int]]:
    return {(clause.span.source, clause.span.start)
            for clause in view.clauses if not clause.unsupported}


def _sentences(docs: dict[str, str]) -> int:
    return sum(len([part for part in re.split(r"(?<=。)", text) if part.strip()])
               for text in docs.values())


def main() -> None:
    if os.environ.get("VERA_LEADS"):
        T.PATH = os.environ["VERA_LEADS"]
    docs = T.load(N, STRIDE)
    original = os.environ.get("VERA_CONSTRUCTIONS_OFF", "")
    try:
        disabled_view = _view(docs, True, original)
        enabled_view = _view(docs, False, original)
    finally:
        if original:
            os.environ["VERA_CONSTRUCTIONS_OFF"] = original
        else:
            os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)

    before = _supported(disabled_view)
    after = _supported(enabled_view)
    newly_supported = after - before
    total_sentences = _sentences(docs)
    print(f"supported sentences: disabled={len(before)}, enabled={len(after)}, sample={total_sentences}")
    print(f"newly supported sentences: {len(newly_supported)}")

    rule_sentences = {(c.span.source, c.span.start)
                      for c in enabled_view.clauses
                      if c.rule == RULE and not c.unsupported}
    candidates = sorted(newly_supported & rule_sentences)
    assert len(candidates) >= 60, f"expected 60 newly supported sentences, got {len(candidates)}"
    sample = [candidates[(i * len(candidates)) // 60] for i in range(60)]
    selected = set(sample)
    clauses_by_sentence: dict[tuple[str, int], list] = {}
    for clause in enabled_view.clauses:
        key = (clause.span.source, clause.span.start)
        if key in selected and clause.rule == RULE:
            clauses_by_sentence.setdefault(key, []).append(clause)

    checked = 0
    licensed = 0
    roundtrips = 0
    realizable = 0
    for key in sample:
        clauses = clauses_by_sentence.get(key, [])
        assert clauses, f"no {RULE} clause for newly supported sentence {key}"
        for clause in clauses:
            checked += 1
            try:
                result = semantic_verify.license_clause(clause, enabled_view)
                if result is None or result is True:
                    licensed += 1
            except Exception:
                pass
            realization = semantic_realize.realize_clause(clause)
            text = getattr(realization, "text", None)
            if isinstance(text, str) and text:
                realizable += 1
                check = semantic_realize.check_round_trip(clause, text)
                if check.get("passed") is True:
                    roundtrips += 1

    license_pct = 100.0 * licensed / checked if checked else 0.0
    roundtrip_pct = 100.0 * roundtrips / realizable if realizable else None
    print(f"checker licensed: {licensed}/{checked} ({license_pct:.1f}%)")
    if roundtrip_pct is None:
        print("realize round trip: N/A (the closed realizer refused all audited construction clauses)")
    else:
        print(f"realize round trip: {roundtrips}/{realizable} realizable clauses ({roundtrip_pct:.1f}%)")

    print("precision examples:")
    for number, key in enumerate(sample[:15], 1):
        source_name, start = key
        source = enabled_view.sources[source_name]
        sentence_clause = clauses_by_sentence[key][0]
        sentence = source[sentence_clause.span.start:sentence_clause.span.end]
        print(f"EXAMPLE {number}: {sentence}")
        for clause in clauses_by_sentence[key]:
            print("  " + json.dumps(data(clause), ensure_ascii=False, sort_keys=True))

    assert len(after) >= len(before), "enabled coverage fell below disabled coverage"
    assert len(newly_supported) >= 10, "fewer than 10 newly supported sentences"
    assert checked > 0 and licensed == checked, "checker did not license every audited clause"
    assert realizable == 0 or roundtrips / realizable >= 0.95, "round-trip agreement below 95%"
    print("DEMO OK")


if __name__ == "__main__":
    main()
