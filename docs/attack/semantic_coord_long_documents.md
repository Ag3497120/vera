# Long and multi-document coordination attack

Scope: direct calls to the permitted helpers in `verantyx/semantic_coord.py`, using constructed token tuples. The module contract licenses only renyō predicates followed by an optional `て`/`で` and comma, and shares the first clause's は-topic only when a later clause has no は/が phrase.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| COORD-01 | ungrounded | `coordination_ok(tagged, [0, 3])` for `調べ(連用形)・て(助詞)・から(接続助詞)・送る(終止形)`; separately reproduced with `調べ(連用形)・で(助詞)・しかし(接続詞)・送る(終止形)` | `False`: `から` and `しかし` are outside the permitted te/renyō separators. | `True` for both examples. The coordinator consumes `て`/`で`, then checks the separator gap without examining the connective before the next predicate. |

The defect remains visible as a non-strict xfail in the attack tests. Both reproductions are in that test, so the reported result is confirmed twice.

## What held

- A single predicate and a non-renyō non-final predicate were refused. Direct `が`, `ので`, `から`, `ば`, `たら`, and `と` separators were also refused.
- A valid two-link chain using `て` and comma was accepted. Its clause boundary and first-topic span matched the token spans, and a later clause's own が-marker was detected within that clause.
- Across 48 independently constructed sentences with a repeated entity and alternating first-clause は/が markers, topic spans and later own-subject checks stayed local to each call.
- A constructed 256-predicate chain preserved the coordination result, first-topic span, and final clause boundary.
- A complete particle-bounded name passed `phrase_bounded`; a name fragment adjacent to another noun token was rejected.
- Exact duplicate inputs returned the same coordination result. Replacing the te separator with `ので` made the near-duplicate input fail the coordination check.

## Run

Acceptance command result: **16 passed, 1 xfailed** in 0.09 seconds. The xfail is COORD-01.

## What I did not cover

- End-to-end reader, route, or answer behavior; this module accepts one sentence's tokens and does not aggregate documents or produce answers.
- Behavior of a live morphological tagger, corpus documents, or long-document ingestion. Inputs here were constructed token tuples.
- Invalid predicate indices, malformed token tuples, or performance beyond the 256-predicate constructed chain.
- Sealed, heldout, or development data.
