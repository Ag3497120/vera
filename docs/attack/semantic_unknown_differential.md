# Semantic unknown differential findings

Scope: an independent reference for the public early decisions (term and budget guards, exact known-term matches, and the documented projection budget), plus checks that generated outputs remain typed constructed candidates. The reference does not reuse `semantic_unknown` helpers.

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| SU-D01 | robustness | Empty-clause View with source `alpha`; query `unseen`; budget `1` | `BUDGET_REFUSAL`: one distinct source word plus the query exceeds the budget | `CANDIDATES`; reproduced twice by the xfailed regression |

The regression is marked `xfail` because the module is outside this unit's write set. No answer or evidence is emitted by the repro; the disagreement is the budget refusal being skipped.

## What held

- Non-string terms raise `TypeError`; invalid, boolean, and negative budgets return a typed budget refusal.
- Exact role-term and predicate matches return `KNOWN_TERM` before work-budget projection.
- Generated Views whose clause and role counts exceed a budget of one return a budget refusal, matching the independent count.
- Unknown-term reports do not use an answer status, and every returned candidate is marked `constructed=True` and `evidence=False`.
- The acceptance run completed with **9 passed and 1 xfailed**.

## Not covered

- The older explain, lattice, unit-decomposition, and vocabulary helpers were treated as opaque; this unit does not validate their candidate quality or internal semantics.
- Generated budget-reference cases used simple whitespace-separated ASCII words. Other tokenization cases, large inputs, hangs, and performance limits were not covered.
- No external or held-out material was used.
