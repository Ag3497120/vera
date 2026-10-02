# Verifier agents fabrication and provenance attack

Scope: `verantyx/verifier_agents.py` brief construction, verdict parsing, and the data passed to the verification-record boundary. The acceptance command completed with **13 passed, 1 xfailed**.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| VAF-01 | crash | Call `parse_verdict([{"type":"VERDICT","result":[],"evidence_ref":"test:acceptance-check"}])`. | The parser contract says malformed output raises `ValueError` as unverified. | Membership-testing the list result against the allowed-result set raises `TypeError: unhashable type: 'list'`. The reproducer is retained as a non-strict xfail. |

## What held

- Brief fields preserve request text as JSON data and include the stated claimant and verifier identities.
- Brief construction rejects a verifier using the claimant identity or claimant session, and rejects a claimant that does not match the request.
- Verdict parsing accepts a single structured verdict and rejects multiple events, duplicate JSON keys, extra fields, path traversal references, and vague references.
- The run path abstains before starting an adapter when the active acceptance subject does not match the requested target.
- With two passing adapter events, the record boundary receives the corresponding verifier IDs, sessions, results, and evidence references in stable sorted order.

## Not covered

- The run-path record checks use a small `ProjectFrame` subclass that captures the call; they do not exercise persisted `Memory` records or the real `verify_claim` acceptance path.
- Tests check reference syntax and propagation, not whether external files, commands, artifacts, or record references actually exist or support the verdict.
- Failure, timeout, polling exhaustion, adapter exceptions, and superseded-record behavior were not exercised.
- No external or restricted datasets were used.
