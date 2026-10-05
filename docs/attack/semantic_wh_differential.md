# Semantic WH differential review

## Findings

The differential cases produced no disagreements, so there are no defect rows.

| id | severity (wrong-ANSWER, ungrounded, crash, hang, robustness) | minimal repro | expected | observed |
|---|---|---|---|---|

## What held

- A question with at least two distinct requested roles emits one wildcard `Pattern` bind; a one-role request or repeated semantic role abstains.
- Wh-plus-case phrases map to their case roles, and role-noun lists map to their listed roles. Output labels preserve the full wh-plus-case phrase or noun, in source order.
- The plan keeps the wildcard predicate and default `Pattern` fields, passes through the supplied `full` value, and emits one matching output per role.
- The accepted surface shapes handle surrounding whitespace, the optional `ですか` suffix, and trailing `?`, `？`, or `。` punctuation.
- The independent reference parser and the implementation agreed on the generated distinct-role wh/case combinations, generated noun pairs, and the listed abstention and near-miss cases. The acceptance run completed with 18 tests passing.

The reference model tokenizes wh words and case particles from left to right and separately parses noun lists. It uses its own local role maps and does not import parser constants or call parser helpers from `semantic_wh.py`. Expected plan fields come from the documented wildcard-bind contract and the `Pattern` IR shape.

## Not covered

- Integration with the semantic question reader, routing, coordination, or downstream answer selection.
- Whether a wildcard plan is grounded or unambiguous against any document; this unit only checks question reading and plan construction.
- Inputs outside the two documented question shapes, and stress behavior beyond the bounded generated cases.
- Corpus behavior; no corpus or external data was used.
