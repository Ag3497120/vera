# Remedy limits attack

Scope: the public `remedy(result)` dictionary transformation in
`verantyx/remedy.py`. The expected results below follow its verdict contract
and remedy table. One field-propagation defect was reproduced and retained as
an xfail.

## Findings

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| RL-1 | robustness | `remedy({})` | Return an empty-verdict typed fallback with `needs_registration: None` and the no-remedy note. | Returned the typed fallback; no exception. |
| RL-2 | robustness | `NOT_ATTESTED` with a one-megabyte `terms` string | Preserve the supplied term without truncation and provide the known repair form. | Returned the full term and repair form. |
| RL-3 | robustness | Repeat calls for the same known refusal | Return equal forms and leave the input unchanged. | Repeated calls were equal; the input stayed unchanged. |
| RL-4 | robustness | Two threads repeatedly read different typed refusals | Each call stays associated with its own verdict and subject. | Both readers received their respective verdict and subject throughout the run. |
| RL-5 | robustness | `remedy({"verdict": "UNKNOWN_FUTURE_CASE", "subject": "topic"})` | Carry the truthy `subject` through, as promised by the function docstring. | Returned the typed unknown-verdict fallback but omitted `subject`; retained as an xfail. |

RL-1 through RL-4 are robustness observations. RL-5 is a reproducible
robustness defect in the unlisted-verdict branch. No wrong answer or fabricated
answer was observed.

## What held

- Empty verdicts returned the typed fallback. Unlisted verdicts also returned
  a typed fallback, but omitted `subject` (RL-5).
- Terminal verdicts and registered refusals were repeatable; registered
  output was idempotent.
- Insertion order did not affect results, and unrelated fields were not copied
  into a known remedy form.
- Falsey optional fields were omitted, while a large truthy field was carried
  intact.
- Two concurrent readers got independent results.

## What I did not cover

- End-to-end registration, ingestion, judge rebuilding, or verdict changes;
  this helper only formats a remedy for an existing result.
- Heap-growth and strict latency thresholds, which are not stable assertions
  for this small pure transformation.
- Non-dictionary inputs or objects with hostile `.get()` / string conversion
  behavior, outside the declared `Dict[str, Any]` input contract.
- Any data-backed or external workflow.

Acceptance command: `/Users/motonisihikoudai/vera-wiring/env/bin/python -B -m
pytest -q tests/attack/test_remedy_limits.py` with the unit's specified corpus,
bytecode, and import environment. The final run reported 9 passed and 1 xfailed.
