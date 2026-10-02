# Memory merge injection review

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| None | — | No defect reproduced by the targeted cases | Merge and inspection follow the documented typed-event contract | No mismatch was observed; the targeted run reported 12 passed. |

## What held

- Instruction text in document records, question events, agent messages, and nested quoted or Unicode payloads remained payload data during merge.
- Prose that mentioned superseding a record, including a Unicode-confusable operation name, did not create a supersession link.
- Conflicting instruction-bearing values produced a typed `CONFLICT` containing both record IDs and values; neither value was selected.
- A repeated record ID with different record data was rejected as a collision instead of selecting one version.
- Reversing the merge inputs and merging the tested inputs in stages produced the same canonical event union.
- Instruction prose did not bypass rejection of dangling supersession references or cycles.

## What I did not cover

`memory_merge.py` merges typed events and inspects active records and conflicts; it does not implement authorization or escalation decisions. These tests therefore do not establish how a caller handles the merged payloads, authenticates writers, or validates which writers may emit structured `supersede` events. I did not inspect callers or other modules, test `merge_files` or malformed JSONL input, or measure behavior on large logs. I also did not use network, heldout, sealed, or development data.

## Run

The specified targeted pytest command completed with **12 passed**.
