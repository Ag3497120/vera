# Semantic coordination Unicode/noise attack

Scope: direct tests of `verantyx.semantic_coord` using synthetic tagged tokens. The coordinator contract licenses only the documented te/で and comma coordination chain, shares the first topic only under its subject-phrase rule, and requires phrase edges at particles or real punctuation.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| U1 | robustness | `phrase_bounded([("🔥", "補助記号", "", "", 0, 1), ("猫", "名詞", "一般", "", 1, 2), ("見る", "動詞", "自立", "終止形", 2, 4)], 1, 2)` | `False`: an emoji is not a particle or real punctuation, so it must not establish the left phrase edge. | `True`. The same result occurred for a combining mark, zero-width space, and `<` markup residue tagged as `補助記号`. The four cases are retained as non-strict xfails. |

## What held

- The acceptance run reported 10 passed and 4 xfailed in 0.09 seconds.
- A canonical `て、` chain and a bare renyō form followed by `、` were accepted; a bare renyō form without a separator was refused.
- Fullwidth comma, halfwidth katakana `ﾃ`, and zero-width noise inserted before `て` did not license coordination.
- Katakana ascii art `ノシ` tagged as `補助記号` did not establish a phrase edge.
- Topic spans and `tag()` offsets included combining marks by Python code point length. A halfwidth `ﾊ` token was not treated as the exact topic particle `は`.

## What was not covered

- No tokenizer/tagger was run; all inputs were synthetic tokens, so behavior on real OCR or mixed-script parser output remains untested.
- Normalization variants, broader markup and ascii-art forms, and runtime behavior on long or malformed token streams were not explored.
- The coordinator implementation was not changed. The reported issue is a phrase-boundary robustness defect, not a demonstrated wrong answer or fabrication.
