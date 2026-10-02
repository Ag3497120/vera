#!/usr/bin/env python3
"""Coverage and precision demo for the source-bounded quote construction."""
from __future__ import annotations

import json
import os
import sys

sys.path[:0] = [".", "tools"]
os.environ.setdefault("VERA_CORPUS_ROOT", "/tmp/vera-empty-materials")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

import read_coverage as coverage
from verantyx.semantic_ir import data
from verantyx.semantic_reader import document_view
from verantyx.semantic_verify import license_clause
from verantyx import semantic_realize


N = 1500
STRIDE = 200
AUDIT_SIZE = 60


def _supported(view):
    return {(clause.span.source, clause.span.start)
            for clause in view.clauses if not clause.unsupported}


def _grouped(view):
    groups = {}
    for clause in view.clauses:
        groups.setdefault((clause.span.source, clause.span.start), []).append(clause)
    return groups


def _audit_sample(view, keys):
    groups = _grouped(view)
    checked = 0
    licensed = 0
    roundtrip_checked = 0
    roundtrip_ok = 0
    details = []
    for key in keys:
        clauses = tuple(c for c in groups.get(key, ()) if c.rule == "quote")
        raw = view.sources.get(key[0], "")
        sentence = next((c.span.text for c in clauses if c.span.start == key[1]), "")
        if not sentence and raw:
            sentence = raw[key[1]:].split("。", 1)[0] + ("。" if "。" in raw[key[1]:] else "")
        clause_results = []
        for clause in clauses:
            checked += 1
            try:
                license_clause(clause, view)
                ok = True
            except Exception:
                ok = False
            licensed += int(ok)
            result = semantic_realize.realize_clause(clause)
            if isinstance(result, semantic_realize.Realized):
                rt = semantic_realize.check_round_trip(clause, result.text)
                roundtrip_checked += 1
                roundtrip_ok += int(bool(rt.get("passed")))
            clause_results.append({"licensed": ok, "clause": data(clause)})
        details.append({"sentence": sentence, "clauses": clause_results})
    license_rate = licensed / checked if checked else 0.0
    roundtrip_rate = roundtrip_ok / roundtrip_checked if roundtrip_checked else 1.0
    return {
        "sentences": len(keys),
        "clauses": checked,
        "licensed": licensed,
        "license_rate": license_rate,
        "roundtrip_checked": roundtrip_checked,
        "roundtrip_ok": roundtrip_ok,
        "roundtrip_rate": roundtrip_rate,
        "examples": details,
    }


def main():
    documents = coverage.T.load(N, STRIDE)
    os.environ["VERA_CONSTRUCTIONS_OFF"] = "quote"
    disabled = document_view(documents)
    os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)
    enabled = document_view(documents)

    off_count = len(_supported(disabled))
    on_count = len(_supported(enabled))
    new_keys = sorted(_supported(enabled) - _supported(disabled))
    print(f"supported_sentences disabled={off_count} enabled={on_count}")
    print(f"newly supported sentences={len(new_keys)}")

    sample = new_keys[:AUDIT_SIZE]
    audit = _audit_sample(enabled, sample)
    print("precision audit " + json.dumps({
        key: audit[key] for key in ("sentences", "clauses", "licensed", "license_rate",
                                    "roundtrip_checked", "roundtrip_ok", "roundtrip_rate")
    }, ensure_ascii=False, sort_keys=True))
    for example in audit["examples"][:15]:
        print("EXAMPLE " + json.dumps(example, ensure_ascii=False, sort_keys=True))

    # This unit is assigned Wikipedia coverage only; no gold phenomenon was
    # assigned, and the gold-probe corpus is outside this unit's read boundary.
    print("gold probe: no assigned phenomenon (Wikipedia coverage only)")

    assert on_count >= off_count, "enabled coverage fell below disabled coverage"
    assert len(new_keys) >= 10, "fewer than 10 newly supported sentences"
    assert len(sample) == AUDIT_SIZE, "fewer than 60 newly supported sentences to audit"
    assert audit["clauses"] > 0 and audit["license_rate"] == 1.0, "checker license audit failed"
    assert audit["roundtrip_rate"] >= 0.95, "round-trip agreement below 95%"
    print("DEMO OK")


if __name__ == "__main__":
    main()
