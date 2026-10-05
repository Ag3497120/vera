# Differential attack: constructed explanations from units

## Findings

The acceptance run completed with 10 passed tests. No disagreement or defect
was reproduced, so there are no defect findings to classify.

| id | severity (`wrong-ANSWER`, `ungrounded`, `crash`, `hang`, `robustness`) | minimal repro | expected | observed |
|---|---|---|---|---|
| — | — | — | — | No defect reproduced by this suite. |

## What held

An independent reference interpreter applies the shared split grammar to
synthetic stores and models. Generated combinations of slot support, held
units, labels, and vocabulary membership agreed with `explain` on the typed
result. Focused checks also held for bare-suffix and tied-split abstentions,
the held-word score priority, crossing order and vocabulary filtering,
constructed draft marking, optional edge pairs, and pass-through of a
non-`UNITS` route result. Edge lookup exceptions were ignored as specified.

## What was not covered

The tests stub `reach` to isolate `explain`'s `UNITS` branch and one
non-`UNITS` pass-through. They do not verify real reach routing, corpus-backed
stores, lattice neighbourhoods, or behavior over corpus data. No defect was
reproduced, so no xfail reproducer was needed. The implementation module was
read-only and was not changed.
