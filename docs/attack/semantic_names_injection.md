# Semantic names injection attack

Scope: direct tests of `verantyx/semantic_names.py` name-splitting, token-covering, and past-auxiliary helpers. No downstream caller was exercised.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| SN-I-01 | robustness | `cover=[("我輩","名詞","代名詞",0,2),("ユン","名詞","固有名詞",2,4)]`; `name_split_in(cover,"我輩ユン")` | `None`: the descriptor must be a common noun or noun suffix, while `代名詞` is a pronoun subtype. | `("我輩","ユン")`: the helper rejects only the exact `固有名詞` subtype for preceding noun tokens. The reproducer is marked `xfail` in the test suite. |

No wrong-ANSWER or fabrication behavior was observed in these helper tests.

## What held

- Token covering returned adjacent tokens for the requested range and rejected a gap or a token that did not tile the range.
- Name splitting accepted a Kanji title followed by one proper noun, and rejected a single-token name, a non-Kanji descriptor, a mismatched value, and a non-proper final token.
- An instruction-like proper-name surface was returned as literal name text by the helper.
- Past-auxiliary detection followed the auxiliary POS and lemma, including when the surface text differed.
- Acceptance command result: **12 passed, 1 xfailed**.

## What was not covered

- No tokenizer integration, surrounding semantic-name callers, authority decisions, or escalation behavior were exercised. Literal handling by this helper does not establish safety of downstream consumers.
- No malformed tuple/object inputs, performance stress, or corpus examples were tested.
- The robustness finding is a tagged-input classification issue; no generated answer, ungrounded claim, crash, or hang was tested or observed.
