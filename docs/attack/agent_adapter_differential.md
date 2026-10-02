# Agent adapter differential attack

## Findings

| id | severity | minimal repro | expected | observed |
| --- | --- | --- | --- | --- |
| none | — | No disagreement appeared in the exercised cases. | The adapter follows the closed event and lifecycle contract. | The independent reference comparisons and contract checks passed. |

## What held

- The independently written parser reference agreed with the adapter on generated valid and invalid closed events, mixed prose and JSON lines, duplicate JSON keys, and replacement decoding for invalid UTF-8.
- Questions and free text converted to the expected typed conductor questions.
- The Codex command retained the brief as one argument after the option separator.
- Chunked runner output was assembled into the expected events; timeout closed the handle and stopped the runner once.
- The fake adapter normalized scripted events. Frame brief compilation included the active record, removed malformed records, redacted sensitive content, and retained an in-project relative path.
- The required acceptance command completed with **15 passed**.

## What I did not cover

- I did not run a real Codex executable, launch a subprocess, or make a network request; runner behavior was checked through an injected deterministic fake.
- The differential reference covers protocol parsing cases used by the generated suite. It does not independently model every size-limit boundary, every Unicode/control-character combination, or every frame-record nesting and count boundary.
- I did not inspect other project modules or use external or held-out data.
