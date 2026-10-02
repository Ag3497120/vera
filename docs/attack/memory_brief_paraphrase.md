# Memory brief paraphrase attack

## Findings

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| MBP-01 | robustness | Keep a FACT's slots as subject `会議`, attribute `場所`, value `東京`; use focus `会議の場所` and a budget that fits one of two records. Change its sentence from `会議の場所は東京です。参加者が迷わないよう、事前に会場案内を共有します。` to the synonymous `東京で会議を開きます。参加者が迷わないよう、事前に会場案内を共有します。` | The same typed fact remains focused and selected after the wording change. | The direct wording selects `r1`; the reordered wording loses the literal focus match, so earlier `r2` is selected. In both cases the other ID is reported as dropped. |

## What held

- Fullwidth and ASCII focus text compare equivalently after width and case normalization.
- A focused FACT sorts ahead of an unfocused INVARIANT.
- Polite and plain sentences that retain the focused phrase select the same record under a constrained budget.
- Entity and number changes in a record's sentence are reflected in the rendered line.
- An explicitly completed TASK is omitted and listed as dropped; an open TASK remains eligible.
- A record that cannot be asked about is reported as dropped, and superseded records are removed before dropped-ID accounting.
- Invalid budgets are rejected, and a budget too small to report dropped IDs raises `ValueError`.

## Coverage limits

The tests use a small in-test memory double for `active()` and `ask_about()` to isolate the brief compiler's selection path. They do not cover integration with the concrete memory store, lesson records, a wider set of task states, or semantic matching across other paraphrase families. The compiler output was checked as a brief; no downstream response generation was evaluated.

Acceptance command run from the worktree root with the specified empty corpus environment: **14 passed, 1 xfailed**.
