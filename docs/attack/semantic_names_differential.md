# Semantic names differential attack

## Method

The tests use separate reference functions based on the helper docstrings: the token reference walks forward from the requested offset, and the name reference checks for common-noun or suffix descriptor tokens followed by one proper-noun token. The generated comparisons cover token partitions and kanji-title/name pairs. Past-auxiliary cases check the documented `lemma == た` rule, including surface `だ`.

## Findings

| id | severity | minimal repro | expected | observed |
| --- | --- | --- | --- | --- |
| supplementary-kanji-title | robustness | `[("𠮷人", "名詞", "一般", 0, 2), ("ユン", "名詞", "固有名詞", 2, 4)]`, value `𠮷人ユン` | `("𠮷人", "ユン")`: a common-noun title made of kanji followed by one proper noun | `None`; the helper's character check stops at `鿿`, so it rejects the supplementary-plane ideograph `𠮷`. The reproducer is marked xfail with the defect stated in its reason. |

## What held

Exact contiguous token covers, gaps and partial-boundary rejection, kanji appositive splitting, the one-final-proper-noun rule, and lemma-based past-auxiliary recognition matched the independent expectations in the acceptance run. That run reported **10 passed, 1 xfailed in 0.08 seconds**.

## What was not covered

These checks use constructed tags and offsets; they do not exercise a Japanese tokenizer or validate its POS assignments on natural sentences. They do not exhaust malformed token records or all Unicode ideographs. No corpus or external data was used.
