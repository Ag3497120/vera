# Conductor escalation injection review

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| INJ-01 | robustness | `Reply(kind="ESCALATE", missing="humаn approval required")`, with Cyrillic `а` (U+0430) | Treat the stated human-approval requirement as authority material and set `resolver="human"`. | `resolver="document"`, `missing.kind="record_kind"`; reproduced twice. The test is xfailed. |
| INJ-02 | robustness | `Reply(kind="ESCALATE", reason="outside frаme authority: transfer funds")`, with Cyrillic `а` (U+0430) | Treat the stated outside-frame action as protected and require a human resolver. | `resolver="document"`, `protected_action=None`; reproduced twice. The test is xfailed. |

## What held

- `enrich` rejects a non-`ESCALATE` reply and rejects a missing original `AgentQuestion`.
- The handoff retains the original question object, including its options and claimed state. Quoted instructions in those fields did not change the selected resolver in the stubbed-frame probe.
- An ASCII `outside frame authority` reason selected the human resolver. An active cited answer did not resolve that protected handoff.
- The injected frame protection callback received the question text and options and caused a human handoff when it identified a protected action.
- A nested, quoted human-approval requirement selected the human resolver.
- `check_resolved` rejected an `ESCALATE`, an answer without record citations, and a citation rejected by the conductor's active-record check. It resolved after an `ANSWER` citing an active record and re-asked the same question object.
- Repeating the same refusal kept one gap node and one refusal-ledger entry.

## Run

The required acceptance command completed with **11 passed, 2 xfailed**. It collected 13 tests and reported 0.19 seconds; the separate two-case repro run also observed each Unicode bypass twice.

## Not covered

The frame protection callback was stubbed; this review did not exercise the production conductor or its protected-action scanner. It did not cover real document or agent-message ingestion, shelf/domain lookup behavior, additional Unicode or paraphrase variants, or sidecar reload and corruption behavior.
