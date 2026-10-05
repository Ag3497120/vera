# Semantic names limits attack

The checks exercise `tokens_covering`, `name_split_in`, and `is_past_aux` using constructed inputs. They do not use corpus data.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| SN-L1 | robustness | `tokens_covering([("技師", ..., 0, 2), ("ユン", ..., 2, 4)][::-1], 0, 4)` | Return both tokens in span order because their spans tile the interval regardless of input order. | Returns `None`; the iteration order is used as the span order. Reproduced by the xfail test. |
| SN-L2 | robustness | `tokens_covering([("技師", ..., 0, 2), ("師", ..., 1, 2)], 1, 2)` | Return `None`; an existing token crosses the requested start boundary, so the in-range token does not form an unambiguous covering. | Returns the second token after filtering out the crossing token. Reproduced by the xfail test. |

## What held

- Correctly ordered tokens tiled the requested span, outside tokens were ignored, and gaps and empty spans returned `None`.
- Name splitting accepted kanji common-noun descriptors followed by one proper-noun token, and refused a non-kanji prefix, a lone proper name, a text mismatch, and a proper-noun descriptor token.
- Past auxiliary recognition followed the auxiliary POS and lemma, including a voiced surface with lemma `た`.
- A 20,000-token descriptor, a 20,000-character non-kanji prefix, repeated calls, two concurrent independent callers, and a retained-allocation check completed with the asserted outcomes.

## Not covered

- Malformed token tuple shapes, non-integer or negative offsets, and objects missing `feature` fields are outside the typed inputs exercised here.
- No timing claim is made beyond the test's 20-second ceiling; there is no explicit module-level budget or input-size limit to inspect.
- This attack did not evaluate the callers that create token spans or the broader semantic pipeline.
