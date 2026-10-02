# Verifier agents: injection and authority review

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| VA-I1 | robustness | Build a brief with claimant ID `reviewer` and verifier ID `revіewer` (the second spelling contains Cyrillic `і`, U+0456), using an otherwise valid independent-verifier spec and a separate session. | Reject or escalate: the verifier must be a distinct agent from the claimant. | `build_verifier_brief` accepts the verifier ID and creates a brief. The reproducer is marked xfail. |
| VA-I2 | crash | `parse_verdict([{"type": "VERDICT", "result": [], "evidence_ref": "test:check"}])` | Raise `ValueError` for unverified/malformed output, as stated by the parser contract. | A `TypeError` for an unhashable list escapes the parser. The reproducer is marked xfail. |

## What held

- Brief fields containing prompt-injection text, nested quotes, and Unicode remain serialized as JSON under the explicit untrusted-data instruction. Extra instruction text beside the ASK_VERIFIER spec is not copied into the brief.
- Exact claimant/verifier ID reuse, claimant-session reuse, a claimant/spec mismatch, unsupported templates, and an oversized brief are rejected.
- The parser accepts a single valid structured PASS or FAIL verdict. It rejects multiple events, prose around the JSON, duplicate keys, extra verdict fields, vague references, and malformed or traversal-style references.
- The acceptance command completed with **19 passed and 2 xfailed** in **0.17 seconds**.

## What I did not cover

- I did not exercise `run_verifiers` through a complete active acceptance record and adapter session, including polling, timeout, stop, disagreement, or conductor re-check behavior.
- I did not test a broad Unicode confusable corpus or every Unicode formatting/control character.
- Evidence references were checked for parser syntax only; this review did not confirm that referenced tests, records, files, or artifacts actually exist.
