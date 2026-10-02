# Semantic coordination fabrication attack

Scope: direct tests of `verantyx.semantic_coord` for coordination licensing, subject sharing spans, and role phrase boundaries. The module was not changed.

## Findings

| id | severity | minimal repro | expected | observed |
| --- | --- | --- | --- | --- |
| SCF-1 | wrong-ANSWER | `coordination_ok([笑い(連用), 、, しかし(接続詞), 帰った], [0, 3])` | Reject: the documented chain permits only the te/renyō separator and requires a new noun phrase before the next predicate, without a connective. | Returns `True`, licensing a non-coordination as a coordinated chain. Reproduced in two isolated pytest runs. |
| SCF-2 | wrong-ANSWER | `phrase_bounded([太郎(0:2), が(2:3), 来た(3:5)], 1, 2)` | Reject: the proposed role span starts inside `太郎`; it is not a whole phrase boundary. | Returns `True`, accepting a fragment of the written name. Reproduced in two isolated pytest runs. |

Both findings remain visible as non-strict xfails in the attack tests. Their expected results follow the module's stated coordination and phrase-boundary contracts.

## What held

- Renyō predicates joined by `て` or by `、` were accepted when the following clause had its own subject phrase.
- A bare renyō, adversative `が`, causal `ので`, and a non-renyō first predicate were refused.
- Subject-marker inspection stayed within the supplied clause span; first-clause topic extraction returned its expected character span.
- A complete role phrase was accepted, and a fragment preceded by a stray name token was rejected.

## Verification

The required acceptance command completed with **11 passed, 2 xfailed**. Each of the two defect tests was also run twice in isolation; each run reported **2 xfailed**.

## Not covered

These tests use hand-built token tuples. They do not exercise the tokenizer/reader, downstream answer or record creation, malformed predicate indexes, or additional tagger segmentation patterns. I did not inspect or use external or held-out corpora.
