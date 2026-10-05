# Agent adapter limits and determinism attack

Scope: the parser, command builder, injected-runner lifecycle, and frame brief in `verantyx/agent_adapter.py`. The probes use synthetic frames and local injected runners; they do not start an external agent.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| LIM-01 | robustness | Compile a frame record with `slots={"score": float("nan")}`. | `RECORDS_JSON` is valid strict JSON, or compilation returns a typed refusal. | The brief contains the non-standard JSON token `NaN`; a strict JSON parse rejects it. Reproduced by an xfail. |
| LIM-02 | robustness | Compile a frame record with `slots={"count": 10**5000}`. | The integer is within the brief character budget and is serialized, or compilation returns a deliberate bounded refusal. | Compilation raises `ValueError` in JSON integer-to-text conversion at Python's digit guard before the brief-size check. Reproduced by an xfail. |

## What held

- Closed question events are normalized; prose remains `OTHER`; byte input decodes invalid UTF-8 with replacement.
- Duplicate JSON keys, extra event fields, non-standard JSON constants, bad input types, and invalid parser limits are rejected or refused with the adapter's typed error behavior.
- Configured line and total-output limits are enforced.
- Repeated brief compilation is stable, and reversing slot insertion order does not change the brief. Sensitive values and external paths are redacted; project-relative file paths are retained.
- Excess active records and deeply nested values are refused.
- The command builder preserves the brief as one argument and refuses a brief over its declared size limit. Oversized messages are refused before reaching the runner.
- Split output lines are buffered until complete. Timed-out handles close, stop the runner once, and return no later events. Two concurrent handles keep their event streams separate.

## Not covered

- An actual Codex process or any non-test runner implementation; all lifecycle checks use injected in-memory runners.
- Sustained load, scheduler stress, memory profiling, and repeated near-cap output/brief workloads.
- Filesystem symlink behavior and platform-specific path handling beyond the synthetic paths in the tests.

## Run record

Acceptance command: `/Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_agent_adapter_limits.py`, with the unit's specified environment. Final result: 12 passed, 2 xfailed in 0.19 seconds.
