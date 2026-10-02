#!/usr/bin/env python3
"""Recompute the real-question kind distribution independently of the report generator.

Reads $VERA_REAL_QUESTIONS and classifies each row with the same entry point the generator
(tools/real_questions_eval.py) uses: conductor.classify_question(question, options).
Prints row ID and kind only (never the question text), then per-kind counts and shares and the
OTHER rate, so the table in docs/REAL_QUESTIONS_2026-10-02.md can be recomputed from this output.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("VERA_CORPUS_ROOT", "/tmp/vera-empty-materials")

from verantyx import conductor  # noqa: E402


def main() -> int:
    path = os.environ.get("VERA_REAL_QUESTIONS")
    if not path:
        print("UNKNOWN_INPUT: VERA_REAL_QUESTIONS is not set", file=sys.stderr)
        return 2
    rows = []
    with open(path, encoding="utf-8") as stream:
        for line in stream:
            if line.strip():
                rows.append(json.loads(line))
    kinds = Counter()
    print("row kind")
    for index, row in enumerate(rows):
        kind = conductor.classify_question(row["question"], row["options"])
        kinds[kind] += 1
        print(f"R{index + 1:03d} {kind}")
    total = len(rows)
    print(f"total {total}")
    print("kind count share")
    for kind in conductor.QUESTION_KINDS:
        print(f"{kind} {kinds[kind]} {kinds[kind] / total:.1%}")
    unknown = sorted(set(kinds) - set(conductor.QUESTION_KINDS))
    if unknown:
        print(f"kinds outside QUESTION_KINDS: {unknown}")
    print(f"OTHER rate {kinds['OTHER']}/{total} ({kinds['OTHER'] / total:.1%})")
    print(f"verantyx module file: {conductor.__file__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
