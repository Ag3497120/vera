# Semantic reader paraphrase attack

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| P1 | robustness | `read_request("誰が箱を運びましたか？")` compared with `read_request("箱を運んだのは誰ですか？")` | Both paraphrases should produce a typed question plan for `運ぶ`, with `箱` as patient and a variable agent. | The direct form produces that typed plan. The cleft form returns a typed unread request (`empty nominal path`) and no plan. The reproducer is retained as a non-strict xfail. |

## What held

- Topic/subject marking (`は`/`が`), argument order, and polite/plain predicate forms kept the same event frame in the covered examples.
- Recipient order and polite/plain forms kept the agent, patient, and recipient roles.
- Plain and polite copulas preserved an identity clause. Spacing within an Arabic numeral and unit preserved the typed quantity.
- Replacing the entity or predicate changed that term in the typed clause. Negation flipped polarity, and changing the quantity changed its typed value.
- An interrogative document sentence stayed unread rather than becoming an asserted clause; a direct event question produced a role-bound plan.

## Not covered

This was a narrow set of hand-written Japanese paraphrases. It did not cover broad vocabulary or dialect variation, long multi-clause documents, complex scope, passive/causative alternations, or execution of question plans against evidence. The test does not establish general semantic equivalence beyond the examples above.

## Acceptance run

The required test command completed with 10 passed and 1 xfailed.
