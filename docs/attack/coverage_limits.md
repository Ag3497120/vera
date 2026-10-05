# Coverage limits attack

Acceptance run: **11 passed, 1 xfailed** in **0.11s** using the required
`tests/attack/test_coverage_limits.py` command.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| CL-01 | robustness | Give `closing_domains` five shelves, each holding the same subject as a core. | The module documentation says equal scores are displayed as ties, so all five tied shelves should remain visible. | Only the first four shelves in domain-name order are returned. The reproducer is retained as a non-strict xfail in `test_all_equal_top_shelves_remain_displayed_as_a_tie`. |

## What held

- Empty domains and whitespace-only subjects report a coverage hole.
- Exact subject presence ranks a shelf; a source label by itself does not count as a core.
- Alias lookup uses one hop and names the canonical title in its signal.
- The returned shortlist is capped at four, and its contents are stable under domain insertion order.
- Repeated calls return the same value without mutating the supplied shelf sets.
- A one-million-character subject and an atlas of 10,000 domains completed without a crash or hang; returned ranking remained four rows at most.
- Two concurrent readers using the same domain mapping returned the same result across 64 calls.
- `document_needed` reports a hole without naming a shelf when there is no matching presence.

## Not covered

- Memory usage was not profiled; the large-input checks verify completion and returned-output bounds only.
- The tests use the expected shelf shape (`crosses` and optional `source_labels`); malformed shelf objects and malformed alias mappings were not tested.
- This run did not test integration with corpus loading or other coverage consumers.
