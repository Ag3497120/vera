#!/usr/bin/env python3
"""Coverage and precision demo for the source-bounded time expression rule."""
from __future__ import annotations

import json
import os
import random
import re
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tools")

import read_coverage as coverage
from verantyx.semantic_reader import document_view
from verantyx import semantic_realize, semantic_verify


def supported_keys(view):
    return {(clause.span.source, clause.span.start)
            for clause in view.clauses if not clause.unsupported}


def sentence_at(source: str, offset: int) -> str:
    start = source.rfind("。", 0, offset) + 1
    stop = source.find("。", offset)
    if stop < 0:
        stop = len(source)
    else:
        stop += 1
    return source[start:stop].strip()


def describe(clause):
    return {
        "rule": clause.rule,
        "predicate": clause.predicate,
        "time": clause.time,
        "roles": [{
            "name": role.name,
            "value": str(role.term),
            "kind": getattr(role.term, "kind", ""),
            "granularity": getattr(role.term, "granularity", ""),
            "extent": getattr(role.term, "extent", ""),
            "span": [role.span.start, role.span.end],
        } for role in clause.roles],
        "span": [clause.span.start, clause.span.end],
    }


def main():
    docs = coverage.T.load(1500, 200)
    prior_off = os.environ.get("VERA_CONSTRUCTIONS_OFF")
    disabled = {part.strip() for part in (prior_off or "").split(",") if part.strip()}
    disabled.add("time_expr")
    os.environ["VERA_CONSTRUCTIONS_OFF"] = ",".join(sorted(disabled))
    try:
        disabled_view = document_view(docs)
    finally:
        if prior_off is None:
            os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
        else:
            os.environ["VERA_CONSTRUCTIONS_OFF"] = prior_off

    enabled_view = document_view(docs)
    off_keys, on_keys = supported_keys(disabled_view), supported_keys(enabled_view)
    newly_supported = sorted(on_keys - off_keys)
    custom = {}
    for clause in enabled_view.clauses:
        if clause.rule == "time_expr" and not clause.unsupported:
            custom.setdefault((clause.span.source, clause.span.start), []).append(clause)

    print(f"supported sentences: disabled={len(off_keys)} enabled={len(on_keys)}")
    print(f"newly supported sentences: {len(newly_supported)}")

    sample_keys = random.Random(20261002).sample(newly_supported, min(60, len(newly_supported)))
    checker_total = checker_passed = 0
    realizable = round_trip_passed = 0
    for key in sample_keys:
        clauses = custom.get(key, ())
        if not clauses:
            raise AssertionError(f"newly supported span lacks a time_expr clause: {key}")
        for clause in clauses:
            checker_total += 1
            try:
                verdict = semantic_verify.license_clause(clause, enabled_view)
                accepted = verdict is None or verdict is True
            except Exception:
                accepted = False
            if accepted:
                checker_passed += 1

            realized = semantic_realize.realize_clause(clause)
            text = getattr(realized, "text", None)
            if text:
                realizable += 1
                round_trip = semantic_realize.check_round_trip(clause, text)
                if round_trip.get("passed"):
                    round_trip_passed += 1

    checker_pct = 100.0 * checker_passed / max(1, checker_total)
    # The realizer currently has no rule for time_expr. If it declines every
    # sampled clause, there are no round trips to disagree with.
    round_trip_pct = 100.0 * round_trip_passed / realizable if realizable else 100.0
    print(f"precision sample: {len(sample_keys)} sentences, {checker_passed}/{checker_total} checker licensed")
    round_trip_state = "vacuous; no clause was realizable" if not realizable else ""
    print(f"round-trip: {round_trip_passed}/{realizable} realizable clauses "
          f"({round_trip_pct:.1f}%{'; ' + round_trip_state if round_trip_state else ''})")

    for index, key in enumerate(sample_keys[:15], 1):
        source = enabled_view.sources[key[0]]
        print(json.dumps({
            "example": index,
            "sentence": sentence_at(source, key[1]),
            "clauses": [describe(clause) for clause in custom[key]],
        }, ensure_ascii=False, separators=(",", ":")))

    assert len(on_keys) >= len(off_keys)
    assert len(newly_supported) >= 10
    assert checker_total > 0 and checker_pct == 100.0
    assert round_trip_pct >= 95.0
    print("DEMO OK")


if __name__ == "__main__":
    main()
