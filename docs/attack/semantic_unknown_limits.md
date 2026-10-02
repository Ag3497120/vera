# Semantic unknown limits attack

Scope: limit and determinism probes against `verantyx/semantic_unknown.py`, using synthetic View-shaped values. No corpus or external source data was used.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| BUD-01 | robustness | One empty-source clause with no roles; query `mystery`; budget `1` | The single clause fits the documented clause/role-term/source-word projection budget. | `BUDGET_REFUSAL`; marked as a non-strict xfail in the attack test. |

## What held

- Invalid and zero budgets returned `BUDGET_REFUSAL` with no candidates.
- A non-string query raised the documented `TypeError`.
- Empty input fit a positive budget; held role and predicate terms returned `KNOWN_TERM`.
- Returned candidates used an allowed kind, were marked constructed, and were not evidence.
- Reordered clauses produced identical JSON, repeated calls were idempotent, and two concurrent readers agreed.
- Repeated empty-view reads stayed below the test's retained-memory bound.

The acceptance run was **16 passed, 1 xfailed** in **0.12 seconds**. The memory probe made **16** calls and required retained traced memory below **1,000,000** bytes. A source with **10,000** repeated `word ` tokens was refused under the low budget; an empty-view query of **16,384** `x` characters returned a typed report.

## Not covered

- Real parser-produced semantic Views, malformed internal View objects, sources larger than the **50,000-character** stress input, and sustained high-concurrency workloads.
- This unit did not modify the implementation or investigate any sealed, heldout, or development material.
