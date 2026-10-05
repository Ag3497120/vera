# Semantic verifier attack: negation and modality

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| N1 | wrong-ANSWER | Audit `whether(走る)` against `走るな。`; repeat with `whether(触る)` against `触るな。` | A prohibition is not factual evidence that the event occurs or does not occur, so the audit should return no factual answer. | Both clauses are licensed as `polarity='+'`, `modality='assert'`; the audit returns `answer=True`. Reproduced with both sentences. The xfailed test records the defect. |
| N2 | ungrounded | `license_clause` on `水は冷たくない。`; repeat with `部屋は暗くない。` | A negated adjective must not be certified as a positive identity assertion. | Both are represented as `identity`, positive polarity, assert modality, and `license_clause` accepts them. The xfailed test records the defect. |

## What held

- `太郎は来ない。` is licensed as a negative event assertion. `東京は大阪ではない。` is licensed with negative polarity, while `東京は大阪だ。` remains positive.
- The tested double-negative sentence `太郎は走らなくはない。` is rejected as unsupported instead of being used as an ordinary negative fact.
- The question `太郎は来るか。` produces no factual answer. The hearsay sentence `太郎は来るそうだ。` is rejected by source licensing even though its current clause metadata says `assert`.
- A normative pattern can match permission and prohibition clauses, while a permission-only pattern does not match a prohibition clause. The tested native permission and prohibition sentences are rejected as unsupported rather than licensed as facts.
- The audit distinguishes explicit negative evidence from missing evidence: `太郎は来ない。` yields `False` for the tested `whether(来る)` query, while an empty source yields no answer.
- Acceptance run: **9 passed, 4 xfailed**.

## Not covered

- The examples are hand selected; this does not cover all Japanese negative conjugations, dialects, spelling variants, or ない-adjectives.
- I did not test the complete request, proof replay, and `gate` path. Tests exercise `license_clause`, `_match`, and the verifier's independent audit.
- I did not cover broad obligation syntax, nested quotations, conditional scope, or multi-predicate modality combinations.
- No verifier implementation changes were made; this unit only adds attack tests and findings.
