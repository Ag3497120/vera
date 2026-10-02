# Semantic coordination paraphrase attack

Scope: direct tests of the contract in `verantyx/semantic_coord.py`, using hand-built sentence-token tuples. The acceptance command completed with **11 passed, 3 xfailed**.

## Findings

| ID | Severity | Minimal repro | Expected | Observed |
|---|---|---|---|---|
| coordination-tail | wrong-ANSWER | `太郎は食べ(連用)て(接続助詞)から(接続助詞)帰る`, predicate indexes `[2, 5]` | `coordination_ok` is false because the connective after `て` is not licensed by the documented chain form. | True on both direct reproductions. The scan checks the consumed `て` but skips `から` before the next predicate. |
| span-start | robustness | Token `クク` spans `[0, 2)`, topic particle `は` follows; request span `[1, 2)`. | False: the start is inside a token, not at the chunk start or after a particle/punctuation boundary. | True. |
| span-end | robustness | One noun token `ククル` spans `[0, 3)`; request span `[0, 2)`. | False: the end is inside a token, not before a particle, punctuation, or predicate. | True. |

The coordination defect was evaluated twice with the same input before reporting. Each finding has a non-strict xfail reproducer so it remains visible while the acceptance command passes.

## What held

- The same te-chain verdict held when only the final predicate surface changed from plain `帰る` to polite `帰ります`.
- A bare renyō predicate followed by a comma was accepted, while adjacent predicates without a permitted separator were rejected.
- A later clause's own `は` or `が` phrase was detected; a later clause without either marker was not.
- The first-clause topic span followed the entity surface (`太郎` or `猫`) and covered the whole tested noun token.
- A whole topic token ending before its particle was phrase-bounded, and a requested fragment that left a neighboring noun token was rejected.
- An adversative `が` chain was rejected.

## Not covered

These tests do not exercise a tokenizer/tagger or the surrounding semantic pipeline. They do not cover every connective, particle-tag variation, word-order pattern, multi-token noun phrase, or malformed token-span layout. No external or held-out material was used.
