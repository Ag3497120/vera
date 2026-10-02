# Conductor differential attack

The checks compare selected `ProjectFrame` behavior with a small independent reference for conflict-free order graphs and direct expectations from the conductor's typed contract. The reference evaluates phase states and edges itself; it does not call conductor helpers.

## Findings

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| CD-01 | robustness | Add tasks `Draft=完了` and `Review=未着手`, then add the active order `draft → review` using an unconflicted decision as its reason. Ask “What is the next phase?” | `ANSWER` with `Review`: task identities are treated case-insensitively elsewhere in the conductor. | `ESCALATE`, missing `TASK state`, because order resolution looks up task records by the raw endpoint strings. The test repeats the repro twice. |

No wrong-answer or ungrounded-answer defect was observed in these checks.

## What held

- The generated conflict-free order cases agreed with the naive readiness reference: a single ready successor is answered, while no ready successor, an unresolved endpoint, or a tie does not produce an answer.
- A matching active policy tied to an active decision supplied its answer and both record IDs. A condition mismatch escalated without an answer.
- A protected publishing request escalated to a human even when a policy allowed it.
- Empty or malformed questions escalated without an answer.
- A completion claim without a goal escalated. A human-judged acceptance required a typed human verification, and an independent acceptance requested another verifier before a passing verification allowed `done`.

Acceptance command result: `15 passed, 1 xfailed`.

## Not covered

- Broad natural-language classifier behavior, including the full English and Japanese cue space.
- Choice resolution, aliases, and the closed-choice resolver's two-ask path.
- File digest and git witnesses, command-runner outcomes, and authority-boundary paths beyond the protected publishing check.
- Concurrent writers, malformed persisted records, and long-running or large frames.

The result is limited to this attack's checks; it does not establish general conductor correctness.
