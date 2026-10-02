#!/usr/bin/env python3
"""Coverage and precision demo for the adnominal construction."""
from __future__ import annotations

import hashlib
import os
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tools")

import read_coverage  # sets the configured train-lead path on its loader helper
import round5a_route_tune as T
from verantyx.semantic_reader import document_view
from verantyx.semantic_verify import license_clause
from verantyx.semantic_realize import Refused, check_round_trip, realize_clause


def _supported(view):
    return {(c.span.source, c.span.start) for c in view.clauses if not c.unsupported}


def _licensed(clause, view):
    try:
        result = license_clause(clause, view)
    except Exception as exc:  # surfaced as a failed assertion below
        return False, type(exc).__name__ + ": " + str(exc)
    return result is None or result is True, result


def main() -> None:
    original_off = os.environ.get("VERA_CONSTRUCTIONS_OFF")
    prior = {x.strip() for x in (original_off or "").split(",") if x.strip()}
    try:
        os.environ["VERA_CONSTRUCTIONS_OFF"] = ",".join(sorted(prior | {"adnominal"}))
        docs = T.load(1500, 200)
        disabled = document_view(docs)
        disabled_count = len(_supported(disabled))

        if original_off is None:
            os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
        else:
            os.environ["VERA_CONSTRUCTIONS_OFF"] = original_off
        enabled = document_view(docs)
        enabled_count = len(_supported(enabled))
        new_sentences = _supported(enabled) - _supported(disabled)

        def sample_key(key):
            raw = (key[0] + ":" + str(key[1])).encode("utf-8")
            return hashlib.sha256(raw).digest()

        sample = sorted(new_sentences, key=sample_key)[:60]
        clauses_by_sentence = {}
        for clause in enabled.clauses:
            key = (clause.span.source, clause.span.start)
            if key in new_sentences and clause.rule == "adnominal" and not clause.unsupported:
                clauses_by_sentence.setdefault(key, []).append(clause)

        checked_clauses = 0
        licensed_clauses = 0
        failed_licenses = []
        realizable = 0
        roundtrip_ok = 0
        failed_roundtrips = []
        for key in sample:
            clauses = clauses_by_sentence.get(key, ())
            if not clauses:
                failed_licenses.append((key, "no supported adnominal clause"))
                continue
            for clause in clauses:
                checked_clauses += 1
                okay, detail = _licensed(clause, enabled)
                if okay:
                    licensed_clauses += 1
                else:
                    failed_licenses.append((key, detail))
                    continue
                output = realize_clause(clause)
                if isinstance(output, Refused) or not getattr(output, "text", ""):
                    continue
                realizable += 1
                result = check_round_trip(clause, output.text)
                if isinstance(result, dict) and result.get("passed") is True:
                    roundtrip_ok += 1
                else:
                    failed_roundtrips.append((key, result))

        checker_rate = licensed_clauses / checked_clauses if checked_clauses else 0.0
        roundtrip_rate = roundtrip_ok / realizable if realizable else 1.0
        print(f"supported off={disabled_count} on={enabled_count} newly_supported={len(new_sentences)}")
        print(f"audit sentences={len(sample)} clauses={checked_clauses} licensed={licensed_clauses}/{checked_clauses} "
              f"realizable={realizable} roundtrip={roundtrip_ok}/{realizable}")

        shown = 0
        for key in sample:
            if shown >= 15:
                break
            clauses = clauses_by_sentence.get(key, ())
            if not clauses:
                continue
            sentence = clauses[0].span.text
            descriptions = []
            for clause in clauses:
                roles = ", ".join(f"{r.name}={r.span.text!r}" for r in clause.roles)
                descriptions.append(f"{clause.predicate} [{roles}]")
            print(f"EXAMPLE {shown + 1:02d}: {sentence}\n  " + "; ".join(descriptions))
            shown += 1

        assert enabled_count >= disabled_count, "enabled coverage fell below disabled"
        assert len(new_sentences) >= 10, "fewer than 10 newly supported sentences"
        assert len(sample) == 60, "fewer than 60 newly supported sentences for precision audit"
        assert checked_clauses > 0 and checker_rate == 1.0, ("construction checker rejected clauses", failed_licenses[:3])
        assert roundtrip_rate >= 0.95, ("round-trip agreement below 95%", failed_roundtrips[:3])
        assert shown == 15, "fewer than 15 examples available"
        print("DEMO OK")
    finally:
        if original_off is None:
            os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
        else:
            os.environ["VERA_CONSTRUCTIONS_OFF"] = original_off


if __name__ == "__main__":
    main()
