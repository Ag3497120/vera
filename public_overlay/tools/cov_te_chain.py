#!/usr/bin/env python3
"""Coverage and precision demo for the te_chain construction."""
from __future__ import annotations

import hashlib
import json
import os
import sys


os.environ.setdefault("VERA_CORPUS_ROOT", "/tmp/vera-empty-materials")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")
sys.path.insert(0, ".")
sys.path.insert(0, "tools")

from read_coverage import T
from verantyx.semantic_reader import document_view
import verantyx.semantic_verify as semantic_verify
import verantyx.semantic_realize as semantic_realize


def _coverage_keys(view):
    return {(clause.span.source, clause.span.start) for clause in view.clauses if not clause.unsupported}


def _sentence_for(source: str, text: str, position: int) -> str:
    start = text.rfind("。", 0, position) + 1
    end = text.find("。", position)
    if end < 0:
        end = len(text)
    else:
        end += 1
    sentence = text[start:end]
    return sentence if sentence else source


def _sample_key(key):
    source, start = key
    return hashlib.sha256((source + ":" + str(start)).encode("utf-8")).digest()


def main() -> None:
    docs = T.load(1500, 200)
    original_off = [part.strip() for part in os.environ.get("VERA_CONSTRUCTIONS_OFF", "").split(",")
                    if part.strip() and part.strip() != "te_chain"]
    os.environ["VERA_CONSTRUCTIONS_OFF"] = ",".join(original_off + ["te_chain"])
    disabled_view = document_view(docs)
    disabled = len(_coverage_keys(disabled_view))

    if original_off:
        os.environ["VERA_CONSTRUCTIONS_OFF"] = ",".join(original_off)
    else:
        os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
    enabled_view = document_view(docs)
    enabled = len(_coverage_keys(enabled_view))
    newly_supported = _coverage_keys(enabled_view) - _coverage_keys(disabled_view)
    print("supported_sentences disabled={} enabled={} newly_supported={}".format(
        disabled, enabled, len(newly_supported)))

    ordered_keys = sorted(newly_supported, key=_sample_key)
    audit_keys = ordered_keys[:60]
    audit_set = set(audit_keys)
    new_clauses = [c for c in enabled_view.clauses
                   if c.rule == "te_chain" and (c.span.source, c.span.start) in audit_set]
    by_key = {}
    for clause in new_clauses:
        by_key.setdefault((clause.span.source, clause.span.start), []).append(clause)

    checked = 0
    licensed = 0
    realizable = 0
    roundtrip_ok = 0
    realizer_out_of_scope = 0
    failures = []
    for key in audit_keys:
        for clause in by_key.get(key, ()):
            checked += 1
            try:
                result = semantic_verify.license_clause(clause, enabled_view)
                if result is None:
                    licensed += 1
                else:
                    failures.append((key, "checker returned a non-empty result"))
            except Exception as exc:
                failures.append((key, type(exc).__name__ + ": " + str(exc)))
            realized = semantic_realize.realize_clause(clause)
            checks = getattr(realized, "checks", None)
            roundtrip = checks.get("roundtrip") if isinstance(checks, dict) else None
            if isinstance(roundtrip, dict):
                realizable += 1
                if roundtrip.get("passed") is True:
                    roundtrip_ok += 1
            elif getattr(realized, "reason", "") == "UNSUPPORTED_RULE":
                realizer_out_of_scope += 1
            else:
                failures.append((key, "realizer did not return a round-trip check or typed unsupported-rule refusal"))

    checker_pct = 100.0 * licensed / max(1, checked)
    roundtrip_pct = 100.0 if realizable == 0 else 100.0 * roundtrip_ok / realizable
    print("precision sample_sentences={} clauses={} checker_licensed={}/{} ({:.1f}%)".format(
        len(audit_keys), checked, licensed, checked, checker_pct))
    qualifier = "vacuous " if realizable == 0 else ""
    print("roundtrip realizable={}/{} ({}{:.1f}%); typed_out_of_scope={}".format(
        roundtrip_ok, realizable, qualifier, roundtrip_pct, realizer_out_of_scope))
    if failures:
        print("checker_failures=" + json.dumps(failures[:5], ensure_ascii=False))

    example_rows = [(key, (clause,)) for key in audit_keys for clause in by_key.get(key, ())]
    for key, example_clauses in example_rows[:15]:
        source, start = key
        full_source = enabled_view.sources[source]
        sentence = _sentence_for(source, full_source, start)
        payload = {
            "sentence": sentence,
            "clauses": [
                {
                    "predicate": c.predicate,
                    "predicate_span": c.predicate_span.text,
                    "roles": [{"name": r.name, "term": str(r.term), "span": r.span.text}
                              for r in c.roles],
                    "scope": c.span.text,
                }
                for c in example_clauses
            ],
        }
        print(json.dumps(payload, ensure_ascii=False))

    assert enabled >= disabled, "enabled coverage fell below disabled coverage"
    assert len(newly_supported) >= 10, "fewer than 10 newly supported sentences"
    assert checked > 0 and licensed == checked, "checker did not license every audited clause"
    assert not failures, "unexpected checker or realization failure"
    assert roundtrip_pct >= 95.0, "round-trip agreement fell below 95%"
    print("DEMO OK")


if __name__ == "__main__":
    main()
