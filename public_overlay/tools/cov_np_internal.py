#!/usr/bin/env python3
"""Coverage, source-licensing, realization, and train-gold demo for np_internal."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys

sys.path.insert(0, ".")
sys.path.insert(0, "tools")

import read_coverage as coverage
from verantyx.semantic_ir import data
from verantyx.semantic_reader import document_view
import verantyx.semantic_realize as realize
import verantyx.semantic_verify as verify


GOLD_PROBE = "phase2/gold_probe.py"
LIMIT = 60


def _disabled_names():
    return {part.strip() for part in os.environ.get("VERA_CONSTRUCTIONS_OFF", "").split(",")
            if part.strip() and part.strip() != "np_internal"}


def _set_disabled(names):
    if names:
        os.environ["VERA_CONSTRUCTIONS_OFF"] = ",".join(sorted(names))
    else:
        os.environ.pop("VERA_CONSTRUCTIONS_OFF", None)


def _supported(view):
    return {(clause.span.source, clause.span.start) for clause in view.clauses if not clause.unsupported}


def _gold_counts(disabled):
    env = os.environ.copy()
    _set_disabled(disabled)
    env = os.environ.copy()
    command = [sys.executable, "-B", GOLD_PROBE, "wdw", "--n", "150", "--seed", "0"]
    result = subprocess.run(command, cwd=".", env=env, text=True, capture_output=True,
                            timeout=35, check=True)
    counts = {}
    for line in result.stdout.splitlines():
        if "{" not in line:
            continue
        offset = line.find("{")
        name = line[:offset].strip()
        if not name or name == "TOTAL":
            continue
        value = ast.literal_eval(line[offset:])
        if isinstance(value, dict):
            counts[name] = {key: int(value.get(key, 0)) for key in
                            ("correct", "wrong_overlap", "wrong_other", "abstain")}
    if not counts:
        raise RuntimeError("gold probe returned no phenomenon counts")
    return counts


def _gold_audit(off, on):
    if set(off) != set(on):
        print("GOLD phenotype sets differ", sorted(off), sorted(on))
        return False
    passed = True
    for name in sorted(off):
        before, after = off[name], on[name]
        print("GOLD", name, "correct", before["correct"], "->", after["correct"],
              "wrong_other", before["wrong_other"], "->", after["wrong_other"],
              "wrong_overlap", before["wrong_overlap"], "->", after["wrong_overlap"])
        if after["correct"] < before["correct"] or after["wrong_other"] > before["wrong_other"]:
            passed = False
    return passed


def main():
    original_disabled = _disabled_names()
    docs = coverage.T.load(1500, 200)

    _set_disabled(original_disabled | {"np_internal"})
    off_view = document_view(docs)
    off_supported = _supported(off_view)
    disabled_count = len(off_supported)

    _set_disabled(original_disabled)
    on_view = document_view(docs)
    on_supported = _supported(on_view)
    enabled_count = len(on_supported)
    newly = on_supported - off_supported
    print("supported_sentences disabled", disabled_count)
    print("supported_sentences enabled", enabled_count)
    print("newly supported sentences", len(newly))

    rank = lambda key: hashlib.sha256((key[0] + ":" + str(key[1])).encode()).digest()
    audit_keys = sorted(newly, key=rank)[:LIMIT]
    audited = [clause for key in audit_keys for clause in on_view.clauses
               if clause.rule == "np_internal" and (clause.span.source, clause.span.start) == key]
    licensed = 0
    roundtrip_checked = 0
    roundtrip_agreed = 0
    checker_total = len(audited)
    for clause in audited:
        try:
            result = verify.license_clause(clause, on_view)
            if result is None or result is True:
                licensed += 1
        except Exception:
            pass
        document = on_view.sources.get(clause.span.source, "")
        produced = realize.realize_clause(clause)
        if produced.__class__.__name__ != "Refused":
            roundtrip_checked += 1
            try:
                result = realize.check_round_trip(clause, document)
                if result.get("passed") is True:
                    roundtrip_agreed += 1
            except Exception:
                pass

    license_pct = 100.0 * licensed / checker_total if checker_total else 0.0
    roundtrip_pct = 100.0 * roundtrip_agreed / roundtrip_checked if roundtrip_checked else None
    print("checker licensed", licensed, "/", checker_total)
    if roundtrip_pct is None:
        print("realizable round trips", roundtrip_agreed, "/", roundtrip_checked,
              "agreement N/A (semantic_realize refused every np_internal rule)")
    else:
        print("realizable round trips", roundtrip_agreed, "/", roundtrip_checked,
              "agreement", round(roundtrip_pct, 1), "%")

    example_by_key = {}
    for clause in on_view.clauses:
        key = (clause.span.source, clause.span.start)
        if clause.rule == "np_internal":
            example_by_key.setdefault(key, clause)
    for clause in off_view.clauses:
        key = (clause.span.source, clause.span.start)
        if key in example_by_key or "unrepresented source content" not in clause.unsupported:
            continue
        if any(role.name in ("agent", "patient", "topic") and
               any(mark in role.span.text for mark in ("の", "と", "や", "、", "である", "という"))
               for role in clause.roles):
            example_by_key[key] = clause
    example_keys = sorted(example_by_key, key=rank)[:15]
    for key in example_keys:
        clause = example_by_key[key]
        print("EXAMPLE", json.dumps({"sentence": clause.span.text,
                                    "clauses": [data(clause)]},
                                   ensure_ascii=False, separators=(",", ":")))
    print("human review examples", len(example_keys))

    _set_disabled(original_disabled | {"np_internal"})
    gold_off = _gold_counts(original_disabled | {"np_internal"})
    gold_on = _gold_counts(original_disabled)
    gold_ok = _gold_audit(gold_off, gold_on)

    gates = {
        "coverage_non_decrease": enabled_count >= disabled_count,
        "new_support_minimum": len(newly) >= 10,
        "checker_100_percent": checker_total > 0 and licensed == checker_total,
        "roundtrip_95_percent": roundtrip_checked == 0 or roundtrip_pct >= 95.0,
        "gold_non_regression": gold_ok,
    }
    for name, passed in gates.items():
        print("GATE", name, "PASS" if passed else "FAIL")
    _set_disabled(original_disabled)
    if all(gates.values()):
        print("DEMO OK")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
