# Memory merge limits attack

Independent limits and determinism checks for `verantyx.memory_merge`.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| MM-01 | robustness | Call `merge_logs([], [])` repeatedly. | The union is empty and repeated calls are stable. | Each call returned `[]`. |
| MM-02 | robustness | Merge two mixed logs in both argument orders, with writes, aliases, a supersession event, and an unrelated event. | The result is a deterministic canonical union independent of argument order. | Both merge orders returned equal results. |
| MM-03 | robustness | Pass 4,000 unique writes as one iterator and the same writes in reverse order as the other. | Exact duplicate writes collapse, and the unique records are ordered by id. | The merge returned 4,000 writes, ordered from `r00000` through `r03999`. |
| MM-04 | robustness | Supply a colliding id, a two-edge partial supersession cycle, or a dangling link to `active_records`. | Invalid record identity, cycles, and incomplete active-state links are rejected with `ValueError`. | Each case raised `ValueError` with the corresponding collision, cycle, or dangling-reference message. |
| MM-05 | robustness | Give `conflicts` three active records for one subject and attribute, with two distinct values. | Return a typed conflict listing every supporting record id in id order, with values aligned to those ids. | Returned one `CONFLICT` with ids `r1`, `r2`, `r3` and values `fast`, `safe`, `safe`. |
| MM-06 | robustness | Run two concurrent readers, each merging the same 500-write input 20 times. | Every call returns the same deterministic result without modifying the shared input. | All 40 results matched the single-reader result; the input still contained 500 events. |
| MM-07 | robustness | Repeat a merge of 300 writes 30 times and sample retained allocations with `tracemalloc`. | Temporary merge state should not accumulate beyond the test's 512 KiB retained-growth bound. | The measured retained growth stayed below 512 KiB. |
| MM-08 | robustness | Merge two one-line JSONL files into a separate output, then read the output and try using an input as output. | The separate output round-trips as the canonical union; overwriting an input is rejected. | The output contained active ids `a`, `b` in order and matched `merge_logs`; reusing the left input raised `ValueError`. |

No defect reproductions were found, so the suite has no xfails.

## What held

- Merging was commutative for the mixed event case, associative across staged merges with a pending supersession link, and idempotent for exact duplicate events.
- Empty inputs remained empty; distinct records with the same id, supersession cycles, and dangling active-state references received typed `ValueError` refusals.
- Conflicts retained all active evidence ids and aligned values rather than selecting one value.
- The bulk, concurrent-reader, repeated-call allocation, and file round-trip checks passed.
- The acceptance run was `12 passed in 0.21s` using the requested interpreter and environment.

## What was not covered

- Inputs substantially larger than 4,000 records, very large individual JSON values, and disk exhaustion were not exercised.
- No deliberately non-terminating or very slow source was passed; iterable inputs are eagerly materialized.
- Concurrent writes to the same output path were not tested. The concurrent check used two readers with in-memory inputs.
- Memory sampling used one bounded workload and a 512 KiB retained-growth threshold; it does not characterize peak memory for very large logs.
- Malformed JSONL beyond the valid round-trip case and Python mappings containing values that are not JSON serializable were not covered.
