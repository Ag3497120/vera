# Conductor escalation limits attack

Acceptance run: `VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_conductor_escalate_limits.py` — **13 passed, 1 xfailed**.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| L1 | robustness | Enrich once with shared injected sidecars, then call `check_resolved` from two threads using the same handoff and an active-record `ANSWER`. A barrier inside `record_branch_outcome` makes both calls pass duplicate detection before either appends. | The idempotent refusal ledger contains one resolved outcome for the handoff. | Both calls returned `True`, but the shared ledger had two resolved outcomes (three total including the initial unresolved outcome). Reproduced twice with the barrier probe; covered by the non-strict xfail test. |

## What held

- Non-`ESCALATE` replies and missing original questions raise typed `ValueError`s.
- The handoff retains the original question object, text, options, and claimed state for re-asking.
- Repeating `enrich` sequentially keeps one gap node and one refusal outcome; separate causes for one subject retain separate gaps, independent of insertion order.
- Empty values become typed missing material, and 65,536-character question and missing strings were retained without truncation.
- A re-ask only resolves from an `ANSWER` with an active record citation. Repeating a successful check records one resolved outcome, and a protected action remains human-resolvable.

## Not covered

- Cross-process concurrent writers, forced process interruption during sidecar writes, or filesystem permission and disk-full failures.
- Inputs substantially larger than 65,536 characters or resource-exhaustion limits.
- End-to-end behavior with a production `ProjectFrame` and its native conductor; tests used small frame and conductor doubles, with real sidecar classes for persistence checks.
