# Verifier agents differential attack

The independent test oracle covers the verifier brief text and verdict parsing. It assembles the brief payload separately and uses a small reference parser for the documented single-event verdict form.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| VA-D01 | crash | `parse_verdict([{"type": "VERDICT", "result": [], "evidence_ref": "test:case"}])` | Raise `ValueError` for unverified output. | Raises `TypeError: unhashable type: 'list'` while checking the result. Tracked by an xfailed test. |
| VA-D02 | ungrounded | `parse_verdict([{"type": "VERDICT", "result": "PASS", "evidence_ref": "."}])` | Reject: `.` does not identify inspectable evidence. | Accepts the verdict as `PASS` with evidence reference `.`. Tracked by an xfailed test. |

No wrong-ANSWER or fabrication finding is reported. The tests do not exercise the acceptance-answer path, so those outcomes were not established.

## What held

- In the generated cases, parsing matched the independent oracle for valid reference forms, malformed event shapes, duplicate JSON keys, unsupported results, and equivalent direct and `OTHER` event encodings.
- The parser strips surrounding whitespace from a reference before validation; a whitespace-padded `file.py` parsed as `file.py` in both the oracle and implementation.
- Generated brief payloads matched the separately assembled canonical brief, including Unicode and instruction-like text held inside the JSON data. Tested identity collisions, an unsupported template, and an over-limit brief were rejected.
- The required acceptance command completed with **8 passed and 2 xfailed in 0.18s**.

## Not covered

- `run_verifiers` integration with a `ProjectFrame`, verifier adapters, and the final conductor re-check.
- Adapter lifecycle and real-time timeout behavior, polling limits, or failures while recording verification.
- Whether a parsed verdict corresponds to real external evidence, and any end-to-end wrong-ANSWER or fabrication behavior. These findings concern the parser boundary only.
