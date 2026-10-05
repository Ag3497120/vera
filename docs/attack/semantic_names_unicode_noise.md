# Attack findings: semantic names Unicode and noise

Scope: `tokens_covering`, `name_split_in`, and `is_past_aux` in
`verantyx/semantic_names.py`. Inputs were constructed locally; no corpus or
external data was used.

## Findings

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| N1 | robustness | `cover=[("技師","名詞","一般",0,2),("","名詞","固有名詞",2,2)]`; `name_split_in(cover,"技師")` | `None`: an empty token cannot supply the required proper name | Returns `("技師", "")`; the regression test is marked xfail. |

## What held

- Exact spans use Python codepoint offsets correctly around an astral emoji in
  the prefix, and gaps are refused.
- A kanji title followed by one proper-name token splits as specified; a
  non-kanji descriptor or non-proper final token is refused.
- Full-width text, a decomposed combining sequence, and markup/emoji in the
  tagged name are returned unchanged as Python strings, without normalization
  or cleanup.
- A zero-width character in the descriptor is refused.
- Past-auxiliary classification follows lemma `た` even when the surface has
  voiced or zero-width noise; a different lemma is refused.

## What was not covered

This attack did not exercise the upstream tokenizer/tagger, offset generation,
normalization policy outside these helpers, malformed tuple shapes, or runtime
behavior on real user messages. The coverage here is limited to synthetic
helper inputs.
