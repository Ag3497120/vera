# Conductor limits attack

The tests exercise the public `ProjectFrame` API for empty and malformed input,
large questions, deterministic ordering, repeat calls, typed refusals, and
concurrent read access.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| order-normalized-id | robustness | Add completed task `Build`, active task `Deploy`, and ORDER `build` → `deploy`; ask “What is next?” | Resolve ORDER endpoints using the same normalized identity used to group TASK records, yielding `Deploy`. | Returns typed `ESCALATE` with missing `TASK state`: ORDER lookup indexes tasks by the raw subject string, so `build` does not find `Build`. The reproducer is retained as a non-strict xfail. |

## What held

- Empty and malformed questions, malformed options, and a 500,000-character
  unclassified question returned typed escalations.
- A unique ready successor produced the same answer on repeat calls and after
  changing fact insertion order. Evidence IDs were unique. Competing ready
  successors caused an escalation instead of a guess.
- A protected publishing request escalated to a human. A supported CONFIRM
  policy answer cited both its policy and active authority records.
- Repeating an unchanged task write preserved its record, and repeated status
  reads returned the same state. Two reader instances also returned matching
  answers while servicing concurrent reads.

Acceptance run with the required empty-corpus environment:

```text
10 passed, 1 xfailed
```

## What was not covered

- Long-running memory growth, histories with many thousands of records, and
  simultaneous writes or cross-process access.
- Closed-choice resolver behavior, filesystem/Git/command acceptance witnesses,
  and human or independent-verifier flows.
- Resource exhaustion beyond the large-question case, corrupted storage, and
  schema migration behavior.
