# Conductor escalation fabrication attack

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| F-01 | ungrounded | `test_unrelated_active_record_cannot_ground_resolution`: answer the unchanged question with an active record citation whose role or entity does not support the answer. | Keep the handoff unresolved because the cited record does not establish the re-asked claim. | `check_resolved` returns `True` based only on the cited ID being active, and records a resolved outcome. Reproduced in two test runs, with both wrong-role and swapped-entity records. |

F-01 is a severity-1 provenance defect. The module verifies that a citation points to an active record, but does not validate that the record supports the answer's role, entity, or polarity.

## What held

- `enrich` rejects non-ESCALATE replies and requires the original `AgentQuestion`.
- The handoff and serialized re-ask preserve the question text, options, claimed state, entity, and negation; `check_resolved` passes the same question object back to the conductor.
- An ESCALATE reply, an ANSWER without citation, and an ANSWER with an inactive citation do not resolve the handoff.
- A cited active record allows resolution, and a protected action remains human-resolvable and cannot be closed by a document answer.

The required acceptance command ran twice. Each run reported **9 passed, 2 xfailed**; the xfails are the two parameter cases for F-01.

## What was not covered

- The provenance checks use a small fake conductor and synthetic record mappings. They do not exercise a live `ProjectFrame`, its record reader, or a real memory store.
- No attack covered sidecar corruption, concurrent updates, or behavior across process restarts.
- This is a focused fabrication/provenance attack; it does not assess other escalation behavior or the broader semantic and older-line pipeline.
