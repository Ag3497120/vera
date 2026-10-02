#!/usr/bin/env python3
"""Coverage and precision demo for the quantifier construction."""
from __future__ import annotations

import os
import random

import read_coverage as coverage
from verantyx.semantic_reader import document_view
from verantyx.semantic_realize import Refused, check_round_trip, realize_clause
from verantyx.semantic_verify import license_clause


N = 1500
STRIDE = 200
AUDIT_SIZE = 60
EXAMPLES = 15
SEED = 20261002


def _supported(view):
    return {(clause.span.source, clause.span.start)
            for clause in view.clauses if not clause.unsupported}


def _clauses_for(view, keys):
    wanted = set(keys)
    return tuple(clause for clause in view.clauses
                 if not clause.unsupported
                 and (clause.span.source, clause.span.start) in wanted)


def _summary_clause(clause):
    roles = ", ".join(f"{role.name}={role.term!s}" for role in clause.roles)
    return f"{clause.predicate}({roles}) [{clause.rule}]"


def main():
    docs = coverage.T.load(N, STRIDE)
    os.environ["VERA_CONSTRUCTIONS_OFF"] = "quantifier"
    disabled = document_view(docs)
    disabled_keys = _supported(disabled)

    os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
    enabled = document_view(docs)
    enabled_keys = _supported(enabled)
    new_keys = tuple(sorted(enabled_keys - disabled_keys))
    sample = random.Random(SEED).sample(new_keys, min(AUDIT_SIZE, len(new_keys)))
    audit_clauses = _clauses_for(enabled, sample)

    licensed = 0
    for clause in audit_clauses:
        result = license_clause(clause, enabled)
        assert result is None, (clause.span.text, clause.rule, result)
        licensed += 1

    realizable = 0
    round_trip_ok = 0
    for clause in audit_clauses:
        candidate = realize_clause(clause)
        if isinstance(candidate, Refused):
            continue
        realizable += 1
        check = check_round_trip(clause, candidate.text)
        assert isinstance(check, dict) and check.get("passed") is True, (
            clause.span.text, candidate.text, check)
        round_trip_ok += 1

    round_trip_rate = round_trip_ok / realizable if realizable else None
    print(f"supported disabled: {len(disabled_keys)}")
    print(f"supported enabled: {len(enabled_keys)}")
    print(f"newly supported sentences: {len(new_keys)}")
    print(f"audited sentences: {len(sample)}")
    print(f"licensed clauses: {licensed}/{len(audit_clauses)}")
    if round_trip_rate is None:
        print(f"realizable clauses round-trip: {round_trip_ok}/{realizable} (none realizable)")
    else:
        print(f"realizable clauses round-trip: {round_trip_ok}/{realizable} ({round_trip_rate:.1%})")

    assert len(enabled_keys) >= len(disabled_keys)
    assert len(new_keys) >= 10
    assert licensed == len(audit_clauses) and audit_clauses
    assert realizable == 0 or round_trip_rate >= 0.95
    assert len(sample) >= EXAMPLES

    print("precision examples:")
    for index, key in enumerate(sample[:EXAMPLES], 1):
        source, start = key
        clause_group = [clause for clause in audit_clauses
                        if (clause.span.source, clause.span.start) == key]
        sentence = clause_group[0].span.text
        print(f"{index:02d}. {sentence}")
        for clause in clause_group:
            print("    " + _summary_clause(clause))

    print("DEMO OK")


if __name__ == "__main__":
    main()
