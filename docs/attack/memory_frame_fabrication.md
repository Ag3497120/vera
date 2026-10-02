# Memory frame fabrication attack

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| MF-FAB-01 | wrong-ANSWER (S1; reproduced twice) | Put `受付時間は平日である。` in a file; write `FACT(ルーター, 未読上限, 512)` with a `text_in_file` witness for only `受付時間`; ask about the router limit. A second case uses `部署の所在地は東京である。`, witness `東京`, and value `1024`. | A witness span must support the complete claim, or the memory must abstain. | Both writes were accepted with fresh witnesses. Both queries returned `ANSWER` with their respective unsupported values (`512` and `1024`), and each result listed the fabricated record's ID as its source. `check_witness` only establishes that the supplied substring exists; it does not bind the substring to the record's claim. |
| MF-FAB-02 | robustness | Write a valid witnessed fact with `supersedes="missing-record"`; catch `WriteRejected`; inspect active records. | A rejected write should leave the append-only log and active memory unchanged. | `WriteRejected` is raised, but the write event has already been appended; the newly written record remains active. |

## What held

- Empty memory returned `UNKNOWN_NO_EVIDENCE` with no values or source records.
- Incomplete slots, sentence delimiters, a missing required witness, and an unknown witness kind were rejected without adding a record.
- Noun normalization was reflected in `slots` and `normalized`, while the value slot remained intact.
- A text witness that became stale was reported as `STALE` and excluded from a fresh query.
- A valid supersession hid the old record and left the replacement active.
- JSONL reload preserved the record ID; when a query answered, its result mapped back to that record.
- Asking about a different entity did not return the stored fact as an answer.
- The closed-choice parser accepted an in-range index and `null`, and rejected out-of-range and malformed choices.

## Not covered

This attack did not cover swapped semantic roles, negation loss, alias adoption through a live asker, `file_sha256` or `git_commit` witnesses, or tampered event logs. No sealed, heldout, or development data was used.

## Run

Acceptance command result: **11 passed, 3 xfailed**. The two independent partial-span cases and the rejected-supersession side effect are retained as non-strict xfails so the defects remain visible while the suite passes.
