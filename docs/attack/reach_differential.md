# Reach differential attack

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| — | — | No discrepancy in the cases exercised | The positional reference and reach contract agree on the checked inputs | No disagreement observed; no defect test was marked xfail |

## What held

- `units_for` matched an independent reference over generated strings and controlled positional slot attestations. Attested splits are emitted right part first, then left part.
- A part attested in the wrong position did not qualify. `by_units` selected the part with more crosses and retained the first part when counts tied.
- Reach returned a held term before consulting other routes, excluded source labels from held/unit returns, and preferred a qualifying unit over containment.
- A judge verdict beginning with `ANSWER` produced containment, while the checked non-answer verdicts produced `UNKNOWN_NO_REACH` with no item.
- `build_model` passed only non-source-label keys to the decomposition function.

## Test run

Acceptance command completed: `15 passed in 0.08s`.

## What was not covered

The tests use small in-memory stores, hand-built slot models, and a stub judge. They do not exercise the real granularity builder or split inventory, a production store, a real graded judge, corpus behavior, or integration with other reach consumers. They also do not establish behavior for malformed objects or long-running inputs. No corpus or external data was used.
