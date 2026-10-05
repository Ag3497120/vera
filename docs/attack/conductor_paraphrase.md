# Conductor paraphrase attack

Independent surface-variant checks against `verantyx/conductor.py`. The acceptance run completed with **8 passed and 3 xfailed**.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| CP-1 | robustness | With a `CONFIRM` policy for `archive the draft` → `yes`, ask “Would it be okay if I archive the draft?” or “Would archiving the draft be acceptable?” | Same `ANSWER yes` as “Can I archive the draft?” | Both paraphrases are classified outside the closed question patterns and return `ESCALATE`. |
| CP-2 | wrong-ANSWER | With a `CONFIRM` policy for singular `archive the draft` → `yes`, ask “Can I archive the drafts?” and “Could I archive the drafts?” | Escalate because the plural entity is not the singular policy condition. | Both questions return `ANSWER yes`; the condition substring matches inside the plural phrase. |
| CP-3 | wrong-ANSWER | With a `CONFIRM` policy for positive `archive the draft` → `yes`, ask “Can I not archive the draft?” and “Could I not archive the draft?” | Escalate because the policy does not cover the negated action. | Both questions return `ANSWER yes`; matching the positive condition ignores negation. |

Each wrong-ANSWER reproducer exercised two question variants in the test run. The expected escalation follows from the policy record's narrower positive singular condition; the answer path must not extend that record to a changed entity number or polarity.

## What held

- Recognized next/order paraphrases, including the Japanese next-step form, kept the `ORDER` classification.
- Common `Can I` / `Could I` / `May I` confirmation forms kept the `CONFIRM` classification and returned the same policy answer.
- Two recognized order phrasings returned the same uniquely ready successor from the active `ORDER` and `TASK` records.
- A protected delete request escalated even with a related archive policy present.
- A missing confirmation policy, malformed choice options, and a done claim without task identity escalated.

## Not covered

Choice resolution and aliases, scope policies, completion witnesses and independent verifier records, conflicting frame records, and broad Japanese policy-answer paraphrases were not exercised. The tests use temporary frames created by the test fixture and do not inspect external corpora.
