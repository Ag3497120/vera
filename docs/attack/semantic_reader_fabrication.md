# Semantic reader fabrication attack

Scope: `verantyx.semantic_reader` document reading and request planning. Findings are based on the reader's typed IR. A severity 1 role-mapping result was run twice with the required empty corpus root; both runs produced the same incorrect plan.

## Findings

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| SRF-01 | wrong-ANSWER | `read_request("本は誰によって花子に渡されたか？")` | The query binds `patient=本`, `recipient=花子`, and an unknown `agent`; its output projects `agent`. | The plan binds `agent=花子` and an unknown `recipient`; its output projects `recipient`. Identical result in two runs. Preserved as an xfail in the attack test. |

## What held

- Active and passive declarative examples kept agent, patient, and recipient terms tied to spans containing those exact source phrases.
- A negative past-tense frame retained negative polarity and past time.
- A document interrogative was returned as unread instead of an asserted clause.
- Separate input sources retained separate source names and sovereigns on clauses and role spans.
- A supersession marker such as `最新版` was retained as unsupported scope.
- A copular numeric value retained its exact quantity and source span.
- A direct `誰に` request projected the recipient variable and kept the other explicit roles bound.
- A recency-scoped request returned as typed unread.

## Not covered

- I did not test the downstream verifier, route, answer renderer, or stored-record resolution; this attack exercises the reader only.
- I did not exhaust Japanese case frames, coordination, quotations, ellipsis, numeric formats, or all tense and modality forms.
- I did not test how an application consumes clauses carrying `unsupported` markers. The recency check establishes that the marker is present, not that every downstream consumer rejects that candidate.
