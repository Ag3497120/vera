# Conductor escalation differential

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| None | — | 63 generated escalation combinations plus the focused cases in `test_conductor_escalate_differential.py` | The typed handoff preserves the original question, classifies missing material, records the refusal once, and closes only after a re-ask cites an active record. | No disagreement with the independent reference model or these contract checks was observed. |

No defect was reproduced, so this unit contains no xfail cases.

## What held

- Across 63 generated combinations of missing-material text, refusal reason, and question kind, handoff fields matched a small independent contract model.
- Authority and vocabulary material routed to a human; ordinary typed record gaps remained document-resolvable.
- Shelf lookup data populated the typed repair fields, including when the lookup returned a JSON string.
- The exact original question was re-asked. A non-answer, an uncited answer, or a citation to an inactive record did not resolve the handoff.
- A cited answer from an active record resolved the gap, while a protected action remained open. Duplicate refusals and repeated successful re-asks did not add duplicate ledger outcomes.

## What was not covered

- Persistent serialization and reload of the growth and gap sidecars; tests used in-memory doubles.
- Integration with a live conductor and a real project frame or memory store.
- Coverage/domain lookup and remedy fallback paths; generated cases used the injected shelf lookup.
- Protected-action detection through a frame's private checker; protected cases used the refusal-reason path.

## Acceptance run

Command run from the worktree root with the unit environment variables:

```text
VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_conductor_escalate_differential.py
```

Result: **8 passed** in 0.18 seconds.
