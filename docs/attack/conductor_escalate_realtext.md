# Conductor escalation stress findings

## Findings

The findings below are contract properties exercised with typed, in-memory cases. They are robustness observations, not claims that these properties were tested against Wikipedia text.

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| R-01 | robustness | Call `enrich` with an `ANSWER`, or with an `ESCALATE` and no original `AgentQuestion`. | Reject before creating a handoff; require an escalation and its original question. | Both calls raised `ValueError` with the contract-specific message. |
| R-02 | robustness | Enrich an escalation with question id, options, and claimed state; inspect the handoff and sidecars. | Retain the exact question for re-ask; record one unresolved refusal and one detected gap; leave the reply typed as `ESCALATE`. | The same `AgentQuestion` object was retained, serialized question and re-ask matched, and both sidecars contained the unresolved event and gap. |
| R-03 | robustness | Enrich a `PERMIT_RECORD` escalation using shelf metadata for a subject. | Return typed missing-record and shelf metadata without converting the refusal into an answer. | `record_kind`, shelf, allowed source, and coverage-hole fields matched; the reply remained `ESCALATE` with no answer value. |
| R-04 | robustness | Enrich an outside-frame-authority escalation, then re-ask with a cited answer; separately enrich a vocabulary escalation. | Route both to a human; do not close the protected action from a document citation. | Both were routed to `human`; the protected handoff stayed open after the cited answer. |
| R-05 | robustness | Re-ask with a non-`ANSWER`, an uncited `ANSWER`, or an answer citing an inactive id. | Keep the gap open unless the reply is an `ANSWER` citing an active record. | All three cases returned unresolved. An answer citing an active id closed the gap and added one resolved outcome. |
| R-06 | robustness | Repeat the same enrichment and resolution check; then enrich the same subject with a different cause. | Deduplicate identical refusal entries while preserving distinct causes as separate gaps. | Repeated entries were deduplicated; the distinct cause received a separate gap and ledger event. |

No wrong-`ANSWER`, ungrounded-output, crash, or hang defect was reproduced in these cases. No xfail was needed. The checks used injected frame, sidecar, and conductor objects, so they do not establish behavior for every production integration.

## What held

- The handoff preserves the original question, its options, and its claimed state for re-asking.
- An escalation stays an escalation and records a typed missing-material description alongside the refusal ledger and gap.
- Authority and vocabulary cases select the human route. A protected action cannot be closed by a later cited answer.
- A normal handoff closes only after the unchanged question gets an `ANSWER` with a citation to an active record.
- Repeated refusal/resolution records deduplicate, while different causes for the same subject remain separately represented.
- The required test run completed with **11 passed in 0.16 seconds**; no test hung or crashed.

## Real-text attempt and limits

I attempted the named Wikipedia lead loader with `load(8, 1)`. It raised `FileNotFoundError` because its configured `jawiki_leads.full.jsonl` corpus file was unavailable. No rows were loaded, so no train-only real-text cases reached `conductor_escalate`; the real-text crash, hang, wrong-answer, and ungrounded-output rates are therefore **not measurable (0 leads sampled)**. The 11 passing checks above use constructed typed questions and replies, not real Wikipedia leads.

Not covered: production `ProjectFrame` integration, concurrent sidecar writes, interruption during persistence, and a conductor that stalls during `answer()`. No network or forbidden dataset was used.
