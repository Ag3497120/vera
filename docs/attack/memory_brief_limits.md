# Memory brief limits attack

Scope: black-box limits and determinism checks for `compile_brief`. The attack tests use a small memory stub implementing `active()` and `ask_about()` so they exercise the brief compiler's budget and ordering behavior without claiming to validate the memory backend.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| MBL-01 | robustness | 256 askable `INVARIANT` rows; set the budget to the character length of all 256 rendered lines. | Include all rows because their complete output fits the budget. | Only rows `r0000`–`r0253` are included; `r0254` and `r0255` appear in `Dropped record ids`. The incremental check accounts for dropped IDs that would disappear if the remaining rows were selected. |
| MBL-02 | crash | One row with `slots=None`; call with a nonempty focus such as `focus="x"`. | Treat the row as unaskable and report `Dropped record ids: bad`. | Raises `AttributeError: 'NoneType' object has no attribute 'values'` during focus ranking, before dropped-ID accounting. |

Both findings have reproducing tests marked `xfail(strict=False)` so they remain visible without failing acceptance. No wrong-answer or fabrication finding was observed.

## What held

- Six invalid budget values raised `ValueError`; empty memory returned an empty brief at budget zero.
- Reversing the input order preserved output order by kind priority, and a line that exactly fit its character budget was included.
- Unaskable records were listed as dropped when the selected line and dropped-ID report fit; a budget too small for the report raised `ValueError`.
- Full-width mixed-case focus matched normalized text and ranked that record first. Superseded IDs were excluded.
- Repeated calls returned the same result without mutating input records. Eight calls through four concurrent readers returned the same brief.
- Acceptance run: **15 passed, 2 xfailed**. The 256-row exact-budget case exposed MBL-01.

## Not covered

- The actual typed memory implementation's `ask_about()` semantics, freshness filtering, or behavior under concurrent writes; `ask_about()` here is supplied by a deterministic stub.
- Inputs larger than the 256-row repro, long-running memory growth, resource exhaustion, or timing behavior at scale.
- Malformed record shapes beyond the `slots=None` focus-ranking reproducer, and non-string/non-iterable focus values.
