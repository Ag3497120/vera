#!/usr/bin/env python3
"""Measure and audit the zero-subject construction on train leads only."""
from __future__ import annotations

import os
import sys

sys.path[:0] = [".", "tools"]

import round5a_route_tune as T

if os.environ.get("VERA_LEADS"):
    T.PATH = os.environ["VERA_LEADS"]

from verantyx.semantic_reader import document_view
from verantyx.semantic_realize import Refused, check_round_trip, realize_clause
from verantyx.semantic_verify import license_clause


def _supported(view):
    return {(clause.span.source, clause.span.start)
            for clause in view.clauses if not clause.unsupported}


def _sample(keys, limit=60):
    ordered = sorted(keys)
    if len(ordered) <= limit:
        return ordered
    return [ordered[(i * len(ordered)) // limit] for i in range(limit)]


def main():
    docs = T.load(1500, 200)
    prior_off = os.environ.get("VERA_CONSTRUCTIONS_OFF", "")
    off_names = {name.strip() for name in prior_off.split(",") if name.strip()}
    off_names.add("zero_subject")
    os.environ["VERA_CONSTRUCTIONS_OFF"] = ",".join(sorted(off_names))
    disabled = document_view(docs)

    off_names.remove("zero_subject")
    if off_names:
        os.environ["VERA_CONSTRUCTIONS_OFF"] = ",".join(sorted(off_names))
    else:
        os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
    enabled = document_view(docs)

    disabled_count = len(_supported(disabled))
    enabled_count = len(_supported(enabled))
    new_keys = _supported(enabled) - _supported(disabled)
    sample = _sample(new_keys)

    audited = 0
    checker_passes = 0
    realizable = 0
    not_realizable = 0
    round_trip_passes = 0
    examples = []
    for key in sample:
        clauses = [c for c in enabled.clauses
                   if (c.span.source, c.span.start) == key and not c.unsupported]
        assert clauses, "newly supported sentence has no supported clause"
        constructed = [c for c in clauses if c.rule == "zero_subject"]
        assert constructed, "new support did not come from zero_subject"
        for clause in clauses:
            audited += 1
            try:
                license_clause(clause, enabled)
            except Exception as error:
                raise AssertionError("semantic_verify rejected " + clause.id) from error
            checker_passes += 1

            realized = realize_clause(clause)
            if isinstance(realized, Refused) or not isinstance(getattr(realized, "text", None), str):
                not_realizable += 1
                continue
            realizable += 1
            round_trip = check_round_trip(clause, realized.text)
            if round_trip.get("passed"):
                round_trip_passes += 1

        examples.append((key, clauses))

    checker_rate = checker_passes / audited if audited else 0.0
    round_trip_rate = round_trip_passes / realizable if realizable else 1.0
    assert enabled_count >= disabled_count, "enabled coverage fell below disabled"
    assert len(new_keys) >= 10, "fewer than ten newly supported sentences"
    assert audited > 0 and checker_rate == 1.0, "checker licensing was not 100%"
    assert round_trip_rate >= 0.95, "realization round-trip agreement below 95%"
    assert len(examples) >= 15, "fewer than fifteen examples to print"

    print("supported disabled:", disabled_count)
    print("supported enabled:", enabled_count)
    print("newly supported:", len(new_keys))
    print("audited clauses:", audited)
    print("semantic_verify licensed:", checker_passes, "/", audited)
    print("realizable clauses:", realizable)
    print("not realizable:", not_realizable)
    if realizable:
        print("round-trip agreement:", round_trip_passes, "/", realizable,
              "(" + format(round_trip_rate * 100, ".1f") + "%)")
    else:
        print("round-trip agreement: N/A (no clauses were realizable)")

    for index, (key, clauses) in enumerate(examples[:15], 1):
        sentence = clauses[0].span.text
        rendered = "; ".join(
            clause.predicate + "(" + ", ".join(
                role.name + "=" + str(role.term) for role in clause.roles) + ")"
            for clause in clauses
        )
        print("EXAMPLE", index, key[0] + ":" + str(key[1]))
        print("  ", sentence)
        print("  ", rendered)

    print("DEMO OK")


if __name__ == "__main__":
    main()
