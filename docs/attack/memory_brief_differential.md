# Memory brief differential review

## Findings

The requested acceptance run found no disagreements in the covered cases, so there are no defect reproducers or xfails.

| ID | Severity (`wrong-ANSWER`, `ungrounded`, `crash`, `hang`, `robustness`) | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| — | — | No discrepancy observed | Reference and compiler agree in the covered cases | Reference and compiler agree in the covered cases |

## What held

- An empty active memory returns an empty brief. Invalid budgets, including `bool`, are rejected.
- A record is rendered only when its sentence is present, its kind/state is eligible, and the public question result names that record as a source. Other active, non-superseded record IDs remain in the dropped-ID line.
- Superseded records are excluded. Closed tasks are not rendered and remain accounted for as dropped records.
- Focus matching uses NFKC normalization and case folding. Matching records sort ahead of others, followed by kind priority, timestamp, and ID.
- The renderer measures Python string length, and the tested Unicode brief fits its exact budget.
- The independent reference agreed with the compiler across 60 deterministic generated cases spanning the supported kinds, task states, focus values, source availability, supersession, and budgets.
- Unsupported records were not emitted as answer lines in the tested source-mismatch case.

The acceptance command completed with **10 passed in 0.07s**. There were no xfails.

## What was not covered

- The tests use a small fake typed-memory interface. They do not exercise the actual memory store's freshness, retrieval, or source-generation behavior.
- Malformed records, duplicate IDs, unusual non-string slot values, and concurrent mutation were not covered.
- No broader test suite was run, and the compiler module was not changed.
