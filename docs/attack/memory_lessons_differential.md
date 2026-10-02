# Memory lesson index differential check

The independent reference implementation covers plain lists of dictionary records and canonical lowercase trigger labels. It applies the visible contract for LESSON filtering, required IDs and situation slots, supersession, duplicate IDs, and ID-ordered results. Generated queries matched that reference.

## Findings

| ID | Severity (wrong-ANSWER, ungrounded, crash, hang, robustness) | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |

No disagreement or defect was reproduced in the covered cases, so there are no findings and no xfail cases.

## What held

- The generated exact-lookup cases matched the independent reference for each known trigger and an unknown trigger.
- LESSON filtering, missing required fields, explicit supersession, a `supersedes` slot, duplicate IDs, and ID ordering behaved as asserted.
- An unmatched query without an asker, an empty query, and a non-string query returned no lessons.
- Clearing the returned list did not remove a lesson from the index.

The acceptance run completed with **10 passed** in **0.12 seconds**.

## Not covered

- The differential generator uses canonical lowercase labels; it does not independently model punctuation, case, Unicode, or spacing normalization in `memory_frame`.
- Resolver behavior with an injected asker, including disagreements, ties, invalid choices, and what context reaches the asker, was not exercised.
- Construction from a `Memory` object, non-list record collections, and malformed nested values beyond the checked missing fields were not covered.
- No wrong-answer or fabrication finding was established outside these bounded checks.
