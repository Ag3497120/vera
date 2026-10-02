# Remedy fabrication and provenance attack

## Findings

The acceptance run produced no reproducible defect, so no finding has a severity classification.

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |

## What held

The targeted acceptance command completed with **16 passed**. `remedy` kept the supplied subject, terms, missing terms, language, and deictic in their matching fields. It did not copy unrelated answer, citation, evidence, or source-record values into its output. Negated and partial context strings remained unchanged; the function did not turn them into claims.

Known answer-like and terminal verdicts were passed through without emitting an answer payload. The tested `UNKNOWN_TIME_DEPENDENT` and `UNKNOWN_NO_SUBJECT` cases remained non-registration routes. An unrecognized refusal returned the generic no-remedy response without adopting supplied answer or record metadata. Empty context values were omitted.

## What I did not cover

This attack covered direct calls to `verantyx.remedy.remedy` only. The function receives no source records, so this did not test whether an upstream component selected a correct, current record or assigned the initial verdict correctly. I did not test malformed non-dictionary inputs, concurrent mutation of nested context values, or the semantic correctness of any advice text. No xfail was added because no defect was reproduced.
