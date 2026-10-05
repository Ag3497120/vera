# Semantic names fabrication attack

Scope: `verantyx.semantic_names` span covering, title/name splitting, and past-auxiliary recognition. Inputs below are synthetic token tuples and lightweight feature objects; no corpus or network data was used.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
| --- | --- | --- | --- | --- |
| SNF-1 | wrong-ANSWER | `tokens_covering([("技師", "名詞", "一般", 0, 2), ("", "名詞", "固有名詞", 2, 2)], 0, 2)`, then `name_split_in(cover, "技師")` | `None`; an empty token cannot support a proper-name answer | Returns `("技師", "")`. The xfailed regression assertion reproduced in two separate targeted pytest invocations. |

## What held

- Adjacent tokens exactly covering a requested span are returned; a gap or a token crossing the requested start yields `None`.
- Tokens wholly outside a requested span do not affect its exact cover.
- A kanji descriptor followed by one proper-noun token is split; the helper rejects a non-kanji prefix, a non-proper final token, and a surface/value mismatch.
- Past-auxiliary recognition accepts lemma `た` with auxiliary POS and rejects a different lemma or non-auxiliary POS.

## What I did not cover

- The defect uses a synthetic zero-width token. I did not establish whether an upstream tokenizer can emit one.
- The module receives token features and offsets, not source records. Stale or superseded records, negation, entity-role swaps, and end-to-end answer provenance are outside this module-level probe.
- I did not exercise a production tokenizer, the semantic route, a corpus, or any held-out/development material.

## Acceptance run

Required full-file command: `VERA_CORPUS_ROOT=/tmp/vera-empty-materials PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. /Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_semantic_names_fabrication.py`.

Result: 11 passed, 1 xfailed (exit status 0).
