# `semantic_names.py` real-text attack

## Findings

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| R1 | robustness | `tokens_covering([("技師", "名詞", "一般", 1, 3), ("ユン", "名詞", "固有名詞", 3, 5)], 1, 5)` | Return the two tokens when they tile the requested span. | Returned both tokens in the acceptance run. |
| R2 | robustness | `name_split_in([("技師", "名詞", "一般", 0, 2), ("ユン", "名詞", "固有名詞", 2, 3)], "技師ユン")` | Return `("技師", "ユン")` for a kanji title followed by one proper-name token. | Returned the expected pair in the acceptance run. |
| R3 | robustness | `name_split_in([("コカ", "名詞", "一般", 0, 2), ("カル", "名詞", "固有名詞", 2, 4)], "コカカル")` | Do not split a katakana prefix that may be part of an unknown name. | Returned `None` in the acceptance run. |
| R4 | robustness | `is_past_aux(SimpleNamespace(feature=SimpleNamespace(pos1="助動詞", lemma="た")))` | Recognize the past auxiliary by lemma, including the voiced surface form. | Returned `True` in the acceptance run. |

No wrong-answer, ungrounded-output, crash, or hang defect was reproduced. These findings document helper-contract checks, not lead-paragraph outcomes.

## What held

The acceptance run passed 11 tests. They covered contiguous token tiling, gaps, boundary-crossing and overlapping tokens, title-plus-name splitting, katakana-fragment rejection, proper-noun constraints, exact surface matching, and past-auxiliary identification by lemma and part of speech.

## Real-text coverage and omissions

Attempted to sample 40 Wikipedia leads with `tools/round5a_route_tune.py:load(40, 1)`, which filters to `split == "train"`. The loader raised `FileNotFoundError` for its configured corpus file, `/Users/motonisihikoudai/Projects/vera-corpus/build/round4/jawiki_leads.full.jsonl`; consequently 0 leads were loaded and no real-text crash, hang, wrong-answer, ungrounded-output, or rate could be measured. Synthetic tagged-token examples above are kept separate from that unavailable real-text sample.

No tokenizer-to-helper end-to-end behavior or broader corpus behavior was covered.
