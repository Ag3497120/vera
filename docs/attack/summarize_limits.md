# `summarize.py` limits attack

Scope: synthetic in-memory stores and edge-reader callbacks, with limits,
pathology, determinism, repeated calls, and concurrent readers. The module was
not changed.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| SL-1 | wrong-ANSWER | One held subject `A` with facets `x,y`; pass `subjects=["A", "A"]` and license `("x", "y")`. Reproduced twice. | `UNKNOWN_TOO_FEW_PATHS`: a repeated identifier is still one path, so it cannot form the two-subject crossing. | `SUMMARY`: the repeated identifier is counted twice as a holder and produces claims. |
| SL-2 | crash | Two held paths share `x,y`; the reader returns `[('x',)]` for `A`. | Reject the malformed record and return typed silence; an incomplete edge record cannot license a claim. | `ValueError: not enough values to unpack (expected 2, got 1)` escapes from pair iteration. |

The duplicate-path expectation follows the contract that a crossing needs at
least two held subjects and each subject represents one path. SL-1 is a
wrong-answer defect and was run twice before reporting. SL-2 is a malformed
reader-record robustness case; ordinary valid edge pairs are covered
separately.

## What held

- Too few held paths, disjoint paths, missing edge lookup, reader exceptions,
  empty input, and vocabulary-gated speech returned the expected typed
  refusals.
- A licensed pair was emitted with the crossing-width and subject-mass counts
  defined by the module. Zero limit dropped every claim, and other limits
  dropped tied rank groups whole.
- Kept claims and text were stable when path order and edge iteration order
  changed. Repeating a call produced an equal result and did not mutate the
  store.
- Two concurrent readers each made 40 calls and returned matching results.
  After 1,000 discarded calls, traced live-memory growth stayed below the test's
  128 KiB bound.
- A synthetic 1,024-subject, equal-rank input completed; with limit 5, all
  1,024 claims were dropped as one group.

## Not covered

- No production corpus or edge sidecar was loaded; all inputs were synthetic.
- A callback that hangs, process-level concurrency, arbitrary non-pair objects
  beyond the one malformed tuple, and inputs larger than the synthetic case
  were not exercised.

## Run

Acceptance command: `/Users/motonisihikoudai/vera-wiring/env/bin/python -B -m
pytest -q tests/attack/test_summarize_limits.py`, with the unit environment
variables and pytest's cache provider disabled to avoid creating files beyond
the permitted deliverables. The run on Python 3.11.14 reported **13 passed,
2 xfailed** in **0.19 seconds**. The two xfails are SL-1 and SL-2.
