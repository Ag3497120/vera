# Verifier-agent paraphrase attack

Scope: `verantyx/verifier_agents.py` brief construction and typed verdict parsing. The tests use the module contract: brief fields are carried as untrusted JSON data, verdict results are exactly `PASS` or `FAIL`, and malformed/unverified verdict output raises `ValueError`.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| VA-P-01 | crash | Call `parse_verdict([{"type": "VERDICT", "result": [], "evidence_ref": "record:acceptance-17"}])` twice. | Malformed result is rejected as an unverified verdict with `ValueError`. | Both calls raise `TypeError` (`unhashable type: 'list'`) while checking membership in the accepted result set. Regression test is xfailed to keep the defect visible. |

## What held

- Polite/plain and reordered prompt text remained intact in `how_to_check`; the surrounding task, target, record, and identity fields stayed the same.
- Quotes and newlines round-tripped through the brief JSON payload, which is explicitly marked as untrusted data.
- Whitespace and key ordering in an `OTHER` JSON verdict did not alter the parsed verdict. The direct `VERDICT` event form produced the same typed result.
- Valid test, command, record, digest, and relative-file references were accepted without changing `PASS`; an explicit `FAIL` remained `FAIL`.
- Multiple verdict events, duplicate JSON keys, vague evidence references, and claimant/verifier identity reuse were rejected.

## What was not covered

- Natural-language semantic equivalence is not evaluated here. This module packages the verifier prompt and parses a typed result; these tests cannot establish that an independent verifier understands particle changes, number/entity substitutions, or meaning-changing paraphrases correctly.
- End-to-end `run_verifiers` behavior with an active acceptance record and real adapter sessions was not exercised.
- No wrong-answer or fabricated-evidence finding was observed.

The required acceptance command completed with 18 passed and 1 xfailed; the xfail reproduces VA-P-01 twice in one test. The run completed in under one second.
