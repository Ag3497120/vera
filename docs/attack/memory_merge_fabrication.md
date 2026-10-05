# Memory merge fabrication attack

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| F1 | robustness | Merge the same write from both logs alongside a distinct write, swapping the log order. | Exact duplicate writes collapse, and merge order does not change the canonical union. | Held: one copy of each record was returned in either order. |
| F2 | robustness | Merge two write events with the same record ID and different values. | Reject the ID collision rather than attributing one value to that ID. | Held: `merge_logs` raised `ValueError` for the collision. |
| F3 | robustness | Give one subject and attribute two distinct active values. | Report a typed conflict with both source IDs and their corresponding values; do not choose one. | Held: the conflict carried both IDs and values in ID order. |
| F4 | robustness | Supersede an old value, while another active record for that property disagrees with the replacement. | Exclude the superseded record from active values and report only the active records. | Held: the conflict named the replacement and the other active record; the old value was absent. |
| F5 | robustness | Merge a record whose value is `not approved` and compare it with an `approved` record. | Preserve the source negation in the record and conflict values. | Held: the exact negated string remained present. |
| F6 | robustness | Use role typed subject/value objects in conflicting records, and separately supply a record missing its attribute slot. | Preserve role and entity structure; do not invent the missing property or combine distinct subjects. | Held: the structured objects were retained and the incomplete record produced no conflict. |
| F7 | robustness | Merge a supersession link before its target write arrives, then merge in the target. | Keep the partial link pending; reject active-state inspection while dangling, then retire the old record once complete. | Held: inspection raised while dangling; after the target arrived, only the replacement was active. |

No wrong-answer or fabrication defect was reproduced in these probes. The acceptance run reported **10 passed**.

## What held

The tested merge retained source record fields, including negation and structured role/entity values. Conflict inspection reported the active records supporting different values, did not combine different subjects, and omitted superseded values. Exact duplicate writes were deduplicated, and same-ID writes with differing record data were rejected.

## What I did not cover

These tests used in-memory event iterables. I did not exercise JSONL path parsing or `merge_files`, malformed event payloads, supersession cycle handling, or alias and unknown-operation events. The probes do not establish behavior outside these cases.
