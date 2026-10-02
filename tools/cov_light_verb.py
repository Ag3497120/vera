#!/usr/bin/env python3
"""Measure and audit source-bounded light-verb readings on train leads."""
from __future__ import annotations

import hashlib
import os
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tools")

import read_coverage as coverage
from verantyx.semantic_reader import document_view
import verantyx.semantic_verify as semantic_verify
import verantyx.semantic_realize as semantic_realize


def _view(documents, disabled):
    if disabled:
        os.environ["VERA_CONSTRUCTIONS_OFF"] = "light_verb"
    else:
        os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
    return document_view(documents)


def _supported(view):
    return {(c.span.source, c.span.start) for c in view.clauses if not c.unsupported}


def _sentence_at(text, position):
    left = max((text.rfind(mark, 0, position) for mark in ("。", "！", "？", "!", "?")),
               default=-1) + 1
    ends = [at for mark in ("。", "！", "？", "!", "?")
            if (at := text.find(mark, position)) >= 0]
    right = min(ends) + 1 if ends else len(text)
    return text[left:right].strip()


def _key_hash(key):
    return hashlib.sha256((key[0] + "\0" + str(key[1])).encode("utf-8")).digest()


def main():
    documents = coverage.T.load(1500, 200)
    disabled_view = _view(documents, True)
    enabled_view = _view(documents, False)
    disabled = _supported(disabled_view)
    enabled = _supported(enabled_view)
    new_keys = sorted(enabled - disabled)
    print("supported_sentences disabled:", len(disabled))
    print("supported_sentences enabled:", len(enabled))
    print("newly supported sentences:", len(new_keys))

    constructed = {}
    for clause in enabled_view.clauses:
        key = (clause.span.source, clause.span.start)
        if clause.rule == "light_verb" and not clause.unsupported and key in new_keys:
            constructed.setdefault(key, []).append(clause)
    sample_keys = sorted(new_keys, key=_key_hash)[:60]
    audit = [clause for key in sample_keys for clause in constructed.get(key, ())]
    licensed = 0
    realizable = 0
    roundtrip = 0
    sources = enabled_view.sources
    for clause in audit:
        try:
            result = semantic_verify.license_clause(clause, enabled_view)
        except Exception as exc:
            raise AssertionError("semantic checker rejected " + clause.id) from exc
        assert result is None, "semantic checker did not license " + clause.id
        licensed += 1
        generated = semantic_realize.realize_clause(clause)
        if isinstance(generated, semantic_realize.Refused):
            continue
        realizable += 1
        result = semantic_realize.check_round_trip(clause, sources[clause.span.source])
        assert result.get("passed") is True, "semantic realization round trip failed"
        roundtrip += 1

    checker_pct = 100.0 * licensed / max(1, len(audit))
    roundtrip_pct = 100.0 * roundtrip / realizable if realizable else None
    print("precision audit:", len(audit), "clauses from", len(sample_keys), "sentences")
    print("checker licensed:", f"{licensed}/{len(audit)} ({checker_pct:.1f}%)")
    if roundtrip_pct is None:
        print("realizable round trips: not applicable (0 clauses accepted by semantic_realize)")
    else:
        print("realizable round trips:", f"{roundtrip}/{realizable} ({roundtrip_pct:.1f}%)")

    example_keys = [key for key in sorted(new_keys) if constructed.get(key)][:15]
    for number, key in enumerate(example_keys, 1):
        source_id, start = key
        source = sources[source_id]
        sentence = _sentence_at(source, start)
        clauses = constructed[key]
        summaries = [{
            "predicate": clause.predicate,
            "roles": [(role.name, role.term) for role in clause.roles],
            "rule": clause.rule,
        } for clause in clauses]
        print(f"EXAMPLE {number}: {sentence}")
        print("  clauses:", summaries)

    assert len(enabled) >= len(disabled), "enabled coverage fell below disabled coverage"
    assert len(new_keys) >= 10, "fewer than 10 newly supported sentences"
    assert checker_pct == 100.0, "construction checker precision was below 100%"
    assert realizable == 0 or roundtrip_pct >= 95.0, "realizable round-trip agreement was below 95%"
    print("DEMO OK")


if __name__ == "__main__":
    main()
