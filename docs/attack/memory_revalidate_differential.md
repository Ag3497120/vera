# Memory revalidation differential attack

## Findings

The independent reference checks and the implementation agreed across the tested scope. No defect was identified, so there are no issue entries:

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| — | — | — | — | — |

## What held

- Matching and mismatching SHA-256 witnesses returned `FRESH` and `STALE`; text witnesses followed whether the requested text was present. Missing or unavailable local files were `STALE`.
- Testimony, unknown witness kinds, and malformed non-dictionary witnesses were `UNVERIFIABLE`. A stubbed git runner's zero and nonzero return codes mapped to `FRESH` and `STALE`; runner exceptions mapped to `UNVERIFIABLE`.
- The cache reused a result before its TTL expired and rechecked at the expiry boundary. A zero TTL or cache size disabled caching, and a bounded cache evicted the least recently used entry. Mapping insertion order did not change a witness cache key.
- The read view excluded stale records while retaining fresh and unverifiable records, and left the source record list unchanged.

The required acceptance command passed: **24 tests passed in 0.16 seconds**.

## What I did not cover

- I did not exercise full `Memory.ask` or `Memory.ask_about` answer construction or real typed memory records; the view check used minimal records to isolate revalidation behavior.
- Git checks used a deterministic stub runner, so I did not validate a real repository or commit object.
- I did not cover concurrent callers, unusual custom Python objects in witnesses, or filesystem changes racing with a read.
- No wrong-answer or fabrication claim was made: answer construction was outside this differential scope.
