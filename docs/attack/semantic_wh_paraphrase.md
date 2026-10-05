# Semantic WH paraphrase attack

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| WH-PAR-single-role | robustness | `read_role_list_question("誰が？", builder, full)` | A wildcard `Bind` with the single asked role `agent`, following the reader's documented wh-plus-case form and wildcard-plan contract. | Returns `None` on both repeated calls; no plan is emitted. |

No wrong-ANSWER or fabrication case was confirmed. The acceptance run reported **10 passed, 1 xfailed**; the xfail is the single-role repro above.

## What held

- Plain and polite/punctuated wh-only forms produced the same wildcard role plan.
- Reordering the wh-role phrases retained the same requested roles, with output order following the phrases.
- The forms `誰`/`だれ` and `何`/`なに`, the agent particles `が`/`は`, and different wh entities retained the role plan when the role particles stayed the same.
- Changing `を` to `に` changed the patient role to recipient.
- The role nouns `渡した人`/`送り主` and `終点`/`受取人` preserved their mapped role plans.
- Repeating an agent role returned `None` without emitting a binding or output.

## Not covered

These checks call the reader with a recording builder. They do not exercise document matching, ambiguity across multiple events, downstream verification, or corpus behavior. Predicate-bearing questions and surface forms outside the wh-plus-case and listed role-noun shapes were not assessed.
