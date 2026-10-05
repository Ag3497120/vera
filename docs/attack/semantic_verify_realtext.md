# Semantic verifier: real-text stress attempt

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| ENV-1 | robustness | Call `tools.round5a_route_tune.load(10, 1)` using the unit's train-lead loader. | Return train-split lead examples for verifier replay. | The loader raised `FileNotFoundError` for its configured `jawiki_leads.full.jsonl` before returning examples; 0 leads were available. This is an input-availability finding, not a verifier defect. |

No verifier defect was reproduced in the clause-licensing checks. The real-lead rates for wrong answers, ungrounded outputs, crashes, and hangs are **not measurable** because no lead text was returned by the loader.

## What held

The acceptance run exercised clause licensing with short constructed Japanese statements, not corpus leads. The verifier licensed 5 supported clauses: an identity statement, a positive past event, a negative past event, and two separate identity statements. It rejected 5 altered source/clause cases: a changed role literal, a shortened role span, a sentence span missing punctuation, a body span missing punctuation, and spans reused after the source text changed. An interrogative identity sentence produced no clauses to license.

Acceptance command:

```text
VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_semantic_verify_realtext.py
```

Result: **10 passed in 0.14s**.

## What was not covered

- No real Wikipedia lead was evaluated, so there are no real-text crash, hang, wrong-answer, or ungrounded-output rates.
- The short source strings in the tests are constructed smoke inputs; they are not represented as Wikipedia quotations or train examples.
- This run checked source-clause licensing and its span/role boundaries. It did not exercise end-to-end proof proposals through `Checker.gate`.
- Long paragraphs, mixed-language text, and source-volume limits were not measured.
