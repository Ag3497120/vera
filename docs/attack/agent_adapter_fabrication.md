# Agent adapter fabrication and provenance attack

## Findings

The probes below held in the required run: **12 passed**. No wrong ANSWER or other defect was reproduced, so there are no defect xfails.

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| AF-01 | robustness | Parse a CLAIM whose task names subject, predicate, object, and negative polarity. | Preserve task and evidence as CLAIM fields without rewriting roles or polarity. | Held; fields were preserved exactly. |
| AF-02 | robustness | Parse a CLAIM missing `evidence`, or with an extra `answer` field. | Emit ERROR, not a partial or ANSWER event. | Held; both invalid shapes were rejected. |
| AF-03 | robustness | Give the JSON object duplicate `task` keys. | Reject the ambiguous structured event. | Held; emitted malformed-event ERROR. |
| AF-04 | robustness | Parse plain prose and try to convert a CLAIM to a conductor question. | Keep prose as OTHER; reject CLAIM conversion. | Held; prose stayed OTHER and CLAIM conversion raised ValueError. |
| AF-05 | robustness | Convert a QUESTION with an ID, negated text, and options. | Preserve the supplied ID, text, and options. | Held; all three values were preserved. |
| AF-06 | robustness | Compile a frame exposing one active record and an out-of-projection field. | Use `_active()` records and serialize only ID, kind, and slots. | Held; only the active record projection appeared in the brief. |
| AF-07 | robustness | Compile slots containing distinct subject/object roles and negative polarity. | Preserve the slot keys and values. | Held; the roles and polarity were unchanged. |
| AF-08 | robustness | Parse an incomplete JSON CLAIM span. | Do not emit a partial CLAIM. | Held; emitted malformed-event ERROR. |
| AF-09 | robustness | Split a JSON CLAIM across runner polls. | Retain the partial span and emit one complete event after the newline. | Held; no first-poll event, then the complete CLAIM. |
| AF-10 | robustness | Put option-like text in a brief passed to the command builder. | Keep the brief as one argument after `--`. | Held; the brief remained one argument. |

## What held

- The closed event parser rejected missing required fields, extra fields, and duplicate JSON keys rather than turning them into claims.
- Event parsing and conductor conversion kept QUESTION, CLAIM, and OTHER roles distinct. Claims were not accepted by `to_conductor_question`.
- The frame brief used the active-record interface and retained the tested entity roles and negative polarity without changing their values.
- Partial JSON was not emitted as a complete claim, including when a valid event arrived in multiple runner chunks.
- The command builder placed the entire brief after the option separator as one argument.

## What was not covered

- The frame fixture supplied the result of `_active()` directly. This checks the adapter projection but does not audit how the real project frame marks records superseded or inactive.
- No end-to-end conductor verification or real external Codex process was exercised; the adapter was tested at its parser, brief, and injected-runner boundaries.
- Exhaustive size-limit, timeout, hostile runner, path-sanitization, and secret-redaction behavior was outside this fabrication/provenance probe.
- No wrong ANSWER was observed, so the required two-run reproduction rule was not triggered.

## Run

`VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_agent_adapter_fabrication.py`

Result: **12 passed in 0.14s**.
