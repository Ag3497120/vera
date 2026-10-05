# Semantic verifier Unicode and noise attack

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| `uq-curly` | robustness | `猫は“青い。犬は白い”と言う。` | Preserve the full sentence range or refuse unsupported quotation marks; do not treat punctuation inside the quote as a source boundary. | `_ranges` returns `(0, 6)` and `(6, 15)`, splitting at the quoted `。`. The non-strict xfail records this behavior. |
| `uq-halfwidth` | robustness | `猫は｢青い。犬は白い｣と言う。` | Preserve the full sentence range or refuse unsupported quotation marks; do not treat punctuation inside the quote as a source boundary. | `_ranges` returns `(0, 6)` and `(6, 15)`, splitting at the quoted `。`. The non-strict xfail records this behavior. |

## What held

- Japanese sentence marks produced exact source ranges. Japanese corner quotes, including nested `「」` and `『』`, kept inner punctuation within the quoted range; an unclosed Japanese quote raised `Rejected`.
- The range helper retained halfwidth punctuation, combining marks, zero-width characters, mixed scripts, emoji sequences, markup residue, and ASCII art without normalizing or dropping those characters in the exercised cases.
- The symbolic record licensing path accepted a Unicode actor when the source term matched exactly, rejected a Latin/Cyrillic confusable mismatch, and rejected fullwidth formula delimiters.
- The native prefix guard rejected ASCII and fullwidth colon scopes. A prefix containing a combining mark passed when its condition span used the exact source offsets; dropping that condition was rejected.

The acceptance command completed with **16 passed, 2 xfailed**. Both xfails are the quotation-boundary defects listed above.

## What I did not cover

- I did not exercise reader-to-plan-to-proof behavior or construct a full proof proposal. The checks cover the verifier's range and native-scope helpers plus its symbolic record licensing branch.
- I did not exercise tokenizer-based frame, copula, identity, or measure licensing with Unicode input, including fullwidth numeric quantities, bidi controls, or malformed byte decoding.
- These results do not establish end-to-end answer correctness; the two quote variants show that the range helper can silently split text it does not recognize as a quotation.
