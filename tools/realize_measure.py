#!/usr/bin/env python3
"""Measure verified semantic realization on stride-sampled Wikipedia train leads."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, ".")

from verantyx.semantic_ir import Clause
from verantyx.semantic_reader import document_view
from verantyx.semantic_realize import (
    MAX_CHARS, MAX_CLAUSES, Realized, Refused, _surface_text,
    check_round_trip, check_term_lineage, projection, realize_clause,
)
from verantyx.typed_edges import _tagger

PATH = Path("/Users/motonishikoudai/Projects/vera-corpus/build/round4/jawiki_leads.full.jsonl")
RULES = ("frame", "copula", "measure")
MUTATION_TYPES = ("flip_polarity", "swap_tense", "swap_roles", "replace_term")
CONTENT_POS = frozenset(("名詞", "動詞", "形容詞", "形状詞", "接頭辞", "接尾辞"))


def load_train_leads(path: Path, count: int, stride: int) -> dict[str, str]:
    """Use the route-tune loader contract: stride first, then train-only leads."""
    documents: dict[str, str] = {}
    with path.open(encoding="utf-8") as stream:
        for index, line in enumerate(stream):
            if index % stride:
                continue
            row = json.loads(line)
            text = row.get("text") or ""
            if row.get("split") == "train" and len(text) >= 40 and not text.startswith(("#", "REDIRECT")):
                documents[f"w{len(documents)}"] = text
            if len(documents) >= count:
                break
    return documents


def _eligible(clause: Clause) -> bool:
    return (clause.rule in RULES and not clause.unsupported
            and not clause.conditions and not clause.condition_spans
            and not clause.exceptions and not clause.exception_spans and not clause.exception_of
            and clause.modality == "assert")


def _attempt_row(clause: Clause, style: str) -> tuple[dict[str, Any], Realized | Refused]:
    result = realize_clause(clause, style)
    row: dict[str, Any] = {
        "kind": "realization", "clause_id": clause.id, "source": clause.span.source,
        "rule": clause.rule, "style": style, "source_text": clause.span.text,
    }
    if isinstance(result, Realized):
        row.update({"status": "REALIZED", "text": result.text, "checks": result.checks,
                    "provenance": result.as_dict()})
    else:
        row.update({"status": "REFUSED", "reason": result.reason, "detail": result.detail,
                    "checks": result.checks or {}})
    return row, result


def _lemma(word: Any) -> str:
    return (getattr(word.feature, "lemma", None) or getattr(word.feature, "orthBase", None)
            or word.surface)


def _content_lemmas(text: str) -> set[str]:
    return {_lemma(word) for word in _tagger()(text) if word.feature.pos1 in CONTENT_POS}


def _swappable_roles(clause: Clause) -> tuple[str, str] | None:
    roles = [r for r in clause.roles if r.name != "agent"]
    roles += [r for r in clause.roles if r.name == "agent"]
    for i, left in enumerate(roles):
        for right in roles[i + 1:]:
            if left.span.text != right.span.text and left.term != right.term:
                return left.name, right.name
    return None


def _mutation(clause: Clause, realized: Realized, kind: str,
              replacement_terms: list[tuple[str, str]]) -> str | None:
    if clause.rule != "frame":
        return None
    if kind == "flip_polarity":
        text, _ = _surface_text(clause, realized.style, topic="は",
                                polarity="-" if clause.polarity == "+" else "+")
        return text
    if kind == "swap_tense":
        text, _ = _surface_text(clause, realized.style, topic="は",
                                time="nonpast" if clause.time == "past" else "past")
        return text
    if kind == "swap_roles":
        pair = _swappable_roles(clause)
        if not pair:
            return None
        roles = {r.name: r for r in clause.roles}
        a, b = pair
        text, _ = _surface_text(clause, realized.style, topic="は",
                                overrides={a: roles[b].span.text, b: roles[a].span.text})
        return text
    if kind == "replace_term":
        role = next((r for r in clause.roles if r.name != "agent"), None)
        role = role or next((r for r in clause.roles if r.name == "agent"), None)
        if role is None:
            return None
        own = _content_lemmas(clause.span.text)
        replacement = next((term for source, term in replacement_terms
                            if source != clause.span.source
                            and term != role.span.text
                            and not (_content_lemmas(term) & own)), None)
        if replacement is None:
            return None
        text, _ = _surface_text(clause, realized.style, topic="は",
                                overrides={role.name: replacement})
        return text
    return None


def _read_projection(clause: Clause, sentence: str) -> tuple[Any, ...] | None:
    from verantyx.semantic_reader import document_view
    view = document_view({"mutation": sentence})
    if view.unread or len(view.clauses) != 1 or view.clauses[0].unsupported:
        return None
    return projection(view.clauses[0])


def _mutate_rows(realized_rows: list[tuple[Clause, Realized]], terms: list[tuple[str, str]],
                 requested: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    quota = requested // len(MUTATION_TYPES)
    quotas = {name: quota for name in MUTATION_TYPES}
    for name in MUTATION_TYPES[:requested % len(MUTATION_TYPES)]:
        quotas[name] += 1
    mutation_rows: list[dict[str, Any]] = []
    used_inputs: set[int] = set()
    for kind in MUTATION_TYPES:
        for index, (clause, realized) in enumerate(realized_rows):
            if len([r for r in mutation_rows if r["mutation"] == kind]) >= quotas[kind]:
                break
            if index in used_inputs:
                continue
            changed = _mutation(clause, realized, kind, terms)
            if not changed or changed == realized.text:
                continue
            changed_projection = _read_projection(clause, changed)
            if changed_projection is None or changed_projection == projection(clause):
                continue
            roundtrip = check_round_trip(clause, changed)
            lineage = check_term_lineage(clause, changed)
            row = {
                "kind": "mutation", "mutation": kind, "clause_id": clause.id,
                "source": clause.span.source, "rule": clause.rule, "style": realized.style,
                "original": realized.text, "mutated": changed,
                "source_projection": projection(clause), "mutated_projection": changed_projection,
                "roundtrip": roundtrip, "term_lineage": lineage,
                "caught_roundtrip": not roundtrip["passed"],
                "caught_term_lineage": not lineage["passed"],
                "caught_jointly": not roundtrip["passed"] or not lineage["passed"],
            }
            mutation_rows.append(row)
            used_inputs.add(index)
    by_type: dict[str, Any] = {}
    for kind in MUTATION_TYPES:
        rows = [row for row in mutation_rows if row["mutation"] == kind]
        by_type[kind] = {
            "requested": quotas[kind], "n": len(rows),
            "roundtrip_caught": sum(row["caught_roundtrip"] for row in rows),
            "term_lineage_caught": sum(row["caught_term_lineage"] for row in rows),
            "jointly_caught": sum(row["caught_jointly"] for row in rows),
        }
    n = len(mutation_rows)
    rates = {
        "n": n,
        "roundtrip_caught": sum(row["caught_roundtrip"] for row in mutation_rows),
        "term_lineage_caught": sum(row["caught_term_lineage"] for row in mutation_rows),
        "jointly_caught": sum(row["caught_jointly"] for row in mutation_rows),
    }
    for key in ("roundtrip_caught", "term_lineage_caught", "jointly_caught"):
        rates[key + "_rate"] = rates[key] / n if n else None
    rates["by_type"] = by_type
    rates["joint_threshold_99_passed"] = bool(n == requested and n and rates["jointly_caught_rate"] >= 0.99)
    return mutation_rows, rates


def run(path: Path = PATH, *, n_docs: int = 1000, stride: int = 300,
        mutation_samples: int = 300, out_dir: Path = Path("results/realize")) -> dict[str, Any]:
    if n_docs < 1 or stride < 1 or mutation_samples < 1:
        raise ValueError("n_docs, stride, and mutation_samples must be positive")
    documents = load_train_leads(path, n_docs, stride)
    view = document_view(documents)
    stats = {rule: {"attempts": 0, "realizable": 0, "refused": {},
                    "passed_both_checks": 0, "failed_roundtrip_only": 0,
                    "failed_term_lineage_only": 0, "failed_both_checks": 0}
             for rule in RULES}
    raw_rows: list[dict[str, Any]] = []
    successful: list[tuple[Clause, Realized]] = []
    source_terms: list[tuple[str, str]] = []
    for clause in view.clauses:
        if not _eligible(clause):
            continue
        for role in clause.roles:
            if role.span.text:
                source_terms.append((clause.span.source, role.span.text))
        for style in ("plain", "polite"):
            row, outcome = _attempt_row(clause, style)
            raw_rows.append(row)
            bucket = stats[clause.rule]
            bucket["attempts"] += 1
            if isinstance(outcome, Realized):
                bucket["realizable"] += 1
                bucket["passed_both_checks"] += 1
                successful.append((clause, outcome))
            else:
                bucket["refused"][outcome.reason] = bucket["refused"].get(outcome.reason, 0) + 1
                checks = outcome.checks or {}
                a = checks.get("roundtrip", {}).get("passed")
                b = checks.get("term_lineage", {}).get("passed")
                if a is False and b is True:
                    bucket["failed_roundtrip_only"] += 1
                elif a is True and b is False:
                    bucket["failed_term_lineage_only"] += 1
                elif a is False and b is False:
                    bucket["failed_both_checks"] += 1
    mutation_rows, mutation_stats = _mutate_rows(successful, source_terms, mutation_samples)
    raw_rows.extend(mutation_rows)
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = out_dir / "realize_measure_2026-10-02.jsonl"
    with raw_path.open("w", encoding="utf-8") as stream:
        for row in raw_rows:
            stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    report = {
        "protocol": "semantic-realize-v1", "prototype": True, "adopted": False,
        "input": str(path), "train_documents": len(documents), "stride": stride,
        "reader_clauses": len(view.clauses), "reader_unread": len(view.unread),
        "eligible_clauses": sum(bucket["attempts"] for bucket in stats.values()) // 2,
        "max_clauses_per_request": MAX_CLAUSES, "max_chars_per_request": MAX_CHARS,
        "per_rule": stats, "mutation_test": mutation_stats,
        "raw_rows": str(raw_path), "raw_row_count": len(raw_rows),
        "joint_mutation_threshold_passed": mutation_stats["joint_threshold_99_passed"],
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not mutation_stats["joint_threshold_99_passed"]:
        return {**report, "exit_status": 2}
    return {**report, "exit_status": 0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", type=Path, default=PATH)
    parser.add_argument("--n", type=int, default=1000)
    parser.add_argument("--stride", type=int, default=300)
    parser.add_argument("--mutation-samples", type=int, default=300)
    parser.add_argument("--out-dir", type=Path, default=Path("results/realize"))
    args = parser.parse_args()
    return int(run(args.path, n_docs=args.n, stride=args.stride,
                   mutation_samples=args.mutation_samples, out_dir=args.out_dir)["exit_status"])


if __name__ == "__main__":
    raise SystemExit(main())
