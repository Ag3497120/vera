# Memory lessons limits attack

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| MLL-1 | crash | `LessonIndex([{"id": "bad", "kind": "LESSON", "slots": {"situation": "broken route"}, 1: "unexpected key"}])` | Refuse or ignore a malformed record without raising. | `TypeError: '<' not supported between instances of 'int' and 'str'` while the constructor sorts record items. Kept visible as a non-strict xfail. |

No wrong-answer or ungrounded-answer defect was observed in this run.

## What held

The acceptance run reported **10 passed and 1 xfailed** in **0.22 seconds**. The passing cases held for empty and non-LESSON inputs, exact trigger isolation, order independence, duplicate-ID de-duplication, superseded-record exclusion, repeated lookups, constructor input isolation, concurrent readers, and retained memory across repeated lookups. The large-index case built and queried **8,000 distinct triggers**. The repeated-lookup memory check made **5,000 calls** and retained less than its **256,000-byte** bound.

The malformed mixed-key crash was also reproduced directly with the minimal input in the findings table.

## Not covered

- The injected asker/resolver path was not exercised; these checks used exact lookup or abstention without an asker.
- Inputs larger than the **8,000-trigger** case, extremely long trigger text, and a formal runtime or memory budget were not measured.
- The malformed-input check covers mixed record-key types only; other invalid field types and custom collection behavior were not explored.
- No wrong-answer behavior is claimed beyond the constructed records and lookups in these tests.
