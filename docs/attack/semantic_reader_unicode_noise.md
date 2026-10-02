# Semantic reader Unicode and noise attack

The reader must preserve source-bound evidence or leave uncertain input unread. These checks exercise width variants, mixed scripts, combining marks, invisible format characters, markup, emoji, ASCII art, and OCR-like text.

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| U1 | robustness | `太郎が花子を見た。` | One source-bound frame with agent `太郎`, patient `花子`, and past tense. | Held: both role spans match the input; the clause has no unsupported marker. |
| U2 | robustness | `太郎が花子を見た！` | Fullwidth sentence punctuation keeps the Japanese clause and raw source span. | Held: one clause retains the full input span. |
| U3 | robustness | `ﾀﾛｳが花子を見た。` | Halfwidth katakana remains faithful in its role value and span. | Held: agent term and span are `ﾀﾛｳ`. |
| U4 | robustness | `Taroが花子を見た。` | Mixed Latin and Japanese text retains the written name. | Held: agent term and span are `Taro`. |
| U5 | robustness | `太郎がCaféを見た。` (the `é` is `e` plus U+0301) | Combining-mark content should be unread or marked unsupported, not silently omitted from a supported frame. | Held: the raw clause span is retained and the candidate is marked unsupported. |
| U6 | robustness | `太郎が花​子を見た。` (U+200B between `花` and `子`) | Zero-width noise in an argument should be unread or flagged as unsupported. | Held: candidate is flagged as unsupported and retains the raw clause span. |
| U7 | robustness | `**太郎**が花子を見た。` | Markup residue should not yield a fully supported frame with omitted source content. | Held: candidate is marked unsupported and retains the raw clause span. |
| U8 | robustness | `太郎が🙂花子を見た。` | Emoji should not alter the roles, and the source span should retain the original sentence. | Held: roles remain source-bound and the clause span includes the emoji. |
| U9 | robustness | `:-) 太郎が花子を見た。` | ASCII-art prefix should be refused as a typed unread span. | Held: there is no clause; the full sentence is unread. |
| U10 | robustness | `太郎が花子を見たxx。` | OCR-like trailing residue should not become a supported frame. | Held: the clause is marked unsupported. |
| U11 | robustness | `太郎が花孑を見た。` | A visually similar written glyph should be preserved verbatim rather than silently normalized. | Held: the patient term and span retain `花孑`. |
| U12 | wrong-ANSWER | `太郎が花子を見​なかった。` (U+200B between `見` and `なかった`) | The source means a past negative. It should be unread or represented with negative polarity. | Defect, reproduced twice: the reader emits one past clause with positive polarity and `unrepresented source content` in `unsupported`. |

## What held

The clean positive and negative examples retained their expected polarity and past tense. Fullwidth terminal punctuation, halfwidth katakana, mixed Latin/Japanese names, and an OCR-like confusable glyph retained source-bound spans. Combining marks, zero-width argument noise, markup residue, and OCR-like trailing text produced unsupported candidates rather than supported clauses. The ASCII-art prefix became a typed unread span. Emoji remained inside the raw clause span while the adjacent Japanese roles stayed intact.

## What I did not cover

This is a targeted suite, not exhaustive Unicode fuzzing. It does not cover every normalization form, bidi control, script combination, emoji sequence, OCR substitution, or markup grammar. It also does not exercise downstream verification or answer generation, and it does not benchmark long-input performance. The reader was not changed because this unit permits edits only to the test and findings files.
