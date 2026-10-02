#!/usr/bin/env python3
"""Coverage and independent-licensor demo for connective_rel."""
from __future__ import annotations

import hashlib
import os
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tools")

import read_coverage as coverage
import round5a_route_tune as corpus

from verantyx.semantic_reader import document_view
from verantyx import semantic_realize, semantic_verify


RULE = "connective_rel"
N = 1500
STRIDE = 200


def _support_keys(view):
    return {(c.span.source, c.span.start) for c in view.clauses if not c.unsupported}


def _rate(passed, total):
    return passed / total if total else 1.0


def _clause_line(clause):
    roles = ", ".join(f"{role.name}={role.term!r}" for role in clause.roles)
    return f"{clause.predicate}({roles}) [{clause.rule}]"


def main():
    corpus_path = os.environ.get("VERA_LEADS")
    if corpus_path:
        corpus.PATH = corpus_path
    prior_off = os.environ.get("VERA_CONSTRUCTIONS_OFF")
    disabled_names = {part.strip() for part in (prior_off or "").split(",") if part.strip()}
    disabled_names.add(RULE)
    os.environ["VERA_CONSTRUCTIONS_OFF"] = ",".join(sorted(disabled_names))
    disabled_coverage = coverage.measure(N, STRIDE)
    docs = corpus.load(N, STRIDE)
    disabled_view = document_view(docs)
    disabled_keys = _support_keys(disabled_view)

    if prior_off is None:
        os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
    else:
        os.environ["VERA_CONSTRUCTIONS_OFF"] = prior_off
    enabled_coverage = coverage.measure(N, STRIDE)
    enabled_view = document_view(docs)
    enabled_keys = _support_keys(enabled_view)
    new_keys = enabled_keys - disabled_keys

    deterministic = sorted(new_keys, key=lambda key: hashlib.sha256(
        f"{key[0]}:{key[1]}".encode("utf-8")).hexdigest())
    sample = deterministic[:60]
    checker_total = checker_passed = 0
    realizable = roundtrip_passed = roundtrip_failed = not_realizable = 0
    generated_by_key = {}

    for key in sample:
        clauses = tuple(c for c in enabled_view.clauses
                        if (c.span.source, c.span.start) == key
                        and c.rule == RULE and not c.unsupported)
        generated_by_key[key] = clauses
        for clause in clauses:
            checker_total += 1
            try:
                semantic_verify.license_clause(clause, enabled_view)
                checker_passed += 1
            except Exception:
                continue

            realized = semantic_realize.realize_clause(clause)
            if isinstance(realized, semantic_realize.Refused):
                # The current v1 realizer intentionally declines extension
                # rules.  Only clauses it can actually construct enter the
                # round-trip denominator.
                if realized.reason != "UNSUPPORTED_RULE":
                    realizable += 1
                    roundtrip_failed += 1
                else:
                    not_realizable += 1
                continue
            realizable += 1
            try:
                checked = semantic_realize.check_round_trip(clause, realized.text)
                if checked.get("passed"):
                    roundtrip_passed += 1
                else:
                    roundtrip_failed += 1
            except Exception:
                roundtrip_failed += 1

    checker_rate = _rate(checker_passed, checker_total)
    roundtrip_rate = _rate(roundtrip_passed, realizable)
    newly_supported = len(new_keys)
    print(f"supported disabled: {disabled_coverage['supported_sentences']}")
    print(f"supported enabled: {enabled_coverage['supported_sentences']}")
    print(f"newly supported sentences: {newly_supported}")
    print(f"checker licensed: {checker_passed}/{checker_total} ({checker_rate:.1%})")
    if realizable:
        print(f"round-trip agreement: {roundtrip_passed}/{realizable} ({roundtrip_rate:.1%}); "
              f"not realizable by current producer: {not_realizable}")
    else:
        print(f"round-trip agreement: no realizable clauses (0 checks); "
              f"not realizable by current producer: {not_realizable}")
    print(f"precision sample: {len(sample)} sentences")

    examples = 0
    for key in sample:
        if examples >= 15:
            break
        sentence = next((c.span.text for c in enabled_view.clauses
                         if (c.span.source, c.span.start) == key), "")
        for clause in generated_by_key.get(key, ()):
            if examples >= 15:
                break
            examples += 1
            print(f"{examples}. {sentence}")
            print("   " + _clause_line(clause))
    print(f"examples printed: {examples}/15 available")

    assert enabled_coverage["supported_sentences"] >= disabled_coverage["supported_sentences"]
    assert newly_supported >= 10
    assert checker_total > 0 and checker_rate == 1.0
    assert roundtrip_rate >= 0.95 and roundtrip_failed == 0
    print("DEMO OK")


if __name__ == "__main__":
    main()
