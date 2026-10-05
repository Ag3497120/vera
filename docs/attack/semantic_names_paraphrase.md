# Semantic names paraphrase attack

Scope: `tokens_covering`, `name_split_in`, and `is_past_aux` in `verantyx/semantic_names.py`. Inputs below use the helper's token and feature contracts.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| — | — | No reproducible defect found in the exercised cases. | Same contract-valid variants retain the split or past-auxiliary result; malformed covers and non-past auxiliaries are rejected. | The focused suite passed all 16 cases. |

## What held

- Exact adjacent token spans were returned, while gaps and partial overlaps were rejected.
- Changing the following particle and clause surface from plain to polite left the extracted title and name unchanged.
- A kanji common-noun title followed by one proper-noun token split into descriptor and name. A noun suffix was accepted in the descriptor, and a katakana prefix was not split as a title.
- Changing the proper-name token preserved the valid split and returned the changed name. Mismatched values and invalid token categories were rejected.
- Past auxiliary surfaces `た` and `だ` were both recognized when their lemma was `た`; a non-past lemma and a non-auxiliary POS were rejected.

## What was not covered

These direct helper tests do not exercise the sentence reader, tokenizer integration, candidate routing, downstream answer construction, or natural-language paraphrase judgments. They do not establish behavior for alternate appositive order, honorific suffixes after names, or tokenizer-specific feature encodings.
