#!/usr/bin/env python3
"""Reread-match evaluation of `vera realize` (W3-d1). No network, no model call.

Copied from W10-f03's tools/fusion/evaluate_model.py (the parts named in artifacts/w3-d1/w10f03_copy.txt): `_identity`, `_mismatch_labels`, `_realize_via_cli`
(now with `--forms`). NOT copied: the learning/generation plumbing (`make_pairs` import, `_heldout_candidates`, the Ollama `evaluate`).

The definition of a match (K312 for sentences): the sentence that `vera realize` writes for a token line is read again with the SAME placement, and the
identity of that reread (the cell key of every cross, and the relations) is the identity of the original text read with the placement.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


def _identity(cross_reading: Any) -> dict[str, Any] | None:
    from verantyx import event_cross, observe

    if isinstance(cross_reading, event_cross.EventCross):
        return {"cell_keys": [observe.cell_key_of(cross_reading)], "relations": []}
    if cross_reading.status != "CROSSED":
        return None
    return {
        "cell_keys": [observe.cell_key_of(cross) for cross in cross_reading.crosses],
        "relations": [
            {key: relation[key] for key in ("type", "from", "to", "head") if key in relation}
            for relation in cross_reading.relations
        ],
    }


def _mismatch_labels(expected: Any, predicted: Any) -> list[str]:
    from verantyx import event_cross

    labels: list[str] = []
    if expected is None or predicted is None:
        return labels
    expected_crosses = expected.crosses if isinstance(expected, event_cross.CrossReading) else (expected,)
    predicted_crosses = predicted.crosses if isinstance(predicted, event_cross.CrossReading) else (predicted,)
    if not expected_crosses or not predicted_crosses:
        return labels
    expected_first, predicted_first = expected_crosses[0], predicted_crosses[0]
    if expected_first.center.get("predicate") != predicted_first.center.get("predicate"):
        labels.append("PREDICATE_MISMATCH")
    expected_roles, predicted_roles = set(expected_first.arms), set(predicted_first.arms)
    if expected_roles - predicted_roles:
        labels.append("ARM_MISSING")
    type_mismatch = False
    for role in expected_roles & predicted_roles:
        expected_arm, predicted_arm = expected_first.arms[role], predicted_first.arms[role]
        if (expected_arm.agreement.to_dict() != predicted_arm.agreement.to_dict()
                or [f.place.types for f in expected_arm.fillers] != [f.place.types for f in predicted_arm.fillers]):
            type_mismatch = True
    if type_mismatch:
        labels.append("TYPE_MISMATCH")
    if _identity(expected) != _identity(predicted):
        labels.append("CROSS_MISMATCH")
    return labels


def _realize_via_cli(tokens: str, lang: str, placement: Path, forms: Path | None = None) -> dict[str, Any]:
    """Route model output through the same public CLI entry used by Vera users."""
    command = [
        sys.executable, "-m", "verantyx.cli", "realize", "-",
        "--lang", lang, "--placement", str(placement),
    ]
    if forms is not None:
        command += ["--forms", str(forms)]
    try:
        completed = subprocess.run(
            command, input=tokens + "\n", check=False,
            capture_output=True, text=True, timeout=30,
        )
    except subprocess.TimeoutExpired:
        return {"status": "ABSTAINED", "reason": "REALIZE_CLI_TIMEOUT"}
    except OSError as exc:
        return {"status": "ABSTAINED", "reason": "REALIZE_CLI_UNAVAILABLE",
                "detail": type(exc).__name__}
    if completed.returncode != 0:
        # W3-d1: a refused forms table is a typed answer (exit code 2 with a JSON body), not a failure of the entry.
        try:
            body = json.loads(completed.stdout)
        except (json.JSONDecodeError, TypeError):
            body = None
        if completed.returncode == 2 and isinstance(body, dict) and str(body.get("reason", "")).startswith("FORMS_"):
            return body
        return {"status": "ABSTAINED", "reason": "REALIZE_CLI_FAILED",
                "returncode": completed.returncode}
    try:
        result = json.loads(completed.stdout)
    except (json.JSONDecodeError, TypeError):
        return {"status": "ABSTAINED", "reason": "REALIZE_CLI_BAD_OUTPUT"}
    if not isinstance(result, dict) or not isinstance(result.get("status"), str):
        return {"status": "ABSTAINED", "reason": "REALIZE_CLI_BAD_OUTPUT"}
    return result


def reread_match(text: str, tokens: str, *, placement: str | Path, lang: str = "ja",
                 forms: str | Path | None = None) -> dict[str, Any]:
    """Does the sentence `vera realize` writes for `tokens` read, with the same placement, as the original `text` does?

    {"status": "MATCH" | "MISMATCH" | "NOT_REALIZED" | "SOURCE_NOT_CROSSED", ...}. A mismatch lists the labels of `_mismatch_labels`. Nothing is guessed:
    a sentence that is not produced is NOT_REALIZED, never a mismatch."""
    from verantyx import event_cross, semantic_read

    path = str(placement)
    source = event_cross.build_crosses(semantic_read.read(text, lang, placement=path), event_cross.default_lookup(path))
    source_identity = _identity(source)
    if source_identity is None:
        return {"status": "SOURCE_NOT_CROSSED", "source_status": source.status}
    realized = _realize_via_cli(tokens, lang, Path(path), Path(forms) if forms is not None else None)
    if realized.get("status") != "REALIZED":
        return {"status": "NOT_REALIZED", "realize_status": realized.get("status"), "reason": realized.get("reason"),
                "detail": realized.get("detail")}
    sentence = realized["text"]
    reread = event_cross.build_crosses(semantic_read.read(sentence, lang, placement=path), event_cross.default_lookup(path))
    reread_identity = _identity(reread)
    if reread_identity is not None and reread_identity == source_identity:
        return {"status": "MATCH", "text": sentence}
    return {"status": "MISMATCH", "text": sentence, "labels": _mismatch_labels(source, reread),
            "reread_status": reread.status}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Count reread matches of `vera realize` on a JSONL of {text, tokens}")
    parser.add_argument("input", type=Path, help="JSONL with one {\"text\", \"tokens\"} object per line")
    parser.add_argument("--placement", required=True, type=Path)
    parser.add_argument("--lang", default="ja")
    parser.add_argument("--forms", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None, help="write the per-row results as JSONL")
    args = parser.parse_args(argv)
    counts: Counter[str] = Counter()
    rows = []
    for line in args.input.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        result = reread_match(row["text"], row["tokens"], placement=args.placement, lang=args.lang, forms=args.forms)
        counts[result["status"]] += 1
        rows.append({"text": row["text"], **result})
    summary = {"rows": len(rows), "counts": dict(sorted(counts.items()))}
    if args.out is not None:
        args.out.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
