# Semantic measure limits attack

## Findings

No defect reproduced in the tested cases. The table records the explicit numeric input boundary exercised by the attack tests.

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| M-01 | robustness | `Aは` + 128 `9` digits + `kg`; repeat with 129 digits | Preserve the 128-digit quantity exactly; decline the over-budget quantity without raising | 128 digits parsed with all digits retained; 129 digits returned `None` |

No `xfail` was needed. No wrong answer or fabrication was observed.

## What held

- Decimal scale and digits were retained for a long fractional amount.
- Empty, incomplete, and trailing-junk sentences were declined; the shared head noun was attached to both parsed measures.
- Reordering two segments kept each entity paired with its own value.
- The supported sum question built a Join, distinct-entity Filter, and Sum chain. An unrecognized question returned `None` without changing the builder.
- Repeating the same read produced the same clauses and deterministic IDs. Two reader threads parsed 80 inputs successfully.
- After 300 discarded reads, the live and peak traced allocations stayed below the test's 512 KiB and 2 MiB bounds.
- A sentence containing 256 short measure segments was fully consumed in order.

The acceptance run was:

```text
/Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_semantic_measure_limits.py
16 passed in 0.17s
```

## What was not covered

- Execution of a completed measure plan against stored clauses, including numerical conversion or comparison results.
- Same/different and compare question plans beyond their shared parser construction path.
- Translation of `None` into caller-level typed refusals.
- Inputs larger than the 256-segment case, sustained concurrent load, or long-lived process memory behavior.
- Any semantic modules other than the measure reader and request builder.
