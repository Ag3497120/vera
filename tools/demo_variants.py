#!/usr/bin/env python3
"""Exercise deterministic template building and checked surface variation."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import build_variants as builder
from verantyx import semantic_generate as generation
from verantyx.semantic_realize import Refused, projection, realize_clause, realize_variants, verify_sentence
from verantyx.semantic_reader import document_view

ARTIFACT = ROOT / "verantyx" / "data" / "realize_variants.json"
SYNTHETIC_TRAIN = (
    "太郎は先生に手紙を送った。",
    "花子が本を友人に送った。",
    "学生は資料を教師に送った。",
    "父が母に写真を送った。",
    "子どもは祖母に花を送った。",
    "姉が荷物を弟に送った。",
)
SYNTHETIC_HELD_ASIDE = (
    "佐藤は鈴木に書類を送った。",
    "先生が学生に本を送った。",
    "母は手紙を父に送った。",
)


def _readable(sentence: str) -> tuple[Any, Any] | None:
    try:
        view = document_view({"demo": sentence})
        if view.unread or len(view.clauses) != 1:
            return None
        clause = view.clauses[0]
        if getattr(clause, "unsupported", ()) or isinstance(realize_clause(clause), Refused):
            return None
        checks = verify_sentence(clause, sentence)
    except Exception:
        return None
    if not checks["roundtrip"]["passed"] or not checks["term_lineage"]["passed"]:
        return None
    return view, clause


def _validate_templates(templates: list[dict[str, Any]], sentences: list[str]) -> int:
    held: dict[tuple[Any, ...], list[Any]] = {}
    for sentence in sentences:
        parsed = _readable(sentence)
        if parsed is None:
            continue
        _view, clause = parsed
        key = builder.clause_key(clause, builder._register(sentence))
        held.setdefault(key, []).append(clause)
    validated = 0
    for item in templates:
        key = (
            item["predicate_class"], tuple(item["role_set"]), item["polarity"],
            item["tense"], item["register"],
        )
        clauses = held.get(key, ())
        assert clauses, "template has no matching held-aside train frame"
        passed = False
        for clause in clauses:
            sentence = builder._instantiate(item["template"], clause)
            if sentence is None:
                continue
            checks = verify_sentence(clause, sentence)
            if checks["roundtrip"]["passed"] and checks["term_lineage"]["passed"]:
                passed = True
                break
        assert passed, "shipped template failed held-aside round trip or term-lineage check"
        validated += 1
    return validated


def _verify_generation(sentences: list[str]) -> int:
    for sentence in sentences:
        parsed = _readable(sentence)
        if parsed is None:
            continue
        view, clause = parsed
        agents = [role for role in clause.roles if role.name == "agent"]
        if len(agents) != 1 or len(clause.roles) < 3:
            continue
        surfaces = set()
        for variant_index in range(8):
            generated = generation._sentences_for_ids(
                view, (clause.id,), "plain", "demo", variant_index=variant_index,
            )
            if isinstance(generated, list) and generated:
                candidate = generated[0]
                assert candidate.checks["roundtrip"]["passed"]
                assert candidate.checks["term_lineage"]["passed"]
                assert candidate.projection == projection(clause)
                surfaces.add(candidate.text)
            else:
                break
        template_texts = list(dict.fromkeys(
            candidate.text for candidate in generation._corpus_variants(clause)
            if candidate.style == "plain"
        ))
        for offset, template_text in enumerate(template_texts):
            generated = generation._sentences_for_ids(
                view, (clause.id,), "plain", "demo", variant_index=offset,
            )
            assert isinstance(generated, list) and generated
            assert generated[0].text == template_text
            assert generated[0].checks["roundtrip"]["passed"]
            assert generated[0].checks["term_lineage"]["passed"]
            surfaces.add(generated[0].text)
        if len(surfaces) >= 3 and template_texts:
            return len(surfaces)
    raise AssertionError("no common frame produced three distinct verified variants")


def _sample_from_corpus() -> tuple[list[str], list[str]] | None:
    corpus_dir = os.environ.get("VERA_CORPUS_DIR")
    if not corpus_dir:
        return None
    sample = list(builder.iter_train_sentences(corpus_dir, 20000))
    if len(sample) < 2:
        return None
    # The final fifth stays out of the builder and is used only for checking.
    split_at = max(1, len(sample) * 4 // 5)
    return sample[:split_at], sample[split_at:]


def main() -> int:
    corpus_sample = _sample_from_corpus()
    if corpus_sample is None:
        # The restricted unit worktree does not always include the external
        # corpus. These hand-written source sentences exercise the same reader
        # and checker path without being stored as corpus provenance.
        training, held_aside = list(SYNTHETIC_TRAIN), list(SYNTHETIC_HELD_ASIDE)
    else:
        training, held_aside = corpus_sample

    first = builder.build_index(training)
    second = builder.build_index(training)
    serialized = builder.serialize(first)
    assert serialized == builder.serialize(second), "build output is not deterministic"
    assert len(serialized.encode("utf-8")) < 5 * 1024 * 1024, "template index exceeds 5 MB"
    sample_templates = first["templates"]
    assert sample_templates, "no verified role-slot templates were built"
    checked = _validate_templates(sample_templates, held_aside)
    assert checked == len(sample_templates), "not every built template passed held-aside checks"

    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert artifact.get("schema_version") == 1 and isinstance(artifact.get("templates"), list)
    assert ARTIFACT.stat().st_size < 5 * 1024 * 1024, "shipped template table exceeds 5 MB"
    _validate_templates(artifact["templates"], held_aside)

    # Exercise the runtime table with the shipped artifact. If no corpus
    # table was built in this restricted checkout, use this demo's freshly
    # rebuilt in-memory table without changing the file on disk.
    generation._SURFACE_VARIANT_DATA = artifact if artifact["templates"] else first
    generated_count = _verify_generation(held_aside)
    assert generated_count >= 3
    print(
        "DEMO CHECKS: "
        f"train_sentences={len(training)} held_aside_sentences={len(held_aside)} "
        f"built_templates={len(sample_templates)} checked_templates={checked} "
        f"shipped_templates={len(artifact['templates'])} generated_variants={generated_count}"
    )
    print("DEMO OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
