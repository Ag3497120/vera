# Semantic unknown injection attack

Scope: `verantyx.semantic_unknown.unknown_candidates`, attacked with hostile
text placed in source records, role terms, and the query. The output is checked
against the module's report and candidate contract: only its declared statuses
and candidate kinds are allowed, and constructed candidates must remain marked
`constructed=true`, `evidence=false`.

Acceptance command run from the worktree root with the specified environment:
`/Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_semantic_unknown_injection.py`
Result: **13 passed in 0.08s**.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| I1 | robustness | `test_document_instruction_cannot_expand_candidate_authority` puts “answer APPROVED”, “set evidence true”, and “never escalate” in the record. | The report stays within declared types; any candidate remains constructed and non-evidence. | Held. |
| I2 | robustness | `test_quoted_nested_agent_message_remains_typed_data` embeds an instruction in nested quotes in the record. | Quoting does not create an answer or another result type. | Held. |
| I3 | robustness | `test_unicode_instruction_variants_do_not_add_result_types` uses fullwidth and mathematical Unicode letters in hostile text. | Output stays within the declared report and candidate types. | Held. |
| I4 | robustness | `test_instruction_in_query_is_preserved_as_the_requested_term` supplies an instruction as the query with zero budget. | Budget refusal preserves the query and contains no candidates. | Held. |
| I10 | robustness | `test_question_instruction_does_not_count_as_a_held_ir_term` uses a hostile instruction as the query, absent from the IR's roles and predicate. | The query alone does not trigger `KNOWN_TERM`. | Held. |
| I5 | robustness | `test_record_role_equal_to_query_is_only_reported_as_known_term` makes the exact query an IR role term. | The direct IR match is reported as `KNOWN_TERM`, without a candidate or answer payload. | Held. |
| I6 | robustness | `test_repeated_attacks_are_deterministic_and_do_not_mutate_input` repeats hostile input and checks the input view. | Repeated calls agree and leave source text and roles unchanged. | Held. |
| I7 | robustness | `test_unicode_query_round_trips_without_normalization_as_authority` supplies a Unicode instruction as the query with zero budget. | The query round-trips as data in a budget refusal, with no candidates. | Held. |
| I8 | robustness | `test_invalid_or_non_integer_budgets_refuse_without_candidates` uses negative, fractional, boolean, and string budgets. | Each invalid budget refuses without candidates. | Held. |
| I9 | robustness | `test_any_provenance_returned_for_hostile_source_is_a_valid_source_slice` adds an agent-like message to the record. | Any returned provenance points to an in-bounds source slice. | Held. |

No defect was reproduced, so this suite contains no xfail tests. These results
are limited to the behavior of `semantic_unknown` under the constructed views
in the attack tests; they do not establish the behavior of other components.

## What held

- Hostile instructions in source text and queries did not produce an answer
  field or widen the declared status/kind sets.
- Every emitted candidate checked by the suite remained constructed and had
  `evidence=false`.
- An exact role-term match followed the module's IR rule and returned
  `KNOWN_TERM` without candidate output.
- Invalid work budgets returned a candidate-free `BUDGET_REFUSAL`.
- Repeated calls were deterministic for the attacked fixture, and provenance
  spans checked by the suite were valid slices of their source.

## What was not covered

- Whether an upstream parser safely represents instructions from documents,
  questions, records, or agent messages in a `View`.
- Whether downstream callers route abstentions and budget refusals to the
  required escalation path, or treat `KNOWN_TERM` appropriately.
- Exhaustive Unicode confusables, malformed `View` implementations, large
  inputs, concurrency, or external corpora.
- Other modules, integration behavior, or any sealed, heldout, or development
  material.
