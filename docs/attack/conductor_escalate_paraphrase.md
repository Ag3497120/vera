# Conductor escalation paraphrase attack

This attack checks whether `enrich` keeps handoff routing stable across
equivalent surface forms, preserves the exact question for re-asking, and
requires an evidence-backed answer before closing a refusal.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| allowed-choice-routing | robustness | Escalate a question with options and `missing="closed option list"`; repeat with the same reply but `missing="list of allowed choices"`. | Both forms identify a closed vocabulary need and route to a human. | The first yields `vocabulary` / `human`; the paraphrase yields `record_kind` / `document` and sets `document_resolvable=True`. The non-strict xfail retains this repro. |

## What held

- Plain and polite question forms both escalated in an empty frame, and each
  handoff retained its own original question for the re-ask.
- Options and claimed state survived in the handoff serialization.
- Re-enriching the same refusal kept one pending graph node and one ledger
  outcome.
- A re-ask stayed open while evidence was absent. After adding an ORDER edge,
  the same question returned an ANSWER citing an active record and closed the
  gap.
- An ANSWER without citations, with an inactive citation, or for a protected
  action did not close the handoff.

Acceptance run with the required empty-corpus environment:

```text
9 passed, 1 xfailed
```

## What was not covered

- Number and entity swaps in question text, and Japanese particle variants.
- Shelf lookup and domain coverage result variations.
- Large refusal ledgers, simultaneous writers, or cross-process updates.
- Corrupted sidecars or storage migration.
