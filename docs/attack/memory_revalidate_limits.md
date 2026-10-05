# Memory revalidation limits

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| MRL-01 | crash | `RevalidatingMemory(...)._status({0: "bad-key", "kind": "testimony"})` | Return `UNVERIFIABLE` for testimony without a witness check. | `_key` raises `TypeError` while sorting the mixed integer and string keys, before `_check` can return `UNVERIFIABLE`. The reproducer is retained as a non-strict xfail. |

## What held

The acceptance run completed with 13 passed and 1 xfailed in 0.22 seconds. Passed cases covered empty and non-mapping witnesses, testimony and unknown-kind handling, file digest/text comparisons, git status mapping and timeout argument, runner timeout handling, cache reuse and expiry, both zero-cache settings, bounded LRU eviction, mapping-order-independent cache keys, a large unknown witness, stale-record filtering and labeling, and two simultaneous asks sharing one cached validation. The cache bound exercised is by entry count.

## Not covered

No real files or git repositories were read; file reads and git results were mocked. The tests do not measure wall-clock cost or process memory for very large file witnesses, test a runner that ignores its timeout, or test multiple `RevalidatingMemory` instances with separate caches. They do not validate the underlying `Memory` answer-selection behavior; wrapper tests stub its ask method to isolate revalidation and labeling.
