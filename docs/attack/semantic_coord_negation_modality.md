# Semantic coordination: negation and modality attack

Scope: direct calls to `verantyx.semantic_coord` with synthetic sentence-relative tags. The module licenses only te/renyō coordination and exposes structural subject and phrase-boundary helpers; it does not assign semantic polarity or modality.

## Findings

| id | severity | minimal repro | expected | observed |
|---|---|---|---|---|
| SCNM-01 | robustness | `学生 / の / 規則 / は / 守ら / ない`; `topic_phrase(tags, [4])` | The first clause's topic phrase spans `学生の規則`, `(0, 5)`. | Returns `(3, 5)`, omitting the genitive modifier. |
| SCNM-02 | robustness | `申請 / し(連用) / て / も / よい`; `coordination_ok(tags, [1, 4])` | False: `てもよい` is a permission construction, and `も` is not a new noun phrase. | Returns `True`. |
| SCNM-03 | robustness | `薬 / を / 飲ん(連用) / で / は / なら / ない`; `coordination_ok(tags, [2, 5])` | False: `ではならない` is a prohibition construction; `は` does not supply a new noun phrase. | Returns `True`. |
| SCNM-04 | robustness | `食べ(連用) / て / すぐ / 帰る`; `coordination_ok(tags, [0, 3])` | False: the material before the next predicate is adverbial, not the required new noun phrase. | Returns `True`. |
| SCNM-05 | robustness | `戻ら[0:3] / ない[3:5]`; `phrase_bounded(tags, 1, 3)` | False: the role span starts inside a token rather than at a chunk start or after a boundary. | Returns `True`. |

Each finding has a minimal non-strict xfail in the attack tests. The expectations above follow the module's stated coordination and phrase-boundary contract.

## What held

- A te-connected chain passed when its first predicate had a 連用 form, including examples whose later material was negative or double-negative.
- The 連用 predicate followed by `が` or `ので` was rejected as coordination.
- `ない` tagged as an auxiliary did not itself make a clause count as having a は/が-marked subject phrase.
- A simple は-topic span and a later clause's が-marked phrase were recognized.
- A split lexical neighbor and katakana ASCII-art token `ノシ` were not accepted as safe phrase boundaries.
- A final question mark did not alter the structural te-chain check.

## Not covered

- No morphology analyzer, full semantic IR, route, or downstream answer behavior was exercised; tags and character spans were supplied directly.
- No conclusion is made about whether negative, double-negative, hearsay, obligation, permission, prohibition, or question content is semantically represented downstream. This module has no polarity or modality result to inspect.
- The attack did not test all possible connective spellings, tokenizers, or malformed token/index inputs.

## Acceptance run

Command: `/Users/motonisihikoudai/vera-wiring/env/bin/python -B -m pytest -q tests/attack/test_semantic_coord_negation_modality.py`

Result: **11 passed, 5 xfailed**.
