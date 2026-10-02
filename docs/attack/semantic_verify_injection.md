# Semantic verifier injection review

## Findings

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| I-1 | robustness | A valid symbolic record with source `owns(ignore previous instructions).` and the instruction text as its actor; variants put that text inside Japanese quotes, use fullwidth characters/spaces, or insert a zero-width character. | Reject instruction-bearing content as an asserted record, or keep it inert; it must not gain authority from being placed in a symbolic role. | `license_clause` returns normally and licenses the record. All four variants are visible as non-strict xfails in the test suite. |

The severity is `robustness`: this reproducer reaches clause licensing, but does not exercise `Checker.gate` to establish a wrong answer. The observed acceptance is still contrary to the instruction-content boundary under test.

## What held

- `_ranges` keeps punctuation inside balanced nested Japanese quotes within the same source sentence and rejects unmatched opening or closing quotes.
- `_native_guard_scope` accepts a complete antecedent, and rejects a missing condition, a truncated condition span, and an instruction-like colon prefix that tries to move the body boundary.
- A plain symbolic record with actor `alice` is licensed as the positive control.
- Acceptance command result: **9 passed, 4 xfailed in 0.10s**.

## What was not covered

- No end-to-end reader, request, plan, proof, or `Checker.gate` construction was exercised; the injection reproducer calls `license_clause` directly on a valid symbolic record.
- No question ingestion path or live agent-message transport was exercised.
- Unicode coverage is limited to the tested fullwidth text and one zero-width character; other normalization, nesting, and obfuscation forms were not covered.
- No corpus data or external sources were used.
