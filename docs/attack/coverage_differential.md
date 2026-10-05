# Coverage differential attack

The reference in `tests/attack/test_coverage_differential.py` independently
scores exact core presence as 2, each split unit as 1, and one explicitly
named alias hop as 2. It uses the granularity split table as input, then
calculates ranking, tie order, signal cap, and top-four selection itself.
Eighty seeded generated cases compare this reference with `closing_domains`.

## Findings

| id | severity | minimal repro | expected | observed |
| --- | --- | --- | --- | --- |
| CD-1 | robustness | subject `topic`, aliases `{"topic": "Widget"}`, shelf cores `{"widget"}` | No exact canonical core is present; the shelf is not ranked and `coverage_hole` is true. | The alias branch checks `canonical.casefold()` against the core set, ranks the shelf at score 2, and reports no hole. The reproducer is retained as a non-strict xfail. |

## What held

- Exact subject cores add 2; source labels exclude a matching core.
- Each matching split unit contributes 1, while displayed signals are capped at four.
- Equal scores sort by domain name, and the output keeps the first four after sorting.
- Alias lookup makes one hop, without following an alias chain.
- An empty atlas reports a coverage hole and requests a general overview; a nonempty atlas names the tied top shelf or shelves.
- The seeded generated comparisons matched the reference outside the documented case-folding difference.

## Not covered

- Behavior for malformed domain objects, non-string domain names, or mutable custom containers.
- Whether upstream corpus construction normalizes core titles before this function receives them; the defect documents behavior at this function's exact-presence boundary.
- Integration with downstream gap handling or any effect on verdicts. This module describes a human-facing shelf suggestion only.
