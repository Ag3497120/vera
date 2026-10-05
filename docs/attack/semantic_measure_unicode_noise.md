# Semantic measure Unicode and noise attack

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| U1 | ungrounded | `りんごは3龘` | Refuse a unit glyph with no grounded dimension, or preserve it as unknown without assigning a dimension. | The parser returns a `measure.counter` clause with quantity unit `龘`. The regression test is xfailed because this broad CJK unit match assigns a counter dimension. |

## What held

- Fullwidth digits, a fullwidth decimal separator, and the compatibility unit glyph `㎏` were refused.
- Decomposed combining marks, halfwidth katakana, zero-width characters, and emoji in labels were retained literally with matching source-span text.
- Inline markup in a label was retained as part of that label. Markdown-style residue outside the sentence was refused.
- The sum question accepted a fullwidth question mark. A fullwidth unit spelling and an inserted zero-width character were refused without adding plan nodes.
- ASCII measure values were represented as exact `Decimal` values, and the amount-plus-unit source span was preserved.

## Not covered

- I did not inspect the IR unit table because the unit rules permit opening only `verantyx/semantic_measure.py`. The arbitrary-Han result is reported as a defect based on the measure contract's requirement that dimensions come from the unit proof rule; the underlying IR fallback policy remains unverified.
- I did not exercise downstream plan verification or execution, normalization across other scripts, OCR image input, or combinations of multiple noise types in one sentence.
