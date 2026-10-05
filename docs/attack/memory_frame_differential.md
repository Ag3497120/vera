# Memory frame differential attack

The test uses a small reference model for noun normalization, exact slot sets, slot text gates, strict bounded JSON choices, and append/supersession projection. Generated input cases compare those independent expectations with verantyx.memory_frame. The accepted-write round trip also checks the JSONL reload path.

## Findings

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| D1 | robustness | Call Memory.write("FACT", ..., witness={"kind": "testimony"}, supersedes="missing-id", subject="ルーター", attribute="未読上限", value="10"). | Reject the unknown supersession target without appending a record. | WriteRejected is raised after the write event is appended; reopening the log returns the new FACT as active. |
| D2 | robustness | parse_choice('説明文のあとに {"choice": 1}', 2) | Return False; the response is not the JSON-only choice format. | Returns index 1 by matching the embedded JSON fragment. |

Both findings have non-strict xfail reproductions in the test file.

## What held

- Generated noun phrases matched the independent trim-and-particle-removal reference.
- Generated missing/extra slot sets and invalid slot text were rejected before append.
- FACT and INVARIANT writes without witnesses and writes with an unknown witness kind were rejected.
- Without a resolver, task states outside the closed canonical list were rejected.
- For generated candidate lists, two asks selecting the same canonical expression produced ADOPT.
- Generated valid bounded JSON choices and clean malformed replies matched the independent parser model.
- A valid task write, supersession, and log reload produced the reference active-record projection.

The acceptance command run from the worktree root completed with **13 passed, 2 xfailed** in **0.17 seconds**.

## Not covered

- Memory.ask and the end-to-end semantic answer path were not tested.
- File-hash freshness, text-in-file witnesses, and git-commit witnesses were not exercised.
- The tests use a deterministic fake asker; they do not invoke Codex or another external resolver.
- Concurrent writers, damaged event logs, long-running inputs, and broad Japanese sentence coverage were not exercised.
