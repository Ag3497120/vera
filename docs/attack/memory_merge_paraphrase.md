# Memory merge paraphrase attack

Scope: `verantyx/memory_merge.py`, using inline typed event mappings. The attack compares verdicts from structured subject, attribute, and value fields while varying surrounding surface text or changing typed values.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| MMP-01 | wrong-ANSWER | Two active `readiness` records for `Mika` with values `ready` and `all set` (`test_synonymous_slot_value_paraphrases_keep_same_verdict`) | Same-meaning value paraphrases retain the no-conflict verdict. | The assertion fails: the values are treated as distinct and produce a conflict for `r1`, `r2`. The xfailed reproducer was run twice. |
| MMP-02 | robustness | Equal typed slots with different polite/plain or word-order text in `surface` | Surface wording alone does not change the conflict verdict. | No conflict in either case; merging the surface variants is commutative. |
| MMP-03 | robustness | Same subject and attribute with values `2` and `3` | A meaning-changing numeric value produces a conflict. | One conflict lists both record IDs and values `(2, 3)`. |
| MMP-04 | robustness | Change one of two opposing records' subject from `Mika` to `Ren` | The entity change separates the records into different subject groups. | The shared-subject pair conflicts; the swapped-subject pair does not. |
| MMP-05 | robustness | Duplicate write with reordered keys; staged three-log supersession; reverse the order of a colliding ID; or add a supersession cycle | Canonical union and active state are order-stable; ID collisions and cycles are rejected. | The tested invariants held. |

MMP-01 is relative to this attack's semantic-paraphrase requirement. The module's documented merge logic compares typed values structurally, so it has no synonym normalization; this is the specific boundary exposed by the reproducer.

## What held

- Reordered JSON object keys on an otherwise identical write deduplicate.
- Writer order does not change the canonical merge for distinct records with surface variants.
- Surface wording outside the typed slots does not create or hide typed conflicts.
- Numeric changes and subject changes affect conflict grouping as expected.
- Staged supersession remains associative in the exercised three-log case; only the new record is active.
- A changed record under an existing ID and a supersession cycle raise `ValueError` in the exercised cases.
- Duplicate alias events are removed, and aliases do not affect conflict inspection.

## What was not covered

- No file-path or JSONL I/O cases, malformed input cases, or large-log performance cases.
- The synonym check covers only `ready` / `all set`; it does not establish broad language understanding or paraphrase coverage.
- No corpus or external data was used. The two targeted xfail runs reproduced MMP-01; the full acceptance run is recorded by the test command result.
