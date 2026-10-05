# Verifier-agent limits attack

Acceptance run: `VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_verifier_agents_limits.py` — **13 passed, 2 xfailed in 0.17s**.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| VA-LIM-A | crash | `parse_verdict([{"type": "VERDICT", "result": [], "evidence_ref": "test:check-1"}])` | Reject malformed verdict with `ValueError`. | Raises an uncaught `TypeError` because list membership in the allowed-result set requires a hashable value. Kept visible as a non-strict xfail. |
| VA-LIM-B | robustness | `run_verifiers(_MemoryFrame(), "task-1", _ask(), [], claimant_id="claimant-1", claimant_session_id="claimant-session-1", timeout_seconds=float("nan"))` | Reject a non-finite timeout budget with `ValueError`. | NaN passes the `timeout_seconds <= 0` check; processing continues and returns the ordinary no-verifier escalation. Kept visible as a non-strict xfail. |

## What held

- Equivalent ask mappings and repeated brief construction produce the same bounded brief; an oversized prompt is rejected. Prompt text remains JSON data in the brief.
- Verdict parsing accepts a valid single event, trims its reference, and rejects zero or multiple events, duplicate JSON keys, and deeply nested malformed JSON.
- Two reader workers returned the same brief and verdict over 40 calls. Repeated parse calls were also stable.
- Unanimous verifier evidence is serialized in identity order independent of verifier input order.
- With a poll budget of two, the adapter was polled twice, stopped, and no verification record was written after timeout.

## Not covered

- No direct memory profiling, very large verifier-list stress, or adapter that blocks inside `start` or `poll` was exercised.
- Orchestration used an in-memory `ProjectFrame` seam; disk-backed acceptance record creation and verification were not exercised.
- Wrong-answer and ungrounded-verdict behavior was not evaluated by this limits-focused suite.
