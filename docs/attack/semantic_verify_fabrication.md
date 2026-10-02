# Semantic verifier fabrication and provenance attack

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| F1 | wrong-ANSWER | Source: `太郎は花子を見た。いや、次郎は花子を見た。` Question: `何が花子を見た？` Submit a valid replayed proof for each actor. | The correction marker retracts the earlier actor claim; only `次郎` should be an answer. | `Checker.audit` returned both `太郎` and `次郎` in two fresh runs. `Checker.gate` also accepted both proposals with replayed proofs. The regression is marked xfail in the attack test. |

## What held

- The original event clause licensed its source roles. Swapping agent and patient together with their spans was rejected.
- A negative source could not be relabelled positive, and a shortened event sentence span was rejected.
- Opposing positive and negative claims produced `Conflict` rather than an answer.
- Proof replay returned the actor bound by the source. Changing the projected answer or splicing a clause from another sovereign was rejected.
- The gate accepted a complete proof-backed proposal and rejected an omitted answer.

## What I did not cover

I did not exercise record version metadata, other correction markers, quotation and normative cases, measure clauses, or guarded exceptions. The correction finding is limited to the Japanese `いや` form above.

## Run

Acceptance command: `/Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_semantic_verify_fabrication.py`

Result: **10 passed, 1 xfailed**. The correction repro was also run twice with fresh checker instances before being recorded.
