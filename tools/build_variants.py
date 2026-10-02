#!/usr/bin/env python3
"""Build checked, slot-based surface templates from train corpus sentences.

Only the three named train families are read.  The output contains templates
with semantic role slots and aggregate counts; source sentences are never
written to the artifact.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Iterator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from verantyx.semantic_realize import Refused, realize_clause, verify_sentence
from verantyx.semantic_reader import document_view

FAMILIES = frozenset(("narrative", "conversation", "paraphrase_entail"))
OUTPUT = ROOT / "verantyx" / "data" / "realize_variants.json"
_REGISTER_POLITE = re.compile(r"(?:です|ます|ません|でした|ました|ませんでした)[。！？!?]*$")
_SKIP_MARKERS = ("sealed", "heldout", "dev", "fixtures.jsonl", "fixture", "verantyx-vera-alpha")


def _record_text(record: Any) -> tuple[str, str, str] | None:
    if not isinstance(record, dict):
        return None
    sources = [record]
    for name in ("item", "example", "data"):
        nested = record.get(name)
        if isinstance(nested, dict):
            sources.append(nested)
    split = next((str(obj.get("split", "")).strip().casefold() for obj in sources
                  if obj.get("split") is not None), "")
    family = next((str(obj.get("family") or obj.get("source_family") or obj.get("dataset") or "")
                   .strip().casefold().replace("-", "_") for obj in sources
                   if obj.get("family") or obj.get("source_family") or obj.get("dataset")), "")
    sentence = next((obj.get("sentence") or obj.get("text") or obj.get("input")
                     for obj in sources if obj.get("sentence") or obj.get("text") or obj.get("input")), None)
    if split != "train" or family not in FAMILIES or not isinstance(sentence, str):
        return None
    sentence = sentence.strip()
    return (family, split, sentence) if sentence else None


def iter_train_sentences(corpus_dir: str | os.PathLike[str], limit: int | None = None) -> Iterator[str]:
    """Yield eligible train sentences in deterministic file and line order."""
    root = Path(corpus_dir)
    if not root.is_dir():
        raise FileNotFoundError(f"corpus directory is unavailable: {root}")
    paths = []
    for path in root.rglob("*.jsonl"):
        relative_parts = {part.casefold() for part in path.relative_to(root).parts}
        if any(marker in part for marker in _SKIP_MARKERS for part in relative_parts):
            continue
        paths.append(path)
    emitted = 0
    for path in sorted(paths, key=lambda item: item.as_posix()):
        with path.open("r", encoding="utf-8") as source:
            for line in source:
                if not line.strip():
                    continue
                try:
                    row = _record_text(json.loads(line))
                except (json.JSONDecodeError, TypeError):
                    continue
                if row is None:
                    continue
                yield row[2]
                emitted += 1
                if limit is not None and emitted >= limit:
                    return


def _register(sentence: str) -> str:
    return "polite" if _REGISTER_POLITE.search(sentence.rstrip()) else "plain"


def clause_key(clause: Any, register: str) -> tuple[str, tuple[str, ...], str, str, str]:
    """Return the closed structural key used by both build and runtime."""
    return (
        f"{getattr(clause, 'rule', '')}:{getattr(clause, 'predicate', '')}",
        tuple(sorted(str(role.name) for role in getattr(clause, "roles", ()))),
        str(getattr(clause, "polarity", "")),
        str(getattr(clause, "time", "") or "none"),
        register,
    )


def _key_dict(key: tuple[str, tuple[str, ...], str, str, str]) -> dict[str, Any]:
    predicate_class, role_set, polarity, tense, register = key
    return {
        "predicate_class": predicate_class,
        "role_set": list(role_set),
        "polarity": polarity,
        "tense": tense,
        "register": register,
    }


def _template_for(clause: Any) -> str | None:
    span = getattr(clause, "span", None)
    roles = tuple(getattr(clause, "roles", ()))
    if span is None or not span.text or not roles:
        return None
    replacements = []
    for role in roles:
        role_span = getattr(role, "span", None)
        if (role_span is None or role_span.source != span.source
                or role_span.start < span.start or role_span.end > span.end
                or role_span.end <= role_span.start
                or role_span.end - role_span.start != len(role_span.text)):
            return None
        lo, hi = role_span.start - span.start, role_span.end - span.start
        if span.text[lo:hi] != role_span.text:
            return None
        replacements.append((lo, hi, "{" + str(role.name) + "}"))
    replacements.sort()
    for left, right in zip(replacements, replacements[1:]):
        if left[1] > right[0]:
            return None
    text = span.text
    for start, end, slot in reversed(replacements):
        text = text[:start] + slot + text[end:]
    slots = re.findall(r"\{([a-z_]+)\}", text)
    if sorted(slots) != sorted(str(role.name) for role in roles):
        return None
    return text


def _instantiate(template: str, clause: Any) -> str | None:
    values = {str(role.name): role.span.text for role in getattr(clause, "roles", ())}
    slots = re.findall(r"\{([a-z_]+)\}", template)
    if not slots or set(slots) != set(values):
        return None
    output = re.sub(r"\{([a-z_]+)\}", lambda match: values.get(match.group(1), ""), template)
    if "{" in output or "}" in output:
        return None
    return output


def read_one(sentence: str) -> tuple[Any, dict[str, Any]] | None:
    """Return the sole supported clause only when both realizer checks pass."""
    try:
        view = document_view({"corpus": sentence})
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
    return clause, checks


def build_index(sentences: Iterable[str]) -> dict[str, Any]:
    """Build deterministic template counts from verified input sentences."""
    counts: Counter[tuple[tuple[str, tuple[str, ...], str, str, str], str]] = Counter()
    input_count = 0
    readable_count = 0
    for sentence in sentences:
        if not isinstance(sentence, str) or not sentence.strip():
            continue
        input_count += 1
        parsed = read_one(sentence.strip())
        if parsed is None:
            continue
        clause, _checks = parsed
        register = _register(sentence)
        template = _template_for(clause)
        if template is None:
            continue
        reconstructed = _instantiate(template, clause)
        # The extraction itself is checked. It may enter the index only if it
        # reproduces the source's independently parsed projection and terms.
        checks = verify_sentence(clause, reconstructed or "")
        if not reconstructed or not checks["roundtrip"]["passed"] or not checks["term_lineage"]["passed"]:
            continue
        readable_count += 1
        counts[(clause_key(clause, register), template)] += 1

    templates = []
    for (key, template), count in sorted(
            counts.items(), key=lambda item: (item[0][0], item[0][1])):
        templates.append({**_key_dict(key), "template": template, "count": count})
    return {
        "schema_version": 1,
        "provenance": {
            "split": "train",
            "input_sentences": input_count,
            "verified_sentences": readable_count,
            "template_count": len(templates),
        },
        "templates": templates,
    }


def serialize(index: dict[str, Any]) -> str:
    return json.dumps(index, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus-dir", default=os.environ.get("VERA_CORPUS_DIR"))
    parser.add_argument("--limit", type=int, default=None, help="maximum eligible train sentences to read")
    args = parser.parse_args(argv)
    if not args.corpus_dir:
        parser.error("set VERA_CORPUS_DIR or pass --corpus-dir")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    try:
        index = build_index(iter_train_sentences(args.corpus_dir, args.limit))
    except OSError as exc:
        parser.error(str(exc))
    serialized = serialize(index)
    if len(serialized.encode("utf-8")) >= 5 * 1024 * 1024:
        parser.error("realize_variants.json must remain under 5 MB")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(serialized, encoding="utf-8")
    print(json.dumps(index["provenance"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
