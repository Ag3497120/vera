# Reach limits attack

Target: `verantyx/reach.py`. This is an independent attacker report; the target module was not changed.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| R-01 | robustness | `reach(Store(), "")`; `reach(Store(), "語" * 1,048,576)`; `reach(Store(), "\x00\ud800")` | Empty and unknown terms return `UNKNOWN_NO_REACH` without crashing or mutating the store. | All returned `UNKNOWN_NO_REACH`; the store remained unchanged. |
| R-02 | robustness | `reach(store, "損害賠償", model=split_model())` with both attested units and unequal core counts | Choose the attested part with the larger core count; when counts tie, preserve the head-final right-first unit order. | The richer part won. Equal-count parts select `賠償`; reversing the store mapping insertion order did not change the result. |
| R-03 | robustness | Call `reach(Store(), term)` for 2,048 distinct unknown terms, then collect and inspect traced allocations. | Repeated calls should not retain each input term; retained traced growth stays below the test's 256 KiB limit. | The check passed below that limit. |
| R-04 | robustness | Run 64 reads across two store/model pairs with two worker threads. | Each reader returns its own route result without cross-reader state changes or errors. | All reads returned the expected `UNITS` or `UNKNOWN_NO_REACH` result. |
| R-05 | robustness | Give a judge an `ANSWER_*` result or a typed non-answer result. | Report an answer as `CONTAINMENT`; leave refusals and unknowns as `UNKNOWN_NO_REACH`. | The routes and judge call were as expected; a unit result also took precedence without calling the judge. |

No `wrong-ANSWER`, `ungrounded`, `crash`, or `hang` defect was reproduced in this scope, so there are no defect xfails.

## What held

- Held terms return `HELD` directly, and source-label entries are excluded as held cores and unit evidence.
- Unit selection prefers the part with more crossings. The right half is checked first on equal counts, and changing the store mapping's insertion order does not affect selection.
- A unit result precedes containment. A judge answer is reported separately as `CONTAINMENT`; judge refusals do not become answers.
- Empty and 1,048,576-character unknown terms, a NUL plus lone-surrogate term, repeated calls, the 2,048-term allocation check, and two concurrent readers passed.
- The acceptance command reported **15 passed** in **0.10 seconds**.

## What I did not cover

- I used small in-memory store, model, and judge doubles; I did not test corpus-backed data or a production `GradedJudge`/`UnitModel` combination.
- I did not measure process RSS, native allocations, long-running memory behavior, or sustained/high-contention concurrency. The allocation check measures only traced Python allocations during its short repeated-call workload.
- I did not test how a judge behaves when asked about a huge term, nor malformed dependency objects outside the documented interfaces.
- This attack checks reach limits and route behavior, not answer grounding or corpus-level accuracy.
