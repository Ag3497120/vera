#!/usr/bin/env python3
"""Measure diathesis reading recovery and audit its source licenses."""
from __future__ import annotations

import os
import sys
from collections import Counter

sys.path[:0] = [".", "tools"]


def _supported(view):
    return {(c.span.source, c.span.start) for c in view.clauses if not c.unsupported}


def _sample(items, count):
    if len(items) <= count:
        return items
    if count <= 1:
        return items[:1]
    indexes = [round(i * (len(items) - 1) / (count - 1)) for i in range(count)]
    return [items[i] for i in indexes]


def _sentence_at(document, start):
    left = document.rfind("。", 0, start) + 1
    right = document.find("。", start)
    if right < 0:
        right = len(document)
    return document[left:right].strip()


def main():
    import round5a_route_tune as corpus
    from verantyx.semantic_reader import document_view
    from verantyx.semantic_realize import realize_clause
    from verantyx.semantic_ir import View
    from verantyx.semantic_verify import license_clause

    if os.environ.get("VERA_LEADS"):
        corpus.PATH = os.environ["VERA_LEADS"]
    documents = corpus.load(1500, 200)
    prior_off = os.environ.get("VERA_CONSTRUCTIONS_OFF", "")
    off_names = [name.strip() for name in prior_off.split(",") if name.strip()]
    if "diathesis" not in off_names:
        off_names.append("diathesis")
    os.environ["VERA_CONSTRUCTIONS_OFF"] = ",".join(off_names)
    disabled_view = document_view(documents)
    disabled_count = len(_supported(disabled_view))
    os.environ["VERA_CONSTRUCTIONS_OFF"] = prior_off
    enabled_view = document_view(documents)
    enabled_count = len(_supported(enabled_view))
    disabled_keys = _supported(disabled_view)
    enabled_keys = _supported(enabled_view)
    new_keys = sorted(enabled_keys - disabled_keys)
    new_clauses = [c for c in enabled_view.clauses
                   if c.rule == "diathesis" and not c.unsupported
                   and (c.span.source, c.span.start) in set(new_keys)]
    clauses_by_key = {}
    for clause in new_clauses:
        clauses_by_key.setdefault((clause.span.source, clause.span.start), []).append(clause)
    audited_keys = _sample(new_keys, 60)
    audited_clauses = [clause for key in audited_keys for clause in clauses_by_key.get(key, ())]
    licensed = 0
    for clause in audited_clauses:
        try:
            checker_view = View(sources=documents, clauses=(clause,))
            license_clause(clause, checker_view)
            licensed += 1
        except Exception:
            pass
    realized_count = 0
    roundtrip_count = 0
    refused = Counter()
    for clause in audited_clauses:
        try:
            result = realize_clause(clause)
        except Exception:
            realized_count += 1
            continue
        if type(result).__name__ == "Refused":
            refused[getattr(result, "reason", "unknown")] += 1
            continue
        realized_count += 1
        check = getattr(result, "checks", {}).get("roundtrip", {})
        if isinstance(check, dict) and check.get("passed") is True:
            roundtrip_count += 1
    agreement = roundtrip_count / realized_count if realized_count else None

    assert enabled_count >= disabled_count, (disabled_count, enabled_count)
    assert len(new_keys) >= 10, len(new_keys)
    assert audited_clauses and licensed == len(audited_clauses), (licensed, len(audited_clauses))
    assert agreement is None or agreement >= 0.95, (roundtrip_count, realized_count, agreement)

    print("supported_sentences disabled=%d enabled=%d newly_supported=%d" %
          (disabled_count, enabled_count, len(new_keys)))
    if realized_count:
        roundtrip_label = "%d/%d" % (roundtrip_count, realized_count)
    else:
        roundtrip_label = "not realizable (0/0; refusals=%s)" % dict(refused)
    print("precision_sample=%d clauses=%d licensed=%d roundtrip=%s" %
          (len(audited_keys), len(audited_clauses), licensed, roundtrip_label))
    for index, key in enumerate(_sample(new_keys, 15), 1):
        source, start = key
        sentence = _sentence_at(documents[source], start)
        descriptions = [
            c.predicate + "(" + ", ".join(r.name + "=" + r.span.text for r in c.roles) + ")"
            for c in clauses_by_key.get(key, ())
        ]
        print("EXAMPLE %02d %s" % (index, sentence))
        print("  " + " | ".join(descriptions))
    print("DEMO OK")


if __name__ == "__main__":
    main()
