# Conduct tree limits and determinism

Scope: `verantyx.conduct_tree` build and descent behavior under bounded inputs,
including empty input, insertion-order changes, repeated readers, and an
invalid grouping arity. No answer-quality claim is made from these tests.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| CT-01 | robustness | `build({})`; then `descend(tree, "invented")` | Empty input stays representable and descent returns a typed no-route result. | Passed: empty root and `UNKNOWN_NO_ROUTE` at `root`. |
| CT-02 | robustness | `build` 37 named leaf crosses using default arity | All leaves remain present and each node has at most the six-arm capacity. | Passed: all 37 leaves were present and maximum fan-out was 6. |
| CT-03 | robustness | Build 19 identical named inputs in forward and reverse insertion order | Sorted grouping produces equal trees independent of caller insertion order. | Passed: built `Node` trees compared equal. |
| CT-04 | robustness | Build the same 13 leaves twice; build 8 leaves while retaining a deep copy of their crosses | Rebuilding is idempotent and build does not mutate its leaf input. | Passed: trees compared equal and the input crosses were unchanged. |
| CT-05 | robustness | Descend twice for an absent term with a caller trail; make two simultaneous read-only descents | Abstentions stay typed, repeated results are stable, and readers do not share or mutate trails/tree state. | Passed: both readers returned independent `UNKNOWN_NO_ROUTE` results; repeated calls left the tree and supplied trails unchanged. |
| CT-06 | crash | `build({'a': {}, 'b': {}}, arity=1)` in a subprocess with a 1-second timeout | Reject an arity that cannot reduce multiple leaves, or otherwise terminate safely. | XFAIL: child exited with `RecursionError` from repeated `_merged_view` nesting before the timeout. |
| CT-07 | robustness | Build 216 leaves, keep only a weak reference to the returned tree, then collect | A completed tree is not retained by a module-level cache after its caller releases it. | Passed: the tree was collectible. |

CT-06 is marked `xfail(strict=False)` in the test so the attack suite remains
green while keeping the defect visible. The child process bounds the failure
and prevents recursive construction from affecting the pytest process.

## What held

- The default six-arm builder retained the tested leaves and respected the
  fan-out limit across multiple levels.
- Empty input produced an empty tree, and a missing term produced the module's
  typed `UNKNOWN_NO_ROUTE` result.
- Repeated builds, reversed insertion order, repeated descent, and two
  concurrent readers showed stable results in the exercised cases.
- The bounded build result became collectible after its caller released it.

## What was not covered

- The optional prebuilt `hierarchy` conversion path was not exercised.
- The arity attack covers `arity=1`; other custom arities and malformed cross
  value types were not tested.
- The concurrency case used two read-only threads. It did not test concurrent
  mutation, which is outside the reader contract.
- The largest memory-lifetime probe used 216 leaves; it does not establish
  behavior for million-sentence corpora.
- These limit tests do not independently validate routed leaf correctness or
  make a wrong-answer / ungroundedness finding.

## Run

Acceptance command run from the worktree root:

```text
VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_conduct_tree_limits.py
```

Result: **9 passed, 1 xfailed**. The arity subprocess diagnostic returned a
nonzero exit with `RecursionError` before its 1-second timeout bound.
