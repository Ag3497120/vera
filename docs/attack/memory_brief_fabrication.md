# Memory brief fabrication and provenance review

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|

No defects were reproduced in the tested cases.

## What held

- The brief retained the source ID and sentence verbatim, including a negation.
- Records about different entities remained attached to their own IDs.
- Records omitted by the ask path and closed tasks were not rendered; their IDs were reported as dropped.
- A LESSON was checked using its situation and response role.
- A superseded ID was excluded while the current record remained eligible.
- Focus changed ordering without changing the supported sentence text.
- The compiler returned drop accounting within budget, rejected a budget too small to report it, and rejected invalid budget values.

Acceptance run: 14 passed.

## What was not covered

- Malformed records outside the typed-memory shape, duplicate record IDs, and exceptions from custom `active()` or `ask_about()` implementations.
- Semantics of the concrete memory writer, resolver, and freshness policy; these checks used a small typed-memory double for the public `active()` / `ask_about()` path.
- Concurrency, very large memories, and budgets close to Python's practical allocation limits.
